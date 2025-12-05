"""
citeflex/unified_router.py

Unified routing logic combining the best of CiteFlex Pro and Cite Fix Pro.

Version History:
    2025-12-05 13:15 V1.0: Initial unified router combining both systems
    2025-12-05 13:15 V1.1: Added Westlaw pattern, verified all medical .gov exclusions
    2025-12-05 20:30 V2.0: Moved to engines/ architecture (superlegal, books)
    2025-12-05 21:00 V2.1: Fixed get_multiple_citations to return 3-tuples
    2025-12-05 21:30 V2.2: Added URL/DOI handling to get_multiple_citations
    2025-12-05 22:30 V2.3: Added famous papers cache (10,000 most-cited papers)

KEY IMPROVEMENTS OVER ORIGINAL router.py:
1. Legal detection uses superlegal.is_legal_citation() which checks FAMOUS_CASES cache
   during detection (not just regex patterns that miss bare case names)
2. Legal extraction uses superlegal.extract_metadata() for cache + CourtListener API
3. Book search uses books.py's GoogleBooksAPI + OpenLibraryAPI with PUBLISHER_PLACE_MAP
4. Academic search uses CiteFlex Pro's parallel engine execution
5. Medical URL override prevents PubMed/NIH URLs from routing to government

ARCHITECTURE:
- Wrapper classes convert superlegal.py/books.py dicts → CitationMetadata
- Parallel execution via ThreadPoolExecutor (12s timeout)
- Routing priority: Legal → URL handling → Parallel search → Fallback
"""

import re
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

from models import CitationMetadata, CitationType
from config import NEWSPAPER_DOMAINS, GOV_AGENCY_MAP
from detectors import detect_type, DetectionResult, is_url
from extractors import extract_by_type
from formatters.base import get_formatter

# Import CiteFlex Pro engines
from engines.academic import CrossrefEngine, OpenAlexEngine, SemanticScholarEngine, PubMedEngine
from engines.doi import extract_doi_from_url, is_academic_publisher_url

# Import Cite Fix Pro modules (now in engines/)
from engines import superlegal
from engines import books
from engines.famous_papers import find_famous_paper


# =============================================================================
# CONFIGURATION
# =============================================================================

PARALLEL_TIMEOUT = 12  # seconds
MAX_WORKERS = 4

# Medical domains that should NOT route to government engine
MEDICAL_DOMAINS = ['pubmed', 'ncbi.nlm.nih.gov', 'nih.gov/health', 'medlineplus']


# =============================================================================
# ENGINE INSTANCES (reused across requests)
# =============================================================================

_crossref = CrossrefEngine()
_openalex = OpenAlexEngine()
_semantic = SemanticScholarEngine()
_pubmed = PubMedEngine()


# =============================================================================
# WRAPPER: CONVERT SUPERLEGAL.PY DICT → CitationMetadata
# =============================================================================

def _legal_dict_to_metadata(data: dict, raw_source: str) -> Optional[CitationMetadata]:
    """Convert superlegal.py extract_metadata() dict to CitationMetadata."""
    if not data:
        return None
    
    return CitationMetadata(
        citation_type=CitationType.LEGAL,
        raw_source=raw_source,
        source_engine=data.get('source_engine', 'Legal Cache/CourtListener'),
        case_name=data.get('case_name', ''),
        citation=data.get('citation', ''),
        court=data.get('court', ''),
        year=data.get('year', ''),
        jurisdiction=data.get('jurisdiction', 'US'),
        neutral_citation=data.get('neutral_citation', ''),
        url=data.get('url', ''),
        raw_data=data
    )


# =============================================================================
# WRAPPER: CONVERT BOOKS.PY DICT → CitationMetadata
# =============================================================================

