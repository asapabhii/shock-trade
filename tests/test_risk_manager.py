"""
Tests for the risk manager.
"""
import pytest
from core.risk_manager import RiskManager
from core.models import OrderIntent, OrderSide


class TestRiskManager:
    """Test suite for RiskManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rm = RiskManager()
        self.rm.bankroll = 10000
        self.rm.max_per_trade_pct = 0.005  # 0.5%
        self.rm.daily_loss_limit = 500
        self.rm.per_match_max_exposure = 200
        self.rm.max_consecutive_errors = 5
    
    def test_calculate_position_size_basic(self, sample_order_intent):
        """Test basic position size calculation."""
        size = self.rm.calculate_position_size(sample_order_intent, 0.35)
        
        # Should be bankroll * max_per_trade_pct = 10000 * 0.005 = 50
        assert size == 50.0
    
    def test_calculate_position_size_respects_daily_limit(self, sample_order_intent):
        """Test that position size respects daily loss limit."""
        # Simulate daily loss
        self.rm._daily_pnl = -480  # Only $20 remaining
        
        size = self.rm.calculate_position_size(sample_order_intent, 0.35)
        
        assert size == 20.0
    
    def test_calculate_position_size_respects_match_limit(self, sample_order_intent):
        """Test that position size respects per-match limit."""
        # Simulate existing exposure
        self.rm._match_exposure[sample_order_intent.match_id] = 180  # Only $20 remaining
        
        size = self.rm.calculate_position_size(sample_order_intent, 0.35)
        
        assert size == 20.0
    
    def test_check_trade_allowed_normal(self, sample_order_intent):
        """Test trade is allowed under normal conditions."""
        allowed, reason = self.rm.check_trade_allowed(sample_order_intent)
        
        assert allowed is True
    
    def test_check_trade_blocked_circuit_breaker(self, sample_order_intent):
        """Test trade blocked when circuit breaker active."""
        self.rm._circuit_breaker_active = True
        
        allowed, reason = self.rm.check_trade_allowed(sample_order_intent)
        
        assert allowed is False
        assert "circuit breaker" in reason.lower()
    
    def test_check_trade_blocked_daily_limit(self, sample_order_intent):
        """Test trade blocked when daily limit reached."""
        self.rm._daily_pnl = -500  # At limit
        
        allowed, reason = self.rm.check_trade_allowed(sample_order_intent)
        
        assert allowed is False
        assert "daily loss limit" in reason.lower()
    
    def test_check_trade_blocked_match_exposure(self, sample_order_intent):
        """Test trade blocked when match exposure limit reached."""
        self.rm._match_exposure[sample_order_intent.match_id] = 200  # At limit
        
        allowed, reason = self.rm.check_trade_allowed(sample_order_intent)
        
        assert allowed is False
        assert "per-match" in reason.lower()
    
    def test_approve_trade_sets_size(self, sample_order_intent):
        """Test that approve_trade sets the position size."""
        sample_order_intent.size = 0  # Start with no size
        
        approved, reason = self.rm.approve_trade(sample_order_intent)
        
        assert approved is not None
        assert approved.size == 50.0
        assert "approved" in reason.lower()
    
    def test_record_error_triggers_circuit_breaker(self):
        """Test that consecutive errors trigger circuit breaker."""
        for i in range(5):
            self.rm.record_error(f"Error {i}")
        
        assert self.rm._circuit_breaker_active is True
        assert self.rm._consecutive_errors == 5
    
    def test_record_success_resets_errors(self):
        """Test that success resets error counter."""
        self.rm._consecutive_errors = 3
        
        self.rm.record_success()
        
        assert self.rm._consecutive_errors == 0
    
    def test_reset_circuit_breaker(self):
        """Test manual circuit breaker reset."""
        self.rm._circuit_breaker_active = True
        self.rm._consecutive_errors = 5
        
        self.rm.reset_circuit_breaker()
        
        assert self.rm._circuit_breaker_active is False
        assert self.rm._consecutive_errors == 0
    
    def test_record_trade_result(self):
        """Test recording trade results."""
        self.rm.record_trade_result(
            match_id=12345,
            pnl=25.0,
            exposure_change=50.0
        )
        
        assert self.rm._daily_pnl == 25.0
        assert self.rm._match_exposure[12345] == 50.0
    
    def test_get_status(self):
        """Test getting risk status."""
        self.rm._daily_pnl = -100
        self.rm._match_exposure[12345] = 50
        
        status = self.rm.get_status()
        
        assert status.daily_pnl == -100
        assert status.daily_loss_remaining == 400  # 500 - 100
        assert status.current_exposure == 50
        assert status.circuit_breaker_active is False
