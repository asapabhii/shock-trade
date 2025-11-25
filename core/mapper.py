"""
Market Mapper - Maps football matches to exchange markets.

Handles team name normalization and fuzzy matching to find
corresponding prediction markets for live football matches.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from difflib import SequenceMatcher
from loguru import logger

from core.models import Match, Market, MatchMarketMapping
from exchanges.kalshi_client import kalshi_client


class MarketMapper:
    """
    Maps football matches to prediction market contracts.
    
    Uses fuzzy string matching to handle variations in team names
    between different data sources.
    """
    
    # Common team name variations and aliases
    TEAM_ALIASES: Dict[str, List[str]] = {
        "manchester united": ["man utd", "man united", "mufc"],
        "manchester city": ["man city", "mcfc"],
        "tottenham hotspur": ["tottenham", "spurs"],
        "wolverhampton wanderers": ["wolves", "wolverhampton"],
        "west ham united": ["west ham"],
        "newcastle united": ["newcastle"],
        "nottingham forest": ["nott'm forest", "nottm forest"],
        "brighton & hove albion": ["brighton"],
        "crystal palace": ["palace"],
        "leicester city": ["leicester"],
        "aston villa": ["villa"],
        "real madrid": ["real madrid cf"],
        "barcelona": ["fc barcelona", "barca"],
        "atletico madrid": ["atletico", "atleti"],
        "bayern munich": ["bayern", "fc bayern"],
        "borussia dortmund": ["dortmund", "bvb"],
        "paris saint-germain": ["psg", "paris sg"],
        "inter milan": ["inter", "internazionale"],
        "ac milan": ["milan"],
        "juventus": ["juve"],
    }
    
    def __init__(self):
        self._market_cache: Dict[str, List[Market]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)
    
    def _normalize_team_name(self, name: str) -> str:
        """
        Normalize team name for matching.
        
        Removes common suffixes, converts to lowercase, strips whitespace.
        """
        normalized = name.lower().strip()
        
        # Remove common suffixes
        suffixes = [" fc", " cf", " sc", " afc", " united", " city"]
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
        
        return normalized.strip()
    
    def _get_team_aliases(self, team_name: str) -> List[str]:
        """Get all known aliases for a team name."""
        normalized = self._normalize_team_name(team_name)
        aliases = [normalized, team_name.lower()]
        
        # Check if this team has known aliases
        for canonical, alias_list in self.TEAM_ALIASES.items():
            if normalized == canonical or normalized in alias_list:
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
        """Refresh the market cache from exchanges."""
        logger.info("Refreshing market cache from Kalshi...")
        
        try:
            markets = await kalshi_client.get_markets(limit=200)
            
            # Index markets by keywords for faster lookup
            self._market_cache = {"all": markets}
            self._cache_timestamp = datetime.utcnow()
            
            logger.info(f"Cached {len(markets)} markets from Kalshi")
            
        except Exception as e:
            logger.error(f"Error refreshing market cache: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._cache_timestamp:
            return False
        return datetime.utcnow() - self._cache_timestamp < self._cache_ttl
    
    async def find_markets_for_match(
        self,
        match: Match,
        min_confidence: float = 0.7
    ) -> List[Market]:
        """
        Find prediction markets that correspond to a football match.
        
        Args:
            match: The football match to find markets for.
            min_confidence: Minimum confidence threshold for matching.
            
        Returns:
            List of matching Market objects.
        """
        # Refresh cache if needed
        if not self._is_cache_valid():
            await self.refresh_market_cache()
        
        all_markets = self._market_cache.get("all", [])
        matching_markets = []
        
        home_name = match.home_team.name
        away_name = match.away_team.name
        
        for market in all_markets:
            # Check if both teams appear in market title/subtitle
            search_text = f"{market.title} {market.subtitle or ''}"
            
            home_score = self._match_team_in_text(home_name, search_text)
            away_score = self._match_team_in_text(away_name, search_text)
            
            # Both teams should be mentioned for a match market
            if home_score >= min_confidence and away_score >= min_confidence:
                matching_markets.append(market)
                logger.debug(
                    f"Matched market '{market.title}' for {match.display_name} "
                    f"(confidence: home={home_score:.2f}, away={away_score:.2f})"
                )
            # Or check for league + one team (for winner markets)
            elif home_score >= min_confidence or away_score >= min_confidence:
                # Check if league name is mentioned
                if match.league_name.lower() in search_text.lower():
                    matching_markets.append(market)
        
        return matching_markets
    
    async def create_mapping(self, match: Match) -> MatchMarketMapping:
        """
        Create a complete mapping for a match including pre-goal probabilities.
        
        Args:
            match: The football match.
            
        Returns:
            MatchMarketMapping with markets and probabilities.
        """
        markets = await self.find_markets_for_match(match)
        
        # Extract pre-goal probabilities from market prices
        home_prob = None
        away_prob = None
        
        for market in markets:
            title_lower = market.title.lower()
            
            # Try to identify home/away win markets
            if "win" in title_lower or "winner" in title_lower:
                home_aliases = self._get_team_aliases(match.home_team.name)
                away_aliases = self._get_team_aliases(match.away_team.name)
                
                for alias in home_aliases:
                    if alias in title_lower:
                        home_prob = market.yes_price
                        break
                
                for alias in away_aliases:
                    if alias in title_lower:
                        away_prob = market.yes_price
                        break
        
        return MatchMarketMapping(
            match_id=match.id,
            home_team_name=match.home_team.name,
            away_team_name=match.away_team.name,
            league_name=match.league_name,
            kickoff=match.kickoff,
            markets=markets,
            pre_goal_home_prob=home_prob,
            pre_goal_away_prob=away_prob,
            last_updated=datetime.utcnow()
        )


# Singleton instance
market_mapper = MarketMapper()