def _book_dict_to_metadata(data: dict, raw_source: str) -> Optional[CitationMetadata]:
    """Convert books.py result dict to CitationMetadata."""
    if not data:
        return None
    
    return CitationMetadata(
        citation_type=CitationType.BOOK,
        raw_source=raw_source,
        source_engine=data.get('source_engine', 'Google Books/Open Library'),
        title=data.get('title', ''),
        authors=data.get('authors', []),
        year=data.get('year', ''),
        publisher=data.get('publisher', ''),
        place=data.get('place', ''),
        isbn=data.get('isbn', ''),
        raw_data=data
    )


# =============================================================================
# UNIFIED LEGAL SEARCH (uses superlegal.py)
# =============================================================================

def _route_legal(query: str) -> Optional[CitationMetadata]:
    """
    Route legal case queries using Cite Fix Pro's superlegal.py.
    
    This is superior to CiteFlex Pro's legal.py because:
    1. FAMOUS_CASES cache has 100+ landmark cases
    2. is_legal_citation() checks cache during detection (catches "Roe v Wade")
    3. Fuzzy matching via difflib for near-matches
    4. CourtListener API fallback with phrase/keyword/fuzzy attempts
    """
    try:
        data = superlegal.extract_metadata(query)
        if data and (data.get('case_name') or data.get('citation')):
            return _legal_dict_to_metadata(data, query)
    except Exception as e:
        print(f"[UnifiedRouter] Legal search error: {e}")
    
    return None


# =============================================================================
# UNIFIED BOOK SEARCH (uses books.py)
# =============================================================================

def _route_book(query: str) -> Optional[CitationMetadata]:
    """
    Route book queries using Cite Fix Pro's books.py.
    
    This is superior to CiteFlex Pro's google_cse.py because:
    1. Dual-engine: Open Library (precise ISBN) + Google Books (fuzzy search)
    2. PUBLISHER_PLACE_MAP fills in publication places
    3. ISBN detection routes to Open Library first
    """
    try:
        results = books.extract_metadata(query)
        if results and len(results) > 0:
            return _book_dict_to_metadata(results[0], query)
    except Exception as e:
        print(f"[UnifiedRouter] Book search error: {e}")
    
    # Fallback to CiteFlex Pro's Crossref (has book chapters)
    try:
        result = _crossref.search(query)
        if result and result.has_minimum_data():
            return result
    except Exception:
        pass
    
    return None


# =============================================================================
# PARALLEL ENGINE EXECUTION (from CiteFlex Pro)
# =============================================================================

def _search_engines_parallel(
    engines: List[Tuple[str, callable]],
    query: str,
    timeout: float = PARALLEL_TIMEOUT
) -> Optional[CitationMetadata]:
    """
    Execute multiple search engines in parallel, return first valid result.
    
    This reduces worst-case latency from 40+ seconds to ~10 seconds.
    """
    if not engines:
        return None
    
    with ThreadPoolExecutor(max_workers=min(len(engines), MAX_WORKERS)) as executor:
        future_to_engine = {
            executor.submit(fn, query): name
            for name, fn in engines
        }
        
        try:
            for future in as_completed(future_to_engine, timeout=timeout):
                engine_name = future_to_engine[future]
                try:
                    result = future.result(timeout=1)
                    if result and result.has_minimum_data():
                        print(f"[UnifiedRouter] Found via {engine_name}")
                        return result
                except Exception as e:
                    print(f"[UnifiedRouter] {engine_name} failed: {e}")
                    continue
        except FuturesTimeout:
            print(f"[UnifiedRouter] Parallel search timed out after {timeout}s")
    
    return None


# =============================================================================
# JOURNAL/ACADEMIC ROUTING (CiteFlex Pro engines)
# =============================================================================

