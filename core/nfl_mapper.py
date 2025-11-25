"""
NFL Market Mapper - Maps NFL games to Kalshi markets.

Handles team name normalization and fuzzy matching to find
corresponding prediction markets for live NFL games.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from difflib import SequenceMatcher
from loguru import logger

from core.models import NFLGame, Market, NFLGameMarketMapping
from exchanges.kalshi_client import kalshi_client


class NFLMarketMapper:
    """
    Maps NFL games to Kalshi prediction market contracts.
    
    Uses fuzzy string matching to handle variations in team names.
    """
    
    # NFL team name variations and common aliases
    TEAM_ALIASES: Dict[str, List[str]] = {
        "arizona cardinals": ["cardinals", "ari", "arizona"],
        "atlanta falcons": ["falcons", "atl", "atlanta"],
        "baltimore ravens": ["ravens", "bal", "baltimore"],
        "buffalo bills": ["bills", "buf", "buffalo"],
        "carolina panthers": ["panthers", "car", "carolina"],
        "chicago bears": ["bears", "chi", "chicago"],
        "cincinnati bengals": ["bengals", "cin", "cincinnati"],
        "cleveland browns": ["browns", "cle", "cleveland"],
        "dallas cowboys": ["cowboys", "dal", "dallas"],
        "denver broncos": ["broncos", "den", "denver"],
        "detroit lions": ["lions", "det", "detroit"],
        "green bay packers": ["packers", "gb", "green bay"],
        "houston texans": ["texans", "hou", "houston"],
        "indianapolis colts": ["colts", "ind", "indianapolis"],
        "jacksonville jaguars": ["jaguars", "jax", "jacksonville", "jags"],
        "kansas city chiefs": ["chiefs", "kc", "kansas city"],
        "las vegas raiders": ["raiders", "lv", "las vegas", "oakland"],
        "los angeles chargers": ["chargers", "lac", "la chargers"],
        "los angeles rams": ["rams", "lar", "la rams"],
        "miami dolphins": ["dolphins", "mia", "miami"],
        "minnesota vikings": ["vikings", "min", "minnesota"],
        "new england patriots": ["patriots", "ne", "new england", "pats"],
        "new orleans saints": ["saints", "no", "new orleans"],
        "new york giants": ["giants", "nyg", "ny giants"],
        "new york jets": ["jets", "nyj", "ny jets"],
        "philadelphia eagles": ["eagles", "phi", "philadelphia", "philly"],
        "pittsburgh steelers": ["steelers", "pit", "pittsburgh"],
        "san francisco 49ers": ["49ers", "sf", "san francisco", "niners"],
        "seattle seahawks": ["seahawks", "sea", "seattle"],
        "tampa bay buccaneers": ["buccaneers", "tb", "tampa bay", "bucs"],
        "tennessee titans": ["titans", "ten", "tennessee"],
        "washington commanders": ["commanders", "was", "washington", "commies"],
    }
    
    def __init__(self):
        self._market_cache: Dict[str, List[Market]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)
    
    def _normalize_team_name(self, name: str) -> str:
        """Normalize team name for matching."""
        return name.lower().strip()
    
    def _get_team_aliases(self, team_name: str) -> List[str]:
        """Get all known aliases for a team name."""
        normalized = self._normalize_team_name(team_name)
        aliases = [normalized]
        
        # Check if this team has known aliases
        for canonical, alias_list in self.TEAM_ALIASES.items():
            # Match if normalized equals canonical or if canonical is contained in normalized
            if normalized == canonical or canonical in normalized or normalized in canonical:
                aliases.extend([canonical] + alias_list)
                break
            # Also check if any alias matches
            for alias in alias_list:
                if alias in normalized or normalized in alias:
                    aliases.extend([canonical] + alias_list)
                    break
        
        return list(set(aliases))
    
    def _similarity_score(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0-1)."""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def _match_team_in_text(self, team_name: str, text: str) -> float:
        """
        Check if team name appears in text, return confidence score.
        
        Returns:
            Confidence score 0-1, where 1 is exact match.
        """
        text_lower = text.lower()
        aliases = self._get_team_aliases(team_name)
        
        best_score = 0.0
        for alias in aliases:
            if alias in text_lower:
                # Direct substring match
                best_score = max(best_score, 0.9)
            else:
                # Fuzzy match
                score = self._similarity_score(alias, text_lower)
                best_score = max(best_score, score)
        
        return best_score
    
    async def refresh_market_cache(self) -> None:
        """Refresh the market cache from Kalshi."""
        logger.info("Refreshing NFL market cache from Kalshi...")
        
        try:
            # Get all markets and filter for NFL-related ones
            all_markets = await kalshi_client.get_markets(limit=200)
            
            # Filter for NFL/football markets
            nfl_keywords = ["nfl", "football", "touchdown", "super bowl"]
            nfl_keywords.extend([alias for aliases in self.TEAM_ALIASES.values() for alias in aliases])
            
            nfl_markets = []
            for market in all_markets:
                search_text = f"{market.title} {market.subtitle or ''}".lower()
                if any(kw in search_text for kw in nfl_keywords):
                    nfl_markets.append(market)
            
            self._market_cache = {"all": all_markets, "nfl": nfl_markets}
            self._cache_timestamp = datetime.utcnow()
            
            logger.info(f"Cached {len(nfl_markets)} NFL markets from Kalshi (total: {len(all_markets)})")
            
        except Exception as e:
            logger.error(f"Error refreshing market cache: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._cache_timestamp:
            return False
        return datetime.utcnow() - self._cache_timestamp < self._cache_ttl

    async def find_markets_for_game(
        self,
        game: NFLGame,
        min_confidence: float = 0.6
    ) -> List[Market]:
        """
        Find prediction markets that correspond to an NFL game.
        
        Args:
            game: The NFL game to find markets for.
            min_confidence: Minimum confidence threshold for matching.
            
        Returns:
            List of matching Market objects.
        """
        # Refresh cache if needed
        if not self._is_cache_valid():
            await self.refresh_market_cache()
        
        all_markets = self._market_cache.get("all", [])
        matching_markets = []
        
        home_name = game.home_team.name
        away_name = game.away_team.name
        
        for market in all_markets:
            search_text = f"{market.title} {market.subtitle or ''}"
            
            home_score = self._match_team_in_text(home_name, search_text)
            away_score = self._match_team_in_text(away_name, search_text)
            
            # Both teams should be mentioned for a game market
            if home_score >= min_confidence and away_score >= min_confidence:
                matching_markets.append(market)
                logger.debug(
                    f"Matched market '{market.title}' for {game.display_name} "
                    f"(confidence: home={home_score:.2f}, away={away_score:.2f})"
                )
            # Or check for single team win markets
            elif home_score >= min_confidence or away_score >= min_confidence:
                # Check if it's an NFL market
                if "nfl" in search_text.lower() or "football" in search_text.lower():
                    matching_markets.append(market)
        
        return matching_markets
    
    async def create_mapping(self, game: NFLGame) -> NFLGameMarketMapping:
        """
        Create a complete mapping for a game including pre-score probabilities.
        
        Args:
            game: The NFL game.
            
        Returns:
            NFLGameMarketMapping with markets and probabilities.
        """
        markets = await self.find_markets_for_game(game)
        
        # Extract pre-score probabilities from market prices
        home_prob = None
        away_prob = None
        
        for market in markets:
            title_lower = market.title.lower()
            
            # Try to identify home/away win markets
            if "win" in title_lower or "winner" in title_lower or "moneyline" in title_lower:
                home_aliases = self._get_team_aliases(game.home_team.name)
                away_aliases = self._get_team_aliases(game.away_team.name)
                
                for alias in home_aliases:
                    if alias in title_lower:
                        home_prob = market.yes_price
                        break
                
                for alias in away_aliases:
                    if alias in title_lower:
                        away_prob = market.yes_price
                        break
        
        return NFLGameMarketMapping(
            game_id=game.id,
            home_team_name=game.home_team.name,
            away_team_name=game.away_team.name,
            kickoff=game.kickoff,
            markets=markets,
            pre_score_home_prob=home_prob,
            pre_score_away_prob=away_prob,
            spread=game.spread,
            over_under=game.over_under,
            last_updated=datetime.utcnow()
        )
    
    async def search_nfl_markets(self, search_term: str = "") -> List[Market]:
        """
        Search for NFL-related markets.
        
        Args:
            search_term: Optional additional search term.
            
        Returns:
            List of matching markets.
        """
        if not self._is_cache_valid():
            await self.refresh_market_cache()
        
        nfl_markets = self._market_cache.get("nfl", [])
        
        if not search_term:
            return nfl_markets
        
        search_lower = search_term.lower()
        return [
            m for m in nfl_markets
            if search_lower in m.title.lower() or 
               (m.subtitle and search_lower in m.subtitle.lower())
        ]


# Singleton instance
nfl_market_mapper = NFLMarketMapper()
