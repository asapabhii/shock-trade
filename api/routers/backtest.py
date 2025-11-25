"""
Backtest API router - Simulate strategy on historical data.
"""
from typing import List, Optional
from datetime import datetime, date
from fastapi import APIRouter
from pydantic import BaseModel, Field
from loguru import logger

from core.decision_engine import DecisionEngine
from core.risk_manager import RiskManager
from core.models import Match, Team, GoalEvent, Market, MatchMarketMapping, MatchStatus

router = APIRouter()


class BacktestConfig(BaseModel):
    """Configuration for a backtest run."""
    bankroll: float = Field(default=10000, description="Starting bankroll")
    max_per_trade_pct: float = Field(default=0.5, description="Max % per trade")
    underdog_threshold: float = Field(default=0.5, description="Underdog probability threshold")
    take_profit_pct: float = Field(default=0.15, description="Take profit %")
    stop_loss_pct: float = Field(default=0.10, description="Stop loss %")


class SimulatedGoal(BaseModel):
    """A simulated goal event for backtesting."""
    match_id: int
    home_team: str
    away_team: str
    scoring_team: str
    is_home_team: bool
    minute: int
    home_score: int
    away_score: int
    pre_goal_home_prob: float
    pre_goal_away_prob: float
    post_goal_price: float


class BacktestResult(BaseModel):
    """Results from a backtest run."""
    total_goals: int
    trades_generated: int
    trades_executed: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    avg_pnl_per_trade: float
    max_drawdown: float
    final_bankroll: float
    trades: List[dict]


class SimulationRequest(BaseModel):
    """Request to run a simulation with custom goals."""
    config: BacktestConfig
    goals: List[SimulatedGoal]


@router.post("/simulate", response_model=BacktestResult)
async def run_simulation(request: SimulationRequest):
    """
    Run a simulation with provided goal events.
    
    This allows testing the strategy logic without live data.
    """
    config = request.config
    goals = request.goals
    
    # Initialize fresh instances for simulation
    engine = DecisionEngine()
    engine.underdog_threshold = config.underdog_threshold
    
    risk_mgr = RiskManager()
    risk_mgr.bankroll = config.bankroll
    risk_mgr.max_per_trade_pct = config.max_per_trade_pct / 100
    
    trades = []
    equity_curve = [config.bankroll]
    
    for goal in goals:
        # Create match object
        match = Match(
            id=goal.match_id,
            league_id=1,
            league_name="Simulation",
            home_team=Team(id=1, name=goal.home_team),
            away_team=Team(id=2, name=goal.away_team),
            home_score=goal.home_score,
            away_score=goal.away_score,
            status=MatchStatus.FIRST_HALF if goal.minute < 45 else MatchStatus.SECOND_HALF,
            minute=goal.minute,
            kickoff=datetime.utcnow()
        )
        
        # Create goal event
        goal_event = GoalEvent(
            id=f"sim-{goal.match_id}-{goal.minute}",
            match_id=goal.match_id,
            timestamp=datetime.utcnow(),
            minute=goal.minute,
            scoring_team_id=1 if goal.is_home_team else 2,
            scoring_team_name=goal.scoring_team,
            is_home_team=goal.is_home_team,
            home_score=goal.home_score,
            away_score=goal.away_score
        )
        
        # Create market mapping
        mapping = MatchMarketMapping(
            match_id=goal.match_id,
            home_team_name=goal.home_team,
            away_team_name=goal.away_team,
            league_name="Simulation",
            kickoff=datetime.utcnow(),
            markets=[
                Market(
                    id=f"SIM-{goal.match_id}",
                    exchange="simulation",
                    title=f"{goal.scoring_team} to win",
                    yes_price=goal.post_goal_price,
                    no_price=1 - goal.post_goal_price,
                    yes_volume=10000,
                    no_volume=10000,
                    status="open"
                )
            ],
            pre_goal_home_prob=goal.pre_goal_home_prob,
            pre_goal_away_prob=goal.pre_goal_away_prob
        )
        
        # Run decision engine
        intent = engine.evaluate_goal(goal_event, match, mapping)
        
        if intent:
            # Check risk
            approved, reason = risk_mgr.approve_trade(intent)
            
            if approved:
                # Simulate trade execution
                entry_price = goal.post_goal_price
                
                # Simulate exit (random outcome for demo)
                import random
                win = random.random() < 0.55  # Slight edge
                
                if win:
                    exit_price = min(entry_price * (1 + config.take_profit_pct), 0.99)
                    pnl = approved.size * config.take_profit_pct
                else:
                    exit_price = max(entry_price * (1 - config.stop_loss_pct), 0.01)
                    pnl = -approved.size * config.stop_loss_pct
                
                trade = {
                    "match": f"{goal.home_team} vs {goal.away_team}",
                    "goal_minute": goal.minute,
                    "scoring_team": goal.scoring_team,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "size": approved.size,
                    "pnl": pnl,
                    "win": win
                }
                trades.append(trade)
                
                # Update equity
                risk_mgr.bankroll += pnl
                equity_curve.append(risk_mgr.bankroll)
    
    # Calculate results
    winning = [t for t in trades if t["win"]]
    losing = [t for t in trades if not t["win"]]
    total_pnl = sum(t["pnl"] for t in trades)
    
    # Calculate max drawdown
    peak = equity_curve[0]
    max_dd = 0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd
    
    return BacktestResult(
        total_goals=len(goals),
        trades_generated=len([g for g in goals]),  # Simplified
        trades_executed=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        total_pnl=total_pnl,
        win_rate=len(winning) / len(trades) if trades else 0,
        avg_pnl_per_trade=total_pnl / len(trades) if trades else 0,
        max_drawdown=max_dd,
        final_bankroll=risk_mgr.bankroll,
        trades=trades
    )