def _route_journal(query: str) -> Optional[CitationMetadata]:
    """
    Route journal/article queries using CiteFlex Pro's academic engines.
    Runs Crossref, OpenAlex, and Semantic Scholar in parallel.
    """
    # Check famous papers cache first (instant lookup for 10,000 most-cited)
    famous = find_famous_paper(query)
    if famous:
        result = _crossref.get_by_id(famous["doi"])
        if result:
            print("[UnifiedRouter] Found via Famous Papers cache")
            return result
    
    # Check for DOI in query first (instant lookup)
    doi_match = re.search(r'(10\.\d{4,}/[^\s]+)', query)
    if doi_match:
        doi = doi_match.group(1).rstrip('.,;')
        result = _crossref.get_by_id(doi)
        if result:
            print("[UnifiedRouter] Found via direct DOI lookup")
            return result
    
    # Parallel search across academic engines
    engines = [
        ("Crossref", _crossref.search),
        ("OpenAlex", _openalex.search),
        ("Semantic Scholar", _semantic.search),
    ]
    
    return _search_engines_parallel(engines, query)


# =============================================================================
# MEDICAL ROUTING (CiteFlex Pro PubMed + academic engines)
# =============================================================================

def _route_medical(query: str) -> Optional[CitationMetadata]:
    """
    Route medical/clinical queries.
    Tries PubMed first (specialized), then falls back to academic engines.
    """
    # Check for PMID
    pmid_match = re.search(r'(?:pmid:?\s*|pubmed:?\s*)(\d+)', query, re.IGNORECASE)
    if pmid_match:
        pmid = pmid_match.group(1)
        result = _pubmed.get_by_id(pmid)
        if result:
            print("[UnifiedRouter] Found via direct PMID lookup")
            return result
    
    # Parallel search: PubMed + academic engines
    engines = [
        ("PubMed", _pubmed.search),
        ("Crossref", _crossref.search),
        ("Semantic Scholar", _semantic.search),
    ]
    
    return _search_engines_parallel(engines, query)


# =============================================================================
# URL ROUTING (with medical domain override)
# =============================================================================

def _is_medical_url(url: str) -> bool:
    """Check if URL is from a medical domain (should route to PubMed, not gov)."""
    lower = url.lower()
    return any(domain in lower for domain in MEDICAL_DOMAINS)


def _is_newspaper_url(url: str) -> bool:
    """Check if URL is from a newspaper domain."""
    lower = url.lower()
    return any(domain in lower for domain in NEWSPAPER_DOMAINS.keys())


def _is_government_url(url: str) -> bool:
    """Check if URL is from a government domain."""
    return '.gov' in url.lower() and not _is_medical_url(url)


def _route_url(url: str) -> Optional[CitationMetadata]:
    """
    Route URL-based queries with smart domain detection.
    
    Priority:
    1. Medical URLs → PubMed (override .gov for NIH/PubMed)
    2. Academic publisher URLs → DOI extraction → Crossref
    3. Government URLs → basic metadata extraction
    4. Newspaper URLs → basic metadata extraction
    5. Generic URLs → basic metadata
    """
    # 1. Medical URL override (PubMed, NIH, etc.)
    if _is_medical_url(url):
        # Try to extract PMID from URL
        pmid_match = re.search(r'/(\d{7,8})/?', url)
        if pmid_match:
            result = _pubmed.get_by_id(pmid_match.group(1))
            if result:
                result.url = url
                return result
        # Fall back to medical routing
        return _route_medical(url)
    
    # 2. Academic publisher URL → DOI extraction
    if is_academic_publisher_url(url):
        doi = extract_doi_from_url(url)
        if doi:
            result = _crossref.get_by_id(doi)
            if result:
                result.url = url
                print("[UnifiedRouter] Found via DOI extraction from URL")
                return result
    
    # 3. Try generic DOI extraction from URL path
    doi_match = re.search(r'(10\.\d{4,}/[^\s?#]+)', url)
    if doi_match:
        doi = doi_match.group(1).rstrip('.,;')
        result = _crossref.get_by_id(doi)
        if result:
            result.url = url
            print("[UnifiedRouter] Found via DOI in URL path")
            return result
    
    # 4. Government URL
    if _is_government_url(url):
        return extract_by_type(url, CitationType.GOVERNMENT)
    
    # 5. Newspaper URL
    if _is_newspaper_url(url):
        return extract_by_type(url, CitationType.NEWSPAPER)
    
    # 6. Generic URL
    return extract_by_type(url, CitationType.URL)


