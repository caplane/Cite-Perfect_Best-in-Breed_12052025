"""
citeflex/engines/google_cse.py

Google Custom Search and book lookup engines.
"""

import re
from typing import Optional, List
from urllib.parse import urlparse

from engines.base import SearchEngine
from models import CitationMetadata, CitationType
from config import GOOGLE_CSE_API_KEY, GOOGLE_CSE_ID, ACADEMIC_DOMAINS


class GoogleCSEEngine(SearchEngine):
    """Google Custom Search for academic sources."""
    
    name = "Google CSE"
    base_url = "https://www.googleapis.com/customsearch/v1"
    
    def __init__(self, api_key: Optional[str] = None, cse_id: Optional[str] = None, **kwargs):
        super().__init__(api_key=api_key or GOOGLE_CSE_API_KEY, **kwargs)
        self.cse_id = cse_id or GOOGLE_CSE_ID
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        if not self.api_key or not self.cse_id:
            return None
        
        params = {
            'key': self.api_key,
            'cx': self.cse_id,
            'q': query,
            'num': 5
        }
        
        response = self._make_request(self.base_url, params=params)
        if not response:
            return None
        
        try:
            data = response.json()
            items = data.get('items', [])
            
            for item in items:
                link = item.get('link', '')
                domain = urlparse(link).netloc.lower()
                
                if any(ad in domain for ad in ACADEMIC_DOMAINS):
                    return self._normalize(item, query)
            
            if items:
                return self._normalize(items[0], query)
            
            return None
        except:
            return None
    
    def _normalize(self, item: dict, raw_source: str) -> CitationMetadata:
        return CitationMetadata(
            citation_type=CitationType.JOURNAL,
            raw_source=raw_source,
            source_engine=self.name,
            title=item.get('title', ''),
            url=item.get('link', ''),
            raw_data=item
        )


class GoogleBooksEngine(SearchEngine):
    """Google Books API for book lookups."""
    
    name = "Google Books"
    base_url = "https://www.googleapis.com/books/v1/volumes"
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        params = {'q': query, 'maxResults': 1}
        
        response = self._make_request(self.base_url, params=params)
        if not response:
            return None
        
        try:
            data = response.json()
            items = data.get('items', [])
            if not items:
                return None
            return self._normalize(items[0], query)
        except:
            return None
    
    def get_by_id(self, isbn: str) -> Optional[CitationMetadata]:
        isbn = re.sub(r'[\s-]', '', isbn)
        params = {'q': f'isbn:{isbn}', 'maxResults': 1}
        
        response = self._make_request(self.base_url, params=params)
        if not response:
            return None
        
        try:
            data = response.json()
            items = data.get('items', [])
            if items:
                return self._normalize(items[0], isbn)
        except:
            pass
        return None
    
    def _normalize(self, item: dict, raw_source: str) -> CitationMetadata:
        info = item.get('volumeInfo', {})
        
        identifiers = info.get('industryIdentifiers', [])
        isbn = ''
        for ident in identifiers:
            if ident.get('type') in ['ISBN_13', 'ISBN_10']:
                isbn = ident.get('identifier', '')
                break
        
        year = None
        pub_date = info.get('publishedDate', '')
        if pub_date:
            year_match = re.match(r'(\d{4})', pub_date)
            if year_match:
                year = year_match.group(1)
        
        return CitationMetadata(
            citation_type=CitationType.BOOK,
            raw_source=raw_source,
            source_engine=self.name,
            title=info.get('title', ''),
            authors=info.get('authors', []),
            year=year,
            publisher=info.get('publisher', ''),
            isbn=isbn,
            url=info.get('infoLink', ''),
            raw_data=item
        )


class OpenLibraryEngine(SearchEngine):
    """Open Library API for book lookups."""
    
    name = "Open Library"
    base_url = "https://openlibrary.org/search.json"
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        params = {'q': query, 'limit': 1}
        
        response = self._make_request(self.base_url, params=params)
        if not response:
            return None
        
        try:
            data = response.json()
            docs = data.get('docs', [])
            if not docs:
                return None
            return self._normalize(docs[0], query)
        except:
            return None
    
    def _normalize(self, item: dict, raw_source: str) -> CitationMetadata:
        year = None
        if item.get('first_publish_year'):
            year = str(item['first_publish_year'])
        
        isbn = ''
        isbns = item.get('isbn', [])
        if isbns:
            isbn = isbns[0]
        
        publishers = item.get('publisher', [])
        publisher = publishers[0] if publishers else ''
        
        return CitationMetadata(
            citation_type=CitationType.BOOK,
            raw_source=raw_source,
            source_engine=self.name,
            title=item.get('title', ''),
            authors=item.get('author_name', []),
            year=year,
            publisher=publisher,
            isbn=isbn,
            raw_data=item
        )
