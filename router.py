"""
citeflex/router.py

Main routing logic for the citation system.
Orchestrates detection, engine selection, and formatting.

FIX APPLIED: Engines now run in parallel using ThreadPoolExecutor
instead of sequential execution, reducing worst-case latency from
40+ seconds to ~10 seconds.
"""

import re
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

from models import CitationMetadata, CitationType, CitationStyle
from detectors import detect_type, DetectionResult
from extractors import extract_by_type
from engines.academic import CrossrefEngine, OpenAlexEngine, SemanticScholarEngine, PubMedEngine
from engines.legal import LegalSearchEngine
from engines.google_cse import GoogleBooksEngine, OpenLibraryEngine
from engines.doi import extract_doi_from_url, is_academic_publisher_url, fetch_crossref_by_doi
from formatters.base import get_formatter


# =============================================================================
# CONFIGURATION
# =============================================================================

# Overall timeout for parallel engine execution (seconds)
PARALLEL_TIMEOUT = 12

# Maximum workers for parallel execution
MAX_WORKERS = 4


# =============================================================================
# ENGINE INSTANCES (reused across requests)
# =============================================================================

_crossref = CrossrefEngine()
_openalex = OpenAlexEngine()
_semantic = SemanticScholarEngine()
_pubmed = PubMedEngine()
_legal = LegalSearchEngine()
_google_books = GoogleBooksEngine()
_open_library = OpenLibraryEngine()


# =============================================================================
# PARALLEL ENGINE EXECUTION
# =============================================================================

def _search_engines_parallel(
    engines: List[Tuple[str, callable]],
    query: str,
    timeout: float = PARALLEL_TIMEOUT
) -> Optional[CitationMetadata]:
    """
    Execute multiple search engines in parallel, return first valid result.
    
    This is the KEY FIX for the sequential timeout issue. Instead of
    running engines one after another (which could take 40+ seconds),
    we run them in parallel and return as soon as any engine succeeds.
    
    Args:
        engines: List of (name, search_function) tuples
        query: Search query
        timeout: Overall timeout for all engines
        
    Returns:
        First valid CitationMetadata found, or None
    """
    if not engines:
        return None
    
    results = []
    
    with ThreadPoolExecutor(max_workers=min(len(engines), MAX_WORKERS)) as executor:
        # Submit all searches
        future_to_engine = {
            executor.submit(fn, query): name
            for name, fn in engines
        }
        
        try:
            # Process results as they complete
            for future in as_completed(future_to_engine, timeout=timeout):
                engine_name = future_to_engine[future]
                try:
                    result = future.result(timeout=1)  # Quick timeout for individual result
                    if result and result.has_minimum_data():
                        print(f"[Router] Found result via {engine_name}")
                        return result
                except Exception as e:
                    print(f"[Router] {engine_name} failed: {e}")
                    continue
        
        except FuturesTimeout:
            print(f"[Router] Parallel search timed out after {timeout}s")
    
    return None


# =============================================================================
# TYPE-SPECIFIC ROUTING
# =============================================================================

def _route_journal(query: str) -> Optional[CitationMetadata]:
    """
    Route journal/article queries to academic engines.
    Runs Crossref, OpenAlex, and Semantic Scholar in parallel.
    """
    # Check for DOI in query first (instant lookup)
    doi_match = re.search(r'(10\.\d{4,}/[^\s]+)', query)
    if doi_match:
        doi = doi_match.group(1).rstrip('.,;')
        result = _crossref.get_by_id(doi)
        if result:
            print("[Router] Found via direct DOI lookup")
            return result
    
    # Parallel search across academic engines
    engines = [
        ("Crossref", _crossref.search),
        ("OpenAlex", _openalex.search),
        ("Semantic Scholar", _semantic.search),
    ]
    
    return _search_engines_parallel(engines, query)


def _route_medical(query: str) -> Optional[CitationMetadata]:
    """
    Route medical/clinical queries.
    Tries PubMed first (specialized), then falls back to journal engines.
    """
    # Check for PMID
    pmid_match = re.search(r'(?:pmid:?\s*|pubmed:?\s*)(\d+)', query, re.IGNORECASE)
    if pmid_match:
        pmid = pmid_match.group(1)
        result = _pubmed.get_by_id(pmid)
        if result:
            print("[Router] Found via direct PMID lookup")
            return result
    
    # Parallel search: PubMed + academic engines
    engines = [
        ("PubMed", _pubmed.search),
        ("Crossref", _crossref.search),
        ("Semantic Scholar", _semantic.search),
    ]
    
    return _search_engines_parallel(engines, query)