# =============================================================================
# MAIN ROUTING FUNCTION
# =============================================================================

def route_citation(query: str) -> Tuple[Optional[CitationMetadata], DetectionResult]:
    """
    Main routing function with unified detection and search.
    
    KEY DIFFERENCE from original router.py:
    - Uses superlegal.is_legal_citation() for legal detection (cache-aware)
    - This catches bare case names like "Roe v Wade" that regex misses
    """
    query = query.strip()
    
    # ==========================================================================
    # STEP 1: Check if it's a legal citation using superlegal.py's cache-aware detector
    # ==========================================================================
    if superlegal.is_legal_citation(query):
        print(f"[UnifiedRouter] Detected: LEGAL (cache-aware)")
        metadata = _route_legal(query)
        if metadata:
            return metadata, DetectionResult(
                citation_type=CitationType.LEGAL,
                confidence=0.95,
                cleaned_query=query
            )
    
    # ==========================================================================
    # STEP 2: Use CiteFlex Pro's pattern detection for other types
    # ==========================================================================
    detection = detect_type(query)
    print(f"[UnifiedRouter] Detected: {detection.citation_type.name} (confidence: {detection.confidence})")
    
    metadata = None
    
    # ==========================================================================
    # STEP 3: Route based on detected type
    # ==========================================================================
    
    if detection.citation_type == CitationType.INTERVIEW:
        metadata = extract_by_type(query, CitationType.INTERVIEW)
    
    elif detection.citation_type == CitationType.LEGAL:
        # Already checked above, but try again in case detection differs
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
        # Try journal engines as default, then book
        metadata = _route_journal(query)
        if not metadata:
            metadata = _route_book(query)
    
    return metadata, detection


# =============================================================================
# HIGH-LEVEL API (same interface as original router.py)
# =============================================================================

def get_citation(
    query: str,
    style: str = "Chicago Manual of Style"
) -> Tuple[Optional[CitationMetadata], Optional[str]]:
    """
    Main entry point for getting a formatted citation.
    
    This is the function imported by document_processor.py.
    
    Args:
        query: The citation query (URL, title, case name, etc.)
        style: Citation style name
        
    Returns:
        Tuple of (CitationMetadata, formatted_citation_string)
        Both may be None if lookup fails.
    """
    metadata, detection = route_citation(query)
    
    if not metadata or not metadata.has_minimum_data():
        print(f"[UnifiedRouter] No metadata found for: {query[:50]}...")
        return None, None
    
    formatter = get_formatter(style)
    formatted = formatter.format(metadata)
    
    return metadata, formatted


