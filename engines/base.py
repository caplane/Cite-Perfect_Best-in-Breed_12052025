"""
citeflex/engines/base.py

Abstract base class for all search engines.
Each engine must implement the search() method.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional, List
import requests

from models import CitationMetadata, CitationType
from config import DEFAULT_HEADERS, DEFAULT_TIMEOUT


class SearchEngine(ABC):
    """
    Abstract base class for search engines.
    
    All engines must implement:
    - search(query) -> CitationMetadata or None
    
    Engines may optionally implement:
    - search_multiple(query, limit) -> List[CitationMetadata]
    - get_by_id(id) -> CitationMetadata (for DOI, PMID, ISBN lookup)
    """
    
    # Override in subclasses
    name: str = "Base Engine"
    base_url: str = ""
    
    # Rate limit retry settings
    MAX_RETRIES = 2
    RETRY_DELAY_BASE = 2  # Base delay in seconds for exponential backoff
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT):
        self.api_key = api_key
        self.timeout = timeout
        self._session = None
    
    @property
    def session(self) -> requests.Session:
        """Lazy-loaded requests session with default headers."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(DEFAULT_HEADERS)
        return self._session
    
    @abstractmethod
    def search(self, query: str) -> Optional[CitationMetadata]:
        """
        Search for a single best-match result.
        
        Args:
            query: Search query string
            
        Returns:
            CitationMetadata if found, None otherwise
        """
        pass
    
    def search_multiple(self, query: str, limit: int = 5) -> List[CitationMetadata]:
        """
        Search for multiple results. Override for engines that support it.
        Default implementation just returns single result in a list.
        
        Args:
            query: Search query string
            limit: Maximum results to return
            
        Returns:
            List of CitationMetadata (may be empty)
        """
        result = self.search(query)
        return [result] if result else []
    
    def get_by_id(self, identifier: str) -> Optional[CitationMetadata]:
        """
        Fetch by direct identifier (DOI, PMID, ISBN, etc.).
        Override in engines that support direct lookup.
        
        Args:
            identifier: The identifier to look up
            
        Returns:
            CitationMetadata if found, None otherwise
        """
        return None
    
    def _make_request(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        method: str = "GET",
        retry_count: int = 0
    ) -> Optional[requests.Response]:
        """
        Make an HTTP request with error handling and rate limit retry.
        
        Implements exponential backoff for 429 (Too Many Requests) responses.
        
        Returns:
            Response object if successful, None on error
        """
        try:
            merged_headers = dict(DEFAULT_HEADERS)
            if headers:
                merged_headers.update(headers)
            
            if method.upper() == "GET":
                response = self.session.get(
                    url,
                    params=params,
                    headers=merged_headers,
                    timeout=self.timeout
                )
            else:
                response = self.session.post(
                    url,
                    json=params,
                    headers=merged_headers,
                    timeout=self.timeout
                )
            
            # Handle rate limiting with exponential backoff
            if response.status_code == 429:
                if retry_count < self.MAX_RETRIES:
                    # Get retry delay from header or use exponential backoff
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            delay = int(retry_after)
                        except ValueError:
                            delay = self.RETRY_DELAY_BASE * (2 ** retry_count)
                    else:
                        delay = self.RETRY_DELAY_BASE * (2 ** retry_count)
                    
                    print(f"[{self.name}] Rate limited. Retrying in {delay}s (attempt {retry_count + 1}/{self.MAX_RETRIES})...")
                    time.sleep(delay)
                    return self._make_request(url, params, headers, method, retry_count + 1)
                else:
                    print(f"[{self.name}] Rate limit exceeded after {self.MAX_RETRIES} retries")
                    return None
            
            response.raise_for_status()
            return response
            
        except requests.Timeout:
            print(f"[{self.name}] Request timeout after {self.timeout}s")
            return None
        except requests.RequestException as e:
            print(f"[{self.name}] Request error: {e}")
            return None
    
    def _create_metadata(
        self,
        citation_type: CitationType,
        raw_source: str = "",
        **kwargs
    ) -> CitationMetadata:
        """
        Helper to create CitationMetadata with common fields pre-filled.
        """
        return CitationMetadata(
            citation_type=citation_type,
            raw_source=raw_source,
            source_engine=self.name,
            **kwargs
        )


class MultiAttemptEngine(SearchEngine):
    """
    Base class for engines that try multiple search strategies.
    Subclasses define the attempts, this class orchestrates them.
    """
    
    @abstractmethod
    def get_search_attempts(self, query: str) -> List[dict]:
        """
        Return a list of search attempt configurations.
        Each dict should have at least 'name' and 'params' keys.
        
        Example:
        [
            {'name': 'phrase', 'params': {'q': f'"{query}"'}},
            {'name': 'keyword', 'params': {'q': query}},
            {'name': 'fuzzy', 'params': {'q': f'{query}~'}},
        ]
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: requests.Response, query: str) -> Optional[CitationMetadata]:
        """Parse a successful response into CitationMetadata."""
        pass
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        """Execute search attempts in order until one succeeds."""
        attempts = self.get_search_attempts(query)
        
        for i, attempt in enumerate(attempts, 1):
            name = attempt.get('name', f'attempt_{i}')
            params = attempt.get('params', {})
            url = attempt.get('url', self.base_url)
            
            print(f"[{self.name}] Attempt {i}: {name}...")
            
            response = self._make_request(url, params=params)
            if response:
                result = self.parse_response(response, query)
                if result and result.has_minimum_data():
                    print(f"[{self.name}] Found via {name}")
                    return result
        
        print(f"[{self.name}] No results after {len(attempts)} attempts")
        return None
