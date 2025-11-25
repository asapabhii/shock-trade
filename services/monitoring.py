"""
Monitoring Service - Collects and exposes trading metrics.

Tracks:
- Latency from goal event to order submission
- Latency from goal event to fill
- Slippage (expected vs actual fill price)
- Fill rate
- Error rates
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from collections import deque
from loguru import logger

from config import settings


@dataclass
class LatencyMeasurement:
    """A single latency measurement."""
    event_id: str
    event_time: datetime
    order_time: Optional[datetime] = None
    fill_time: Optional[datetime] = None
    
    @property
    def event_to_order_ms(self) -> Optional[float]:
        if self.order_time:
            return (self.order_time - self.event_time).total_seconds() * 1000
        return None
    
    @property
    def event_to_fill_ms(self) -> Optional[float]:
        if self.fill_time:
            return (self.fill_time - self.event_time).total_seconds() * 1000
        return None


@dataclass
class SlippageMeasurement:
    """A single slippage measurement."""
    order_id: str
    expected_price: float
    actual_price: float
    
    @property
    def slippage(self) -> float:
        """Slippage in basis points."""
        return (self.actual_price - self.expected_price) * 10000


@dataclass
class MonitoringStats:
    """Aggregated monitoring statistics."""
    # Latency stats
    avg_event_to_order_ms: float = 0
    max_event_to_order_ms: float = 0
    min_event_to_order_ms: float = 0
    p95_event_to_order_ms: float = 0
    
    avg_event_to_fill_ms: float = 0
    max_event_to_fill_ms: float = 0
    
    # Slippage stats
    avg_slippage_bps: float = 0
    max_slippage_bps: float = 0
    
    # Fill stats
    total_orders: int = 0
    filled_orders: int = 0
    rejected_orders: int = 0
    fill_rate: float = 0
    
    # Error stats
    total_errors: int = 0
    errors_last_hour: int = 0
    
    # Health
    is_healthy: bool = True
    health_issues: List[str] = field(default_factory=list)


class MonitoringService:
    """
    Collects and aggregates trading metrics.
    
    Maintains rolling windows of measurements for real-time stats.
    """
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        
        # Rolling windows
        self._latencies: deque[LatencyMeasurement] = deque(maxlen=window_size)
        self._slippages: deque[SlippageMeasurement] = deque(maxlen=window_size)
        self._errors: deque[datetime] = deque(maxlen=window_size)
        
        # Counters
        self._total_orders = 0
        self._filled_orders = 0
        self._rejected_orders = 0
        
        # Thresholds for health checks
        self.max_acceptable_latency_ms = settings.max_latency_ms
        self.max_acceptable_slippage_bps = 50  # 0.5%
        self.min_acceptable_fill_rate = 0.8  # 80%
    
    def record_goal_event(self, event_id: str, event_time: datetime) -> None:
        """Record when a goal event was detected."""
        measurement = LatencyMeasurement(
            event_id=event_id,
            event_time=event_time
        )
        self._latencies.append(measurement)
    
    def record_order_submitted(self, event_id: str, order_time: datetime) -> None:
        """Record when an order was submitted for a goal event."""
        for measurement in reversed(self._latencies):
            if measurement.event_id == event_id:
                measurement.order_time = order_time
                
                latency = measurement.event_to_order_ms
                if latency:
                    logger.debug(f"Goal-to-order latency: {latency:.0f}ms")
                    
                    if latency > self.max_acceptable_latency_ms:
                        logger.warning(
                            f"High latency detected: {latency:.0f}ms > "
                            f"{self.max_acceptable_latency_ms}ms threshold"
                        )
                break
        
        self._total_orders += 1
    
    def record_order_filled(
        self,
        event_id: str,
        order_id: str,
        fill_time: datetime,
        expected_price: float,
        actual_price: float
    ) -> None:
        """Record when an order was filled."""
        # Update latency measurement
        for measurement in reversed(self._latencies):
            if measurement.event_id == event_id:
                measurement.fill_time = fill_time
                break
        
        # Record slippage
        slippage = SlippageMeasurement(
            order_id=order_id,
            expected_price=expected_price,
            actual_price=actual_price
        )
        self._slippages.append(slippage)
        
        self._filled_orders += 1
        
        if abs(slippage.slippage) > self.max_acceptable_slippage_bps:
            logger.warning(
                f"High slippage detected: {slippage.slippage:.1f}bps "
                f"(expected {expected_price:.2f}, got {actual_price:.2f})"
            )
    
    def record_order_rejected(self, reason: str) -> None:
        """Record when an order was rejected."""
        self._rejected_orders += 1
        logger.warning(f"Order rejected: {reason}")
    
    def record_error(self, error: str) -> None:
        """Record an error occurrence."""
        self._errors.append(datetime.utcnow())
        logger.error(f"Monitoring recorded error: {error}")
    
    def get_stats(self) -> MonitoringStats:
        """Calculate and return current monitoring statistics."""
        stats = MonitoringStats()
        
        # Latency stats
        order_latencies = [
            m.event_to_order_ms for m in self._latencies
            if m.event_to_order_ms is not None
        ]
        
        if order_latencies:
            stats.avg_event_to_order_ms = sum(order_latencies) / len(order_latencies)
            stats.max_event_to_order_ms = max(order_latencies)
            stats.min_event_to_order_ms = min(order_latencies)
            
            # P95
            sorted_latencies = sorted(order_latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            stats.p95_event_to_order_ms = sorted_latencies[p95_idx] if sorted_latencies else 0
        
        fill_latencies = [
            m.event_to_fill_ms for m in self._latencies
            if m.event_to_fill_ms is not None
        ]
        
        if fill_latencies:
            stats.avg_event_to_fill_ms = sum(fill_latencies) / len(fill_latencies)
            stats.max_event_to_fill_ms = max(fill_latencies)
        
        # Slippage stats
        slippages = [s.slippage for s in self._slippages]
        if slippages:
            stats.avg_slippage_bps = sum(slippages) / len(slippages)
            stats.max_slippage_bps = max(abs(s) for s in slippages)
        
        # Fill stats
        stats.total_orders = self._total_orders
        stats.filled_orders = self._filled_orders
        stats.rejected_orders = self._rejected_orders
        stats.fill_rate = (
            self._filled_orders / self._total_orders
            if self._total_orders > 0 else 0
        )
        
        # Error stats
        stats.total_errors = len(self._errors)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        stats.errors_last_hour = sum(1 for e in self._errors if e > one_hour_ago)
        
        # Health check
        stats.is_healthy = True
        stats.health_issues = []
        
        if stats.avg_event_to_order_ms > self.max_acceptable_latency_ms:
            stats.is_healthy = False
            stats.health_issues.append(
                f"High average latency: {stats.avg_event_to_order_ms:.0f}ms"
            )
        
        if stats.fill_rate < self.min_acceptable_fill_rate and self._total_orders > 10:
            stats.is_healthy = False
            stats.health_issues.append(
                f"Low fill rate: {stats.fill_rate:.1%}"
            )
        
        if stats.errors_last_hour > 10:
            stats.is_healthy = False
            stats.health_issues.append(
                f"High error rate: {stats.errors_last_hour} errors in last hour"
            )
        
        return stats
    
    def reset(self) -> None:
        """Reset all monitoring data."""
        self._latencies.clear()
        self._slippages.clear()
        self._errors.clear()
        self._total_orders = 0
        self._filled_orders = 0
        self._rejected_orders = 0
        logger.info("Monitoring service reset")


# Singleton instance
monitoring_service = MonitoringService()