def get_multiple_citations(
    query: str,
    style: str = "Chicago Manual of Style",
    limit: int = 5
) -> List[Tuple[CitationMetadata, str, str]]:
    """
    Get multiple citation options for a query.
    
    Args:
        query: Search query
        style: Citation style
        limit: Maximum results
        
    Returns:
        List of (CitationMetadata, formatted_string, source_name) tuples
    """
    results = []
    formatter = get_formatter(style)
    
    # ==========================================================================
    # STEP 0: URL with DOI - extract and lookup directly (MUST BE FIRST)
    # ==========================================================================
    if is_url(query):
        # Try academic publisher URL first
        if is_academic_publisher_url(query):
            doi = extract_doi_from_url(query)
            if doi:
                result = _crossref.get_by_id(doi)
                if result and result.has_minimum_data():
                    result.url = query  # Preserve original URL
                    formatted = formatter.format(result)
                    results.append((result, formatted, "Crossref (DOI)"))
                    return results  # DOI lookup is authoritative
        
        # Try extracting DOI from URL path (e.g., /doi/10.1086/737056)
        doi_match = re.search(r'(10\.\d{4,}/[^\s?#]+)', query)
        if doi_match:
            doi = doi_match.group(1).rstrip('.,;')
            result = _crossref.get_by_id(doi)
            if result and result.has_minimum_data():
                result.url = query
                formatted = formatter.format(result)
                results.append((result, formatted, "Crossref (DOI)"))
                return results  # DOI lookup is authoritative
        
        # For non-DOI URLs, route through _route_url
        metadata = _route_url(query)
        if metadata and metadata.has_minimum_data():
            formatted = formatter.format(metadata)
            source = metadata.source_engine or "URL"
            results.append((metadata, formatted, source))
            return results
    
    # ==========================================================================
    # STEP 0.5: Check famous papers cache (10,000 most-cited papers)
    # ==========================================================================
    famous = find_famous_paper(query)
    if famous:
        # Use DOI to get full metadata from Crossref
        result = _crossref.get_by_id(famous["doi"])
        if result and result.has_minimum_data():
            formatted = formatter.format(result)
            results.append((result, formatted, "Famous Papers"))
            return results  # Famous paper lookup is authoritative
    
    # ==========================================================================
    # STEP 1: Check if legal
    # ==========================================================================
    if superlegal.is_legal_citation(query):
        metadata = _route_legal(query)
        if metadata:
            formatted = formatter.format(metadata)
            source = metadata.source_engine or "Legal Cache"
            results.append((metadata, formatted, source))
        return results
    
    # ==========================================================================
    # STEP 2: Detection-based routing
    # ==========================================================================
    detection = detect_type(query)
    
    if detection.citation_type in [CitationType.JOURNAL, CitationType.MEDICAL]:
        metadatas = _crossref.search_multiple(query, limit)
        for meta in metadatas:
            if meta and meta.has_minimum_data():
                formatted = formatter.format(meta)
                source = meta.source_engine or "Crossref"
                results.append((meta, formatted, source))
    
    elif detection.citation_type == CitationType.BOOK:
        # Query book engines
        try:
            book_results = books.extract_metadata(query)
            for data in book_results[:limit]:
                meta = _book_dict_to_metadata(data, query)
                if meta:
                    formatted = formatter.format(meta)
                    source = meta.source_engine or data.get('source_engine', 'Google Books')
                    results.append((meta, formatted, source))
        except Exception:
            pass
        
        # Also try Crossref (has book chapters)
        if len(results) < limit:
            try:
                metadatas = _crossref.search_multiple(query, limit - len(results))
                for meta in metadatas:
                    if meta and meta.has_minimum_data():
                        formatted = formatter.format(meta)
                        results.append((meta, formatted, "Crossref"))
            except Exception:
                pass
    
    elif detection.citation_type == CitationType.UNKNOWN:
        # For unknown, try BOTH Crossref AND book engines
        # Crossref first (journals, chapters)
        try:
            metadatas = _crossref.search_multiple(query, limit)
            for meta in metadatas:
                if meta and meta.has_minimum_data():
                    formatted = formatter.format(meta)
                    results.append((meta, formatted, "Crossref"))
        except Exception:
            pass
        
        # Then book engines
        if len(results) < limit:
            try:
                book_results = books.extract_metadata(query)
                for data in book_results[:limit - len(results)]:
                    meta = _book_dict_to_metadata(data, query)
                    if meta:
                        formatted = formatter.format(meta)
                        source = data.get('source_engine', 'Google Books')
                        results.append((meta, formatted, source))
            except Exception:
                pass
    
    return results[:limit]


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

def search_citation(query: str) -> List[dict]:
    """
    Backward-compatible search function.
    Returns list of dicts (matching old search.py interface).
    """
    results = []
    
    # Try legal first
    if superlegal.is_legal_citation(query):
        data = superlegal.extract_metadata(query)
        if data:
            results.append(data)
        return results
    
    # Try books
    try:
        book_results = books.extract_metadata(query)
        results.extend(book_results)
    except Exception:
        pass
    
    # Try academic
    try:
        meta = _route_journal(query)
        if meta:
            results.append(meta.to_dict())
    except Exception:
        pass
    
    return results
