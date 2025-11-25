"""
Kalshi Demo API Client.

Kalshi is a regulated prediction market exchange.
This client connects to their DEMO environment for paper trading.

API Documentation: https://trading-api.readme.io/reference/getting-started
Uses RSA key authentication.
"""
import base64
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import httpx
from loguru import logger

from config import settings
from core.models import Market, OrderSide

# Try to import cryptography for RSA signing
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography package not installed - Kalshi RSA auth disabled")


class KalshiClient:
    """
    Async client for Kalshi Demo API with RSA authentication.
    """
    
    def __init__(self):
        self.base_url = settings.kalshi_base_url
        self.api_key = settings.kalshi_api_key
        self.private_key_path = settings.kalshi_private_key_path
        self._client: Optional[httpx.AsyncClient] = None
        self._private_key = None
        self._authenticated = False
        
        # Load private key if available
        self._load_private_key()
    
    def _load_private_key(self):
        """Load RSA private key from file or environment variable."""
        if not HAS_CRYPTO:
            return
        
        import os
        
        # Option 1: Load from KALSHI_PRIVATE_KEY env var (for cloud deployment)
        key_content = os.environ.get("KALSHI_PRIVATE_KEY")
        if key_content:
            try:
                # Handle escaped newlines from env var
                key_content = key_content.replace("\\n", "\n")
                self._private_key = serialization.load_pem_private_key(
                    key_content.encode(),
                    password=None,
                    backend=default_backend()
                )
                logger.info("Kalshi RSA private key loaded from environment variable")
                return
            except Exception as e:
                logger.error(f"Failed to load Kalshi private key from env: {e}")
        
        # Option 2: Load from file path
        key_path = Path(self.private_key_path)
        if not key_path.exists():
            logger.warning(f"Kalshi private key not found at {key_path}")
            return
            
        try:
            with open(key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            logger.info("Kalshi RSA private key loaded from file")
        except Exception as e:
            logger.error(f"Failed to load Kalshi private key: {e}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _sign_request(self, timestamp: str, method: str, path: str) -> str:
        """
        Sign a request using RSA private key.
        
        Kalshi signature format: timestamp + method + path (no body for GET)
        Uses RSA-PSS padding as per Kalshi docs.
        """
        if not self._private_key:
            return ""
        
        # Message to sign: timestamp (ms) + method (uppercase) + path
        message = f"{timestamp}{method.upper()}{path}"
        
        try:
            # Try PSS padding first (newer Kalshi API)
            signature = self._private_key.sign(
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        except Exception:
            # Fallback to PKCS1v15
            signature = self._private_key.sign(
                message.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_auth_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate authentication headers with RSA signature."""
        timestamp = str(int(time.time() * 1000))
        signature = self._sign_request(timestamp, method, path)
        
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
    
    async def login(self) -> bool:
        """
        Verify authentication with Kalshi API.
        
        With RSA auth, we don't need to login - just verify the key works.
        """
        if not self.api_key:
            logger.warning("Kalshi API key not configured")
            return False
            
        if not self._private_key:
            logger.warning("Kalshi private key not loaded")
            return False
        
        # Test authentication by fetching balance
        balance = await self.get_balance()
        if balance is not None:
            self._authenticated = True
            logger.info("Kalshi authentication successful")
            return True
        
        logger.warning("Kalshi authentication failed")
        return False
    
    async def get_balance(self) -> Optional[Dict[str, Any]]:
        """Get account balance."""
        client = await self._get_client()
        path = "/trade-api/v2/portfolio/balance"
        
        try:
            response = await client.get(
                path,
                headers=self._get_auth_headers("GET", path)
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.debug(f"Balance request failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error fetching Kalshi balance: {e}")
            return None
    
    async def get_markets(
        self,
        event_ticker: Optional[str] = None,
        series_ticker: Optional[str] = None,
        status: str = "open",
        limit: int = 100
    ) -> List[Market]:
        """Fetch markets from Kalshi."""
        client = await self._get_client()
        path = "/trade-api/v2/markets"
        
        params = {"limit": limit, "status": status}
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        
        try:
            response = await client.get(
                path,
                params=params,
                headers=self._get_auth_headers("GET", path)
            )
            
            if response.status_code != 200:
                logger.error(f"Markets request failed: {response.status_code}")
                return []
                
            data = response.json()
            
            markets = []
            for m in data.get("markets", []):
                market = Market(
                    id=m["ticker"],
                    exchange="kalshi",
                    title=m.get("title", m["ticker"]),
                    subtitle=m.get("subtitle"),
                    event_ticker=m.get("event_ticker"),
                    yes_price=m.get("yes_bid", 0) / 100 if m.get("yes_bid") else 0.5,
                    no_price=m.get("no_bid", 0) / 100 if m.get("no_bid") else 0.5,
                    yes_volume=m.get("volume", 0),
                    no_volume=m.get("volume", 0),
                    open_interest=m.get("open_interest", 0),
                    status=m.get("status", "open"),
                    expiration=datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")) if m.get("close_time") else None
                )
                markets.append(market)
            
            logger.debug(f"Fetched {len(markets)} markets from Kalshi")
            return markets
            
        except Exception as e:
            logger.error(f"Error fetching Kalshi markets: {e}")
            return []
    
    async def get_market(self, ticker: str) -> Optional[Market]:
        """Fetch a single market by ticker."""
        client = await self._get_client()
        path = f"/trade-api/v2/markets/{ticker}"
        
        try:
            response = await client.get(
                path,
                headers=self._get_auth_headers("GET", path)
            )
            
            if response.status_code != 200:
                return None
                
            m = response.json().get("market", {})
            
            return Market(
                id=m["ticker"],
                exchange="kalshi",
                title=m.get("title", m["ticker"]),
                subtitle=m.get("subtitle"),
                event_ticker=m.get("event_ticker"),
                yes_price=m.get("yes_bid", 50) / 100,
                no_price=m.get("no_bid", 50) / 100,
                yes_volume=m.get("volume", 0),
                no_volume=m.get("volume", 0),
                open_interest=m.get("open_interest", 0),
                status=m.get("status", "open")
            )
        except Exception as e:
            logger.error(f"Error fetching market {ticker}: {e}")
            return None
    
    async def get_orderbook(self, ticker: str) -> Dict[str, Any]:
        """Fetch orderbook for a market."""
        client = await self._get_client()
        path = f"/trade-api/v2/markets/{ticker}/orderbook"
        
        try:
            response = await client.get(
                path,
                headers=self._get_auth_headers("GET", path)
            )
            if response.status_code == 200:
                return response.json().get("orderbook", {})
            return {"yes": [], "no": []}
        except Exception as e:
            logger.error(f"Error fetching orderbook for {ticker}: {e}")
            return {"yes": [], "no": []}
    
    async def search_sports_markets(self, search_term: str) -> List[Market]:
        """Search for sports-related markets."""
        all_markets = await self.get_markets(limit=200)
        
        search_lower = search_term.lower()
        matching = [
            m for m in all_markets
            if search_lower in m.title.lower() or 
               (m.subtitle and search_lower in m.subtitle.lower())
        ]
        
        return matching
    
    async def place_order(
        self,
        ticker: str,
        side: OrderSide,
        outcome: str,
        size: int,
        limit_price: int,
        client_order_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Place an order on Kalshi."""
        client = await self._get_client()
        path = "/trade-api/v2/portfolio/orders"
        
        order_data = {
            "ticker": ticker,
            "action": side.value,
            "side": outcome.lower(),
            "count": size,
            "type": "limit",
            "yes_price" if outcome.lower() == "yes" else "no_price": limit_price
        }
        
        if client_order_id:
            order_data["client_order_id"] = client_order_id
        
        try:
            response = await client.post(
                path,
                json=order_data,
                headers=self._get_auth_headers("POST", path)
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"Order placed successfully: {data}")
                return data.get("order")
            else:
                logger.error(f"Order failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        client = await self._get_client()
        path = f"/trade-api/v2/portfolio/orders/{order_id}"
        
        try:
            response = await client.delete(
                path,
                headers=self._get_auth_headers("DELETE", path)
            )
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        client = await self._get_client()
        path = "/trade-api/v2/portfolio/positions"
        
        try:
            response = await client.get(
                path,
                headers=self._get_auth_headers("GET", path)
            )
            if response.status_code == 200:
                return response.json().get("market_positions", [])
            return []
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    async def get_orders(self, status: str = "open") -> List[Dict[str, Any]]:
        """Get orders."""
        client = await self._get_client()
        path = "/trade-api/v2/portfolio/orders"
        
        try:
            response = await client.get(
                path,
                params={"status": status},
                headers=self._get_auth_headers("GET", path)
            )
            if response.status_code == 200:
                return response.json().get("orders", [])
            return []
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []


# Singleton instance
kalshi_client = KalshiClient()