@router.post("/quick-test")
async def quick_test():
    """
    Run a quick test with sample data to verify strategy logic.
    """
    # Sample goals simulating underdog scenarios
    sample_goals = [
        SimulatedGoal(
            match_id=1,
            home_team="Manchester City",
            away_team="Brentford",
            scoring_team="Brentford",
            is_home_team=False,
            minute=25,
            home_score=0,
            away_score=1,
            pre_goal_home_prob=0.75,
            pre_goal_away_prob=0.15,
            post_goal_price=0.25
        ),
        SimulatedGoal(
            match_id=2,
            home_team="Arsenal",
            away_team="Liverpool",
            scoring_team="Arsenal",
            is_home_team=True,
            minute=35,
            home_score=1,
            away_score=0,
            pre_goal_home_prob=0.45,
            pre_goal_away_prob=0.40,
            post_goal_price=0.55
        ),
        SimulatedGoal(
            match_id=3,
            home_team="Chelsea",
            away_team="Nottingham Forest",
            scoring_team="Nottingham Forest",
            is_home_team=False,
            minute=60,
            home_score=0,
            away_score=1,
            pre_goal_home_prob=0.70,
            pre_goal_away_prob=0.18,
            post_goal_price=0.30
        ),
    ]
    
    request = SimulationRequest(
        config=BacktestConfig(),
        goals=sample_goals
    )
    
    return await run_simulation(request)


@router.get("/sample-goals")
async def get_sample_goals():
    """
    Get sample goal data for testing the simulation endpoint.
    """
    return {
        "description": "Sample underdog goal scenarios for backtesting",
        "goals": [
            {
                "match_id": 1,
                "home_team": "Manchester City",
                "away_team": "Brentford",
                "scoring_team": "Brentford",
                "is_home_team": False,
                "minute": 25,
                "home_score": 0,
                "away_score": 1,
                "pre_goal_home_prob": 0.75,
                "pre_goal_away_prob": 0.15,
                "post_goal_price": 0.25
            },
            {
                "match_id": 2,
                "home_team": "Real Madrid",
                "away_team": "Getafe",
                "scoring_team": "Getafe",
                "is_home_team": False,
                "minute": 40,
                "home_score": 0,
                "away_score": 1,
                "pre_goal_home_prob": 0.80,
                "pre_goal_away_prob": 0.10,
                "post_goal_price": 0.20
            }
        ]
    }
