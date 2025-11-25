"""
Integration tests for the trading pipeline.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from core.models import (
    Match, Team, GoalEvent, Market, MatchMarketMapping,
    OrderIntent, Order, Position, Trade, MatchStatus, OrderSide, OrderStatus
)
from core.state import StateManager
from core.decision_engine import DecisionEngine
from core.risk_manager import RiskManager
from services.trade_service import TradeService


class TestTradingPipeline:
    """Integration tests for the full trading pipeline."""
    
    @pytest.fixture
    def state_manager(self):
        """Fresh state manager for each test."""
        sm = StateManager()
        sm.reset()
        return sm
    
    @pytest.fixture
    def decision_engine(self):
        """Fresh decision engine."""
        engine = DecisionEngine()
        engine.underdog_threshold = 0.5
        engine.min_liquidity = 100
        return engine
    
    @pytest.fixture
    def risk_manager(self):
        """Fresh risk manager."""
        rm = RiskManager()
        rm.bankroll = 10000
        rm.max_per_trade_pct = 0.005
        rm.daily_loss_limit = 500
        rm.per_match_max_exposure = 200
        return rm
    
    @pytest.fixture
    def sample_match(self):
        """Sample match fixture."""
        return Match(
            id=99999,
            league_id=39,
            league_name="Premier League",
            home_team=Team(id=1, name="Arsenal"),
            away_team=Team(id=2, name="Brentford"),
            home_score=0,
            away_score=0,
            status=MatchStatus.FIRST_HALF,
            minute=25,
            kickoff=datetime(2024, 1, 15, 15, 0, 0)
        )
    
    @pytest.fixture
    def underdog_goal(self, sample_match):
        """Goal by underdog team."""
        return GoalEvent(
            id="99999-away-1-30",
            match_id=sample_match.id,
            timestamp=datetime.utcnow(),
            minute=30,
            scoring_team_id=2,  # Brentford (away/underdog)
            scoring_team_name="Brentford",
            is_home_team=False,
            home_score=0,
            away_score=1
        )
    
    @pytest.fixture
    def market_mapping(self, sample_match):
        """Market mapping with underdog having low probability."""
        return MatchMarketMapping(
            match_id=sample_match.id,
            home_team_name=sample_match.home_team.name,
            away_team_name=sample_match.away_team.name,
            league_name=sample_match.league_name,
            kickoff=sample_match.kickoff,
            markets=[
                Market(
                    id="SOCCER-EPL-ARS-BRE-WIN",
                    exchange="kalshi",
                    title="Brentford to win vs Arsenal",
                    yes_price=0.25,  # Underdog price
                    no_price=0.75,
                    yes_volume=5000,
                    no_volume=3000,
                    status="open"
                )
            ],
            pre_goal_home_prob=0.65,  # Arsenal favored
            pre_goal_away_prob=0.25   # Brentford underdog
        )
    
    def test_decision_engine_generates_intent_for_underdog(
        self, decision_engine, sample_match, underdog_goal, market_mapping
    ):
        """Test that decision engine generates intent when underdog scores."""
        intent = decision_engine.evaluate_goal(
            underdog_goal,
            sample_match,
            market_mapping
        )
        
        assert intent is not None
        assert intent.market_id == "SOCCER-EPL-ARS-BRE-WIN"
        assert intent.side == OrderSide.BUY
        assert "underdog" in intent.reason.lower()
    
    def test_risk_manager_approves_valid_trade(
        self, risk_manager, sample_match, market_mapping
    ):
        """Test that risk manager approves valid trades."""
        intent = OrderIntent(
            id="test-intent",
            match_id=sample_match.id,
            market_id="SOCCER-EPL-ARS-BRE-WIN",
            exchange="kalshi",
            side=OrderSide.BUY,
            outcome="yes",
            size=0,
            limit_price=0.27,
            reason="Test trade",
            goal_event_id="test-goal"
        )
        
        approved, reason = risk_manager.approve_trade(intent)
        
        assert approved is not None
        assert approved.size == 50.0  # 10000 * 0.005
        assert "approved" in reason.lower()
    
    def test_risk_manager_blocks_when_daily_limit_reached(
        self, risk_manager, sample_match
    ):
        """Test that risk manager blocks trades when daily limit reached."""
        risk_manager._daily_pnl = -500  # At limit
        
        intent = OrderIntent(
            id="test-intent",
            match_id=sample_match.id,
            market_id="TEST-MKT",
            exchange="kalshi",
            side=OrderSide.BUY,
            outcome="yes",
            size=0,
            limit_price=0.50,
            reason="Test",
            goal_event_id="test"
        )
        
        approved, reason = risk_manager.approve_trade(intent)
        
        assert approved is None
        assert "daily loss limit" in reason.lower()
    
    def test_state_manager_tracks_positions(self, state_manager):
        """Test that state manager correctly tracks positions."""
        position = Position(
            id="pos-1",
            match_id=12345,
            market_id="TEST-MKT",
            exchange="kalshi",
            outcome="yes",
            size=50.0,
            entry_price=0.30,
            current_price=0.35,
            status="open",
            opened_at=datetime.utcnow(),
            entry_order_id="order-1"
        )
        
        state_manager.add_position(position)
        
        assert len(state_manager.get_open_positions()) == 1
        assert state_manager.get_position("pos-1") is not None
    
    def test_state_manager_closes_position(self, state_manager):
        """Test position closing and P/L calculation."""
        position = Position(
            id="pos-2",
            match_id=12345,
            market_id="TEST-MKT",
            exchange="kalshi",
            outcome="yes",
            size=50.0,
            entry_price=0.30,
            current_price=0.30,
            status="open",
            opened_at=datetime.utcnow(),
            entry_order_id="order-2"
        )
        
        state_manager.add_position(position)
        
        # Close with profit
        closed = state_manager.close_position("pos-2", 0.40, "exit-order")
        
        assert closed is not None
        assert closed.status.value == "closed"
        assert closed.realized_pnl > 0  # Profit
        assert len(state_manager.get_open_positions()) == 0
    
    def test_goal_deduplication(self, state_manager, underdog_goal):
        """Test that goals are properly deduplicated."""
        # First time - not processed
        assert not state_manager.is_goal_processed(underdog_goal.id)
        
        # Mark as processed
        state_manager.mark_goal_processed(underdog_goal)
        
        # Second time - should be processed
        assert state_manager.is_goal_processed(underdog_goal.id)
    
    def test_metrics_update_on_trade(self, state_manager):
        """Test that metrics are updated when trades are recorded."""
        trade = Trade(
            id="trade-1",
            match_id=12345,
            match_name="Arsenal vs Brentford",
            market_id="TEST-MKT",
            exchange="kalshi",
            outcome="yes",
            entry_price=0.30,
            exit_price=0.40,
            size=50.0,
            pnl=16.67,
            pnl_pct=33.3,
            entry_time=datetime.utcnow(),
            exit_time=datetime.utcnow(),
            goal_event_id="goal-1",
            reason="Test trade"
        )
        
        state_manager.add_trade(trade)
        
        metrics = state_manager.get_metrics()
        assert metrics.total_trades == 1
        assert metrics.winning_trades == 1
        assert metrics.total_pnl == 16.67


class TestMonitoringService:
    """Tests for the monitoring service."""
    
    def test_latency_tracking(self):
        """Test latency measurement tracking."""
        from services.monitoring import MonitoringService
        from datetime import timedelta
        
        service = MonitoringService()
        event_time = datetime.utcnow()
        order_time = event_time + timedelta(milliseconds=150)  # 150ms later
        
        service.record_goal_event("goal-1", event_time)
        service.record_order_submitted("goal-1", order_time)
        
        stats = service.get_stats()
        assert stats.total_orders == 1
        assert stats.avg_event_to_order_ms >= 150  # At least 150ms
    
    def test_fill_rate_calculation(self):
        """Test fill rate calculation."""
        from services.monitoring import MonitoringService
        
        service = MonitoringService()
        
        # Record some orders
        for i in range(10):
            service.record_goal_event(f"goal-{i}", datetime.utcnow())
            service.record_order_submitted(f"goal-{i}", datetime.utcnow())
        
        # 8 fills, 2 rejections
        for i in range(8):
            service.record_order_filled(
                f"goal-{i}", f"order-{i}",
                datetime.utcnow(), 0.30, 0.31
            )
        
        service.record_order_rejected("Test rejection 1")
        service.record_order_rejected("Test rejection 2")
        
        stats = service.get_stats()
        assert stats.total_orders == 10
        assert stats.filled_orders == 8
        assert stats.rejected_orders == 2
        assert stats.fill_rate == 0.8
    
    def test_health_check(self):
        """Test health status reporting."""
        from services.monitoring import MonitoringService
        
        service = MonitoringService()
        
        # Fresh service should be healthy
        stats = service.get_stats()
        assert stats.is_healthy is True
        assert len(stats.health_issues) == 0


class TestPostTradeManager:
    """Tests for post-trade management."""
    
    def test_take_profit_detection(self):
        """Test take-profit condition detection."""
        from core.post_trade import PostTradeManager
        
        manager = PostTradeManager()
        manager.take_profit_pct = 0.15  # 15%
        
        position = Position(
            id="pos-1",
            match_id=12345,
            market_id="TEST",
            exchange="kalshi",
            outcome="yes",
            size=50.0,
            entry_price=0.30,
            current_price=0.36,  # 20% gain
            status="open",
            opened_at=datetime.utcnow(),
            entry_order_id="order-1"
        )
        
        assert manager.check_take_profit(position) is True
    
    def test_stop_loss_detection(self):
        """Test stop-loss condition detection."""
        from core.post_trade import PostTradeManager
        
        manager = PostTradeManager()
        manager.stop_loss_pct = 0.10  # 10%
        
        position = Position(
            id="pos-1",
            match_id=12345,
            market_id="TEST",
            exchange="kalshi",
            outcome="yes",
            size=50.0,
            entry_price=0.30,
            current_price=0.25,  # 16.7% loss
            status="open",
            opened_at=datetime.utcnow(),
            entry_order_id="order-1"
        )
        
        assert manager.check_stop_loss(position) is True
    
    def test_pnl_calculation(self):
        """Test P/L calculation."""
        from core.post_trade import PostTradeManager
        
        manager = PostTradeManager()
        
        # Long YES, price goes up
        pnl, pnl_pct = manager.calculate_pnl(0.30, 0.40, 100.0, "yes")
        assert pnl > 0
        assert pnl_pct > 0
        
        # Long YES, price goes down
        pnl, pnl_pct = manager.calculate_pnl(0.30, 0.20, 100.0, "yes")
        assert pnl < 0
        assert pnl_pct < 0