def _route_book(query: str) -> Optional[CitationMetadata]:
    """
    Route book queries.
    Uses Google Books and Open Library in parallel.
    """
    # Check for ISBN
    isbn_match = re.search(r'(?:isbn:?\s*)?(\d{10}|\d{13}|\d{3}[-\s]?\d[-\s]?\d{3}[-\s]?\d{5}[-\s]?\d)', query, re.IGNORECASE)
    if isbn_match:
        isbn = re.sub(r'[-\s]', '', isbn_match.group(1))
        # Try both in parallel
        engines = [
            ("Google Books ISBN", lambda q: _google_books.get_by_id(isbn)),
            ("Open Library ISBN", lambda q: _open_library.get_by_id(isbn)),
        ]
        result = _search_engines_parallel(engines, query, timeout=5)
        if result:
            return result
    
    # Parallel book search
    engines = [
        ("Google Books", _google_books.search),
        ("Open Library", _open_library.search),
        ("Crossref Books", _crossref.search),  # Crossref has book chapters
    ]
    
    return _search_engines_parallel(engines, query)


def _route_legal(query: str) -> Optional[CitationMetadata]:
    """
    Route legal case queries.
    Uses the composite LegalSearchEngine (cache + CourtListener).
    """
    return _legal.search(query)


def _route_url(url: str) -> Optional[CitationMetadata]:
    """
    Route URL-based queries.
    Tries to extract DOI from academic URLs.
    """
    # Check if it's an academic publisher URL
    if is_academic_publisher_url(url):
        doi = extract_doi_from_url(url)
        if doi:
            result = fetch_crossref_by_doi(doi)
            if result:
                result.url = url
                print("[Router] Found via DOI extraction from URL")
                return result
    
    # Fall back to extractor for basic URL info
    return extract_by_type(url, CitationType.URL)


# =============================================================================
# MAIN ROUTING FUNCTION
# =============================================================================

def route_citation(query: str) -> Tuple[Optional[CitationMetadata], DetectionResult]:
    """
    Main routing function. Detects type and routes to appropriate engines.
    
    Args:
        query: The citation query (URL, title, etc.)
        
    Returns:
        Tuple of (CitationMetadata or None, DetectionResult)
    """
    # Step 1: Detect type
    detection = detect_type(query)
    print(f"[Router] Detected type: {detection.citation_type.name} (confidence: {detection.confidence})")
    
    metadata = None
    
    # Step 2: Route based on type
    if detection.citation_type == CitationType.INTERVIEW:
        metadata = extract_by_type(query, CitationType.INTERVIEW)
    
    elif detection.citation_type == CitationType.LEGAL:
        metadata = _route_legal(query)
    
    elif detection.citation_type == CitationType.GOVERNMENT:
        metadata = extract_by_type(query, CitationType.GOVERNMENT)
    
    elif detection.citation_type == CitationType.NEWSPAPER:
        metadata = extract_by_type(query, CitationType.NEWSPAPER)
    
    elif detection.citation_type == CitationType.MEDICAL:
        metadata = _route_medical(query)
    
    elif detection.citation_type == CitationType.JOURNAL:
        metadata = _route_journal(query)
    
    elif detection.citation_type == CitationType.BOOK:
        metadata = _route_book(query)
    
    elif detection.citation_type == CitationType.URL:
        metadata = _route_url(query)
    
    elif detection.citation_type == CitationType.UNKNOWN:
        # Try journal engines as default
        metadata = _route_journal(query)
        if not metadata:
            metadata = _route_book(query)
    
    return metadata, detection


# =============================================================================
# HIGH-LEVEL API
# =============================================================================

def get_citation(
    query: str,
    style: str = "Chicago Manual of Style"
) -> Tuple[Optional[CitationMetadata], Optional[str]]:
    """
    Main entry point for getting a formatted citation.
    
    Args:
        query: The citation query (URL, title, case name, etc.)
        style: Citation style name
        
    Returns:
        Tuple of (CitationMetadata, formatted_citation_string)
        Both may be None if lookup fails.
    """
    # Route to get metadata
    metadata, detection = route_citation(query)
    
    if not metadata or not metadata.has_minimum_data():
        print(f"[Router] No metadata found for: {query[:50]}...")
        return None, None
    
    # Format the citation
    formatter = get_formatter(style)
    formatted = formatter.format(metadata)
    
    return metadata, formatted


def get_multiple_citations(
    query: str,
    style: str = "Chicago Manual of Style",
    limit: int = 5
) -> List[Tuple[CitationMetadata, str]]:
    """
    Get multiple citation options for a query.
    
    Useful when the user wants to choose from alternatives.
    
    Args:
        query: Search query
        style: Citation style
        limit: Maximum results
        
    Returns:
        List of (CitationMetadata, formatted_string) tuples
    """
    detection = detect_type(query)
    results = []
    
    # Get multiple results based on type
    if detection.citation_type == CitationType.LEGAL:
        metadatas = _legal.search_multiple(query, limit)
    elif detection.citation_type in [CitationType.JOURNAL, CitationType.MEDICAL]:
        metadatas = _crossref.search_multiple(query, limit)
    elif detection.citation_type == CitationType.BOOK:
        metadatas = _google_books.search_multiple(query, limit) if hasattr(_google_books, 'search_multiple') else []
    else:
        metadatas = _crossref.search_multiple(query, limit)
    
    # Format each
    formatter = get_formatter(style)
    for meta in metadatas:
        if meta and meta.has_minimum_data():
            formatted = formatter.format(meta)
            results.append((meta, formatted))
    
    return results[:limit]
