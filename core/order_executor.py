"""
Order Executor - Handles order submission to exchanges.

Converts OrderIntent into actual exchange orders with proper
error handling, retries, and status tracking.
"""
import uuid
from datetime import datetime
from typing import Optional, Tuple
from loguru import logger

from core.models import OrderIntent, Order, OrderStatus, OrderSide
from exchanges.kalshi_client import kalshi_client


class OrderExecutor:
    """
    Executes orders on connected exchanges.
    
    Handles:
    - Order submission with proper formatting
    - Error handling and retries
    - Order status tracking
    - Latency measurement
    """
    
    def __init__(self):
        self._pending_orders: dict[str, Order] = {}
        self._completed_orders: list[Order] = []
    
    async def execute(
        self,
        intent: OrderIntent
    ) -> Tuple[Optional[Order], str]:
        """
        Execute an order intent on the appropriate exchange.
        
        Args:
            intent: The order intent to execute.
            
        Returns:
            Tuple of (Order object, status message).
        """
        start_time = datetime.utcnow()
        
        # Create internal order record
        order = Order(
            id=str(uuid.uuid4()),
            intent_id=intent.id,
            match_id=intent.match_id,
            market_id=intent.market_id,
            exchange=intent.exchange,
            side=intent.side,
            outcome=intent.outcome,
            size=intent.size,
            limit_price=intent.limit_price,
            status=OrderStatus.PENDING
        )
        
        self._pending_orders[order.id] = order
        
        try:
            if intent.exchange == "kalshi":
                result = await self._execute_kalshi(intent, order)
            else:
                return (None, f"Unknown exchange: {intent.exchange}")
            
            # Calculate latency
            end_time = datetime.utcnow()
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            if result:
                order.exchange_order_id = result.get("order_id")
                order.status = OrderStatus.SUBMITTED
                order.submitted_at = end_time
                
                # Check if immediately filled
                if result.get("status") == "filled":
                    order.status = OrderStatus.FILLED
                    order.filled_at = end_time
                    order.filled_size = intent.size
                    order.avg_fill_price = result.get("avg_price", intent.limit_price)
                
                logger.info(
                    f"Order executed: {order.id} -> {order.exchange_order_id} "
                    f"(latency: {latency_ms:.0f}ms)"
                )
                
                return (order, f"Order submitted successfully (latency: {latency_ms:.0f}ms)")
            else:
                order.status = OrderStatus.REJECTED
                order.error_message = "Exchange rejected order"
                return (order, "Order rejected by exchange")
                
        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.error_message = str(e)
            logger.error(f"Order execution failed: {e}")
            return (order, f"Execution error: {e}")
        
        finally:
            # Move to completed
            if order.id in self._pending_orders:
                del self._pending_orders[order.id]
            self._completed_orders.append(order)
    
    async def _execute_kalshi(
        self,
        intent: OrderIntent,
        order: Order
    ) -> Optional[dict]:
        """
        Execute order on Kalshi.
        
        Args:
            intent: Order intent.
            order: Internal order record.
            
        Returns:
            Exchange response dict or None.
        """
        # Convert price to cents (Kalshi uses 1-99)
        price_cents = int(intent.limit_price * 100)
        price_cents = max(1, min(99, price_cents))
        
        # Convert size to contracts
        # Kalshi contracts are typically $1 each at resolution
        # Size in dollars / price = number of contracts
        num_contracts = int(intent.size / intent.limit_price)
        num_contracts = max(1, num_contracts)
        
        logger.info(
            f"Submitting Kalshi order: {intent.market_id} "
            f"{intent.side.value} {num_contracts} contracts @ {price_cents}c"
        )
        
        result = await kalshi_client.place_order(
            ticker=intent.market_id,
            side=intent.side,
            outcome=intent.outcome,
            size=num_contracts,
            limit_price=price_cents,
            client_order_id=order.id
        )
        
        return result
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Internal order ID.
            
        Returns:
            True if cancelled, False otherwise.
        """
        order = self._pending_orders.get(order_id)
        if not order:
            logger.warning(f"Order {order_id} not found in pending orders")
            return False
        
        if order.exchange == "kalshi" and order.exchange_order_id:
            success = await kalshi_client.cancel_order(order.exchange_order_id)
            if success:
                order.status = OrderStatus.CANCELLED
                del self._pending_orders[order_id]
                self._completed_orders.append(order)
                return True
        
        return False
    
    async def check_order_status(self, order_id: str) -> Optional[Order]:
        """
        Check and update order status.
        
        Args:
            order_id: Internal order ID.
            
        Returns:
            Updated Order object or None.
        """
        # Check pending orders first
        order = self._pending_orders.get(order_id)
        if not order:
            # Check completed orders
            for o in self._completed_orders:
                if o.id == order_id:
                    return o
            return None
        
        # Query exchange for status
        if order.exchange == "kalshi" and order.exchange_order_id:
            orders = await kalshi_client.get_orders(status="open")
            
            # Check if still open
            is_open = any(
                o.get("order_id") == order.exchange_order_id
                for o in orders
            )
            
            if not is_open:
                # Order is no longer open - check if filled
                closed_orders = await kalshi_client.get_orders(status="closed")
                for o in closed_orders:
                    if o.get("order_id") == order.exchange_order_id:
                        if o.get("status") == "filled":
                            order.status = OrderStatus.FILLED
                            order.filled_at = datetime.utcnow()
                            order.filled_size = o.get("filled_count", order.size)
                            order.avg_fill_price = o.get("avg_price", order.limit_price) / 100
                        elif o.get("status") == "cancelled":
                            order.status = OrderStatus.CANCELLED
                        break
                
                # Move to completed
                del self._pending_orders[order_id]
                self._completed_orders.append(order)
        
        return order
    
    def get_pending_orders(self) -> list[Order]:
        """Get all pending orders."""
        return list(self._pending_orders.values())
    
    def get_completed_orders(self, limit: int = 100) -> list[Order]:
        """Get recent completed orders."""
        return self._completed_orders[-limit:]
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        if order_id in self._pending_orders:
            return self._pending_orders[order_id]
        for order in self._completed_orders:
            if order.id == order_id:
                return order
        return None


# Singleton instance
order_executor = OrderExecutor()
