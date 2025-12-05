"""
citeflex/engines/academic.py

Academic database search engines.
- CrossrefEngine: Official DOI registry
- OpenAlexEngine: Broad academic coverage
- SemanticScholarEngine: AI-powered with author matching
- PubMedEngine: Biomedical literature
"""

import re
import difflib
from typing import Optional, List

from engines.base import SearchEngine
from models import CitationMetadata, CitationType
from config import PUBMED_API_KEY, SEMANTIC_SCHOLAR_API_KEY


class CrossrefEngine(SearchEngine):
    """
    Search Crossref - the official DOI registry.
    
    Excellent for:
    - Journal articles with DOIs
    - Recent publications
    - Accurate metadata
    """
    
    name = "Crossref"
    base_url = "https://api.crossref.org/works"
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        params = {
            'query.bibliographic': query,
            'rows': 1
        }
        
        response = self._make_request(self.base_url, params=params)
        if not response:
            return None
        
        try:
            data = response.json()
            items = data.get('message', {}).get('items', [])
            if not items:
                return None
            return self._normalize(items[0], query)
        except Exception as e:
            print(f"[{self.name}] Parse error: {e}")
            return None
    
    def search_multiple(self, query: str, limit: int = 5) -> List[CitationMetadata]:
        params = {
            'query.bibliographic': query,
            'rows': limit
        }
        
        response = self._make_request(self.base_url, params=params)
        if not response:
            return []
        
        try:
            data = response.json()
            items = data.get('message', {}).get('items', [])
            return [self._normalize(item, query) for item in items[:limit]]
        except:
            return []
    
    def get_by_id(self, doi: str) -> Optional[CitationMetadata]:
        """Look up by DOI directly."""
        # Clean DOI
        doi = doi.replace('https://doi.org/', '').replace('http://dx.doi.org/', '')
        url = f"{self.base_url}/{doi}"
        
        response = self._make_request(url)
        if not response:
            return None
        
        try:
            data = response.json()
            item = data.get('message', {})
            if item:
                return self._normalize(item, doi)
        except:
            pass
        return None
    
    def _normalize(self, item: dict, raw_source: str) -> CitationMetadata:
        """Convert Crossref response to CitationMetadata."""
        # Extract authors
        authors = []
        for author in item.get('author', []):
            given = author.get('given', '')
            family = author.get('family', '')
            if given and family:
                authors.append(f"{given} {family}")
            elif family:
                authors.append(family)
        
        # Extract year
        year = None
        for date_field in ['published-print', 'published-online', 'created']:
            if item.get(date_field, {}).get('date-parts'):
                parts = item[date_field]['date-parts'][0]
                if parts:
                    year = str(parts[0])
                    break
        
        # Get container (journal) title
        journal = ''
        container = item.get('container-title', [])
        if container:
            journal = container[0] if isinstance(container, list) else container
        
        # Determine type
        item_type = item.get('type', '')
        if item_type in ['book', 'monograph', 'edited-book']:
            citation_type = CitationType.BOOK
        elif item_type in ['book-chapter', 'book-section']:
            citation_type = CitationType.BOOK
        else:
            citation_type = CitationType.JOURNAL
        
        # Get title
        title_list = item.get('title', [])
        title = title_list[0] if title_list else ''
        
        return self._create_metadata(
            citation_type=citation_type,
            raw_source=raw_source,
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            volume=item.get('volume', ''),
            issue=item.get('issue', ''),
            pages=item.get('page', ''),
            doi=item.get('DOI', ''),
            url=f"https://doi.org/{item.get('DOI')}" if item.get('DOI') else '',
            publisher=item.get('publisher', ''),
            raw_data=item
        )


class OpenAlexEngine(SearchEngine):
    """
    Search OpenAlex - broad academic coverage.
    
    Excellent for:
    - Older publications
    - Open access content
    - Citation networks
    """
    
    name = "OpenAlex"
    base_url = "https://api.openalex.org/works"
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        params = {
            'search': query,
            'per-page': 1
        }
        
        response = self._make_request(self.base_url, params=params)
        if not response:
            return None
        
        try:
            data = response.json()
            results = data.get('results', [])
            if not results:
                return None
            return self._normalize(results[0], query)
        except Exception as e:
            print(f"[{self.name}] Parse error: {e}")
            return None
    
    def search_multiple(self, query: str, limit: int = 5) -> List[CitationMetadata]:
        params = {
            'search': query,
            'per-page': limit
        }
        
        response = self._make_request(self.base_url, params=params)
        if not response:
            return []
        
        try:
            data = response.json()
            results = data.get('results', [])
            return [self._normalize(r, query) for r in results[:limit]]
        except:
            return []
    
    def _normalize(self, item: dict, raw_source: str) -> CitationMetadata:
        """Convert OpenAlex response to CitationMetadata."""
        # Extract authors
        authors = []
        for authorship in item.get('authorships', []):
            author_info = authorship.get('author', {})
            name = author_info.get('display_name')
            if name:
                authors.append(name)
        
        # Get journal from primary location
        journal = ''
        location = item.get('primary_location', {}) or {}
        source = location.get('source', {}) or {}
        if source.get('display_name'):
            journal = source['display_name']
        
        # Get bibliographic info
        biblio = item.get('biblio', {}) or {}
        
        # Extract DOI
        doi = item.get('doi', '')
        if doi and doi.startswith('https://doi.org/'):
            doi = doi.replace('https://doi.org/', '')
        
        # Get URL
        url = item.get('doi', '') or item.get('id', '')
        
        return self._create_metadata(
            citation_type=CitationType.JOURNAL,
            raw_source=raw_source,
            title=item.get('display_name', item.get('title', '')),
            authors=authors,
            year=str(item.get('publication_year', '')) if item.get('publication_year') else None,
            journal=journal,
            volume=biblio.get('volume', ''),
            issue=biblio.get('issue', ''),
            pages=f"{biblio.get('first_page', '')}-{biblio.get('last_page', '')}" if biblio.get('first_page') else '',
            doi=doi,
            url=url,
            raw_data=item
        )


class SemanticScholarEngine(SearchEngine):
    """
    Search Semantic Scholar - AI-powered with author matching.
    
    Features:
    - Author-aware result ranking
    - Good for finding papers by "Author Title" queries
    """
    
    name = "Semantic Scholar"
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    details_url = "https://api.semanticscholar.org/graph/v1/paper/"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(api_key=api_key or SEMANTIC_SCHOLAR_API_KEY, **kwargs)
    
    def _get_headers(self) -> dict:
        """Get headers with API key if available."""
        headers = {}
        if self.api_key:
            headers['x-api-key'] = self.api_key
        return headers
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        """
        Search with author-aware matching.
        Gets top 5 results, scores by author/title match, returns best.
        """
        headers = self._get_headers()
        params = {
            'query': query,
            'limit': 5,
            'fields': 'paperId,title,authors'
        }
        
        response = self._make_request(self.base_url, params=params, headers=headers)
        if not response:
            return None
        
        try:
            data = response.json()
            if data.get('total', 0) == 0:
                return None
            
            papers = data.get('data', [])
            if not papers:
                return None
            
            # Score each paper for relevance
            best_match = self._find_best_match(papers, query)
            
            # Get full details
            return self._fetch_details(best_match['paperId'], query, headers)
            
        except Exception as e:
            print(f"[{self.name}] Parse error: {e}")
            return None
    
    def _find_best_match(self, papers: List[dict], query: str) -> dict:
        """Score papers and return best match."""
        query_lower = query.lower()
        best_match = papers[0]
        best_score = 0
        
        for paper in papers:
            score = 0
            authors = paper.get('authors', [])
            title = paper.get('title', '').lower()
            
            # Check if author names appear in query
            for author in authors:
                name = author.get('name', '').lower()
                parts = name.split()
                if parts:
                    last_name = parts[-1]
                    first_name = parts[0] if len(parts) > 1 else ''
                    
                    if last_name and len(last_name) > 2 and last_name in query_lower:
                        score += 10
                    if first_name and len(first_name) > 2 and first_name in query_lower:
                        score += 5
            
            # Check title word overlap
            query_words = set(query_lower.split()) - {'the', 'a', 'an', 'of', 'and', 'in', 'on', 'for', 'to'}
            title_words = set(title.split()) - {'the', 'a', 'an', 'of', 'and', 'in', 'on', 'for', 'to'}
            overlap = len(query_words & title_words)
            score += overlap * 2
            
            if score > best_score:
                best_score = score
                best_match = paper
        
        return best_match
    
    def _fetch_details(self, paper_id: str, raw_source: str, headers: dict) -> Optional[CitationMetadata]:
        """Fetch full paper details by ID."""
        params = {
            'fields': 'title,authors,venue,publicationVenue,year,volume,issue,pages,externalIds,url'
        }
        
        url = f"{self.details_url}{paper_id}"
        response = self._make_request(url, params=params, headers=headers)
        if not response:
            return None
        
        try:
            item = response.json()
            return self._normalize(item, raw_source)
        except:
            return None
    
    def _normalize(self, item: dict, raw_source: str) -> CitationMetadata:
        """Convert Semantic Scholar response to CitationMetadata."""
        # Extract authors
        authors = [a.get('name', '') for a in item.get('authors', []) if a.get('name')]
        
        # Get journal/venue
        venue = item.get('venue', '')
        pub_venue = item.get('publicationVenue', {}) or {}
        if pub_venue.get('name'):
            venue = pub_venue['name']
        
        # Get DOI from external IDs
        external_ids = item.get('externalIds', {}) or {}
        doi = external_ids.get('DOI', '')
        
        url = item.get('url', '')
        if not url and doi:
            url = f"https://doi.org/{doi}"
        
        return self._create_metadata(
            citation_type=CitationType.JOURNAL,
            raw_source=raw_source,
            title=item.get('title', ''),
            authors=authors,
            year=str(item.get('year', '')) if item.get('year') else None,
            journal=venue,
            volume=str(item.get('volume', '')) if item.get('volume') else '',
            issue=str(item.get('issue', '')) if item.get('issue') else '',
            pages=item.get('pages', ''),
            doi=doi,
            url=url,
            raw_data=item
        )


class PubMedEngine(SearchEngine):
    """
    Search PubMed / NCBI - biomedical literature.
    
    Excellent for:
    - Medical/clinical articles
    - PMID lookups
    - Life sciences
    """
    
    name = "PubMed"
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(api_key=api_key or PUBMED_API_KEY, **kwargs)
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        """Search PubMed using ESearch + ESummary."""
        pmid = self._search_for_pmid(query)
        if not pmid:
            return None
        return self._fetch_details(pmid, query)
    
    def get_by_id(self, pmid: str) -> Optional[CitationMetadata]:
        """Look up by PMID directly."""
        # Clean PMID
        pmid = re.sub(r'\D', '', pmid)
        return self._fetch_details(pmid, f"PMID:{pmid}")
    
    def _search_for_pmid(self, query: str) -> Optional[str]:
        """Search for PMID using ESearch."""
        # Try phrase search first
        for search_query in [f'"{query}"', query]:
            params = {
                'db': 'pubmed',
                'term': search_query,
                'retmode': 'json',
                'retmax': 1
            }
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self._make_request(f"{self.base_url}esearch.fcgi", params=params)
            if response:
                try:
                    data = response.json()
                    id_list = data.get('esearchresult', {}).get('idlist', [])
                    if id_list:
                        return id_list[0]
                except:
                    pass
        
        return None
    
    def _fetch_details(self, pmid: str, raw_source: str) -> Optional[CitationMetadata]:
        """Fetch article details using ESummary."""
        params = {
            'db': 'pubmed',
            'id': pmid,
            'retmode': 'json'
        }
        if self.api_key:
            params['api_key'] = self.api_key
        
        response = self._make_request(f"{self.base_url}esummary.fcgi", params=params)
        if not response:
            return None
        
        try:
            data = response.json()
            article = data.get('result', {}).get(pmid, {})
            if not article or 'error' in article:
                return None
            return self._normalize(article, raw_source, pmid)
        except:
            return None
    
    def _normalize(self, item: dict, raw_source: str, pmid: str) -> CitationMetadata:
        """Convert PubMed response to CitationMetadata."""
        # Extract authors
        authors = [a.get('name', '') for a in item.get('authors', []) if a.get('name')]
        
        # Extract year from pubdate
        year = None
        pubdate = item.get('pubdate', '')
        if pubdate:
            year_match = re.match(r'(\d{4})', pubdate)
            if year_match:
                year = year_match.group(1)
        
        # Extract DOI from article IDs
        doi = ''
        for article_id in item.get('articleids', []):
            if article_id.get('idtype') == 'doi':
                doi = article_id.get('value', '')
                break
        
        return self._create_metadata(
            citation_type=CitationType.MEDICAL,
            raw_source=raw_source,
            title=item.get('title', ''),
            authors=authors,
            year=year,
            journal=item.get('fulljournalname', item.get('source', '')),
            volume=item.get('volume', ''),
            issue=item.get('issue', ''),
            pages=item.get('pages', ''),
            doi=doi,
            pmid=pmid,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            raw_data=item
        )
