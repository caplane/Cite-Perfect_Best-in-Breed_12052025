"""
citeflex/extractors.py

Local extractors for source types that don't require API calls.
These use regex and pattern matching to extract metadata from raw text.

Version History:
    2025-12-05: Added multiple date patterns for newspaper URLs (YYYY-MM-DD format)
"""

import re
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional

from models import CitationMetadata, CitationType
from config import (
    NEWSPAPER_DOMAINS, GOV_AGENCY_MAP,
    get_newspaper_name, get_gov_agency
)


# =============================================================================
# INTERVIEW EXTRACTOR
# =============================================================================

def extract_interview(text: str) -> CitationMetadata:
    """
    Extract interview metadata using regex.
    
    Handles patterns like:
    - "John Smith interview, May 7, 1918, Boston, MA"
    - "Kevin Smith interview with William Jones, 11/27/1981, Austin, TX"
    
    NOTE ON DATE PARSING:
    - Slash/dash dates (MM/DD/YYYY) are assumed to be US format
    - For ambiguous dates like 5/6/2020, this CANNOT determine if it's
      May 6 or June 5. The US convention (May 6) is assumed.
    - Unambiguous dates (day > 12) are handled correctly
    - Word dates (May 7, 2020) are preferred and unambiguous
    
    Returns:
        CitationMetadata with interview fields populated
    """
    clean_text = text.strip()
    
    metadata = CitationMetadata(
        citation_type=CitationType.INTERVIEW,
        raw_source=text,
        source_engine="Interview Extractor"
    )
    
    # =========================================================================
    # DATE EXTRACTION
    # =========================================================================
    
    extracted_date = ""
    
    # Pattern 1: Slash/dash dates (MM/DD/YYYY or MM-DD-YYYY)
    slash_date = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b', clean_text)
    
    # Pattern 2: Word dates (May 7, 1918) - PREFERRED as unambiguous
    word_date = re.search(
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',
        clean_text, re.IGNORECASE
    )
    
    # Prefer word dates (unambiguous) over slash dates (ambiguous)
    if word_date:
        try:
            month, day, year = word_date.groups()
            dt = datetime.strptime(f"{month} {day} {year}", "%b %d %Y")
            metadata.date = dt.strftime("%B %d, %Y")
            extracted_date = word_date.group(0)
        except ValueError:
            metadata.date = word_date.group(0)
            extracted_date = word_date.group(0)
    elif slash_date:
        extracted_date = slash_date.group(0)
        month_str, day_str, year_str = slash_date.groups()
        month_val = int(month_str)
        day_val = int(day_str)
        month_val = int(month_str)
        day_val = int(day_str)
        
        # If day > 12, we know it's DD/MM format (European)
        # If month > 12, we know it's MM/DD format (US)
        # Otherwise, assume US format (MM/DD)
        if month_val > 12 and day_val <= 12:
            # European format: DD/MM/YYYY (first number is day, second is month)
            try:
                dt = datetime.strptime(extracted_date.replace('-', '/'), "%d/%m/%Y")
                metadata.date = dt.strftime("%B %d, %Y")
            except ValueError:
                try:
                    dt = datetime.strptime(extracted_date.replace('-', '/'), "%d/%m/%y")
                    metadata.date = dt.strftime("%B %d, %Y")
                except ValueError:
                    metadata.date = extracted_date
        else:
            # Assume US format: MM/DD/YYYY
            try:
                dt = datetime.strptime(extracted_date.replace('-', '/'), "%m/%d/%Y")
                metadata.date = dt.strftime("%B %d, %Y")
            except ValueError:
                try:
                    dt = datetime.strptime(extracted_date.replace('-', '/'), "%m/%d/%y")
                    metadata.date = dt.strftime("%B %d, %Y")
                except ValueError:
                    metadata.date = extracted_date
    
    # Extract year for the year field
    if metadata.date:
        year_match = re.search(r'\d{4}', metadata.date)
        if year_match:
            metadata.year = year_match.group(0)
    
    # =========================================================================
    # NAME EXTRACTION
    # =========================================================================
    
    # Remove date from text for cleaner name extraction
    text_no_date = clean_text
    if extracted_date:
        text_no_date = clean_text.replace(extracted_date, "")
    
    # Pattern 1: "Name interview with Name" (interviewer interviewing interviewee)
    complex_match = re.search(
        r'^([^,]+?)\s+interview\s+with\s+([^,]+)',
        text_no_date, re.IGNORECASE
    )
    
    # Pattern 2: "Name interview by Name" (interviewee interviewed by interviewer)
    by_match = re.search(
        r'^([^,]+?)\s+interview(?:ed)?\s+by\s+([^,]+)',
        text_no_date, re.IGNORECASE
    )
    
    if complex_match:
        metadata.interviewer = complex_match.group(1).strip().title()
        metadata.interviewee = complex_match.group(2).strip().title()
    elif by_match:
        metadata.interviewee = by_match.group(1).strip().title()
        metadata.interviewer = by_match.group(2).strip().title()
    else:
        # Pattern 3: "Name interview" (just interviewee)
        simple_match = re.search(
            r'^([^,]+?)\s+interview',
            text_no_date, re.IGNORECASE
        )
        if simple_match:
            metadata.interviewee = simple_match.group(1).strip().title()
    
    # =========================================================================
    # LOCATION EXTRACTION
    # =========================================================================
    
    # Pattern: Look for "City, State" or "City, ST" anywhere in text
    # More flexible pattern that captures common location formats
    loc_patterns = [
        # "City, ST" at end or before date
        r',\s*([A-Za-z][A-Za-z\s\.]+),\s*([A-Z]{2})(?:\s*,|\s*$)',
        # "City, State" format
        r',\s*([A-Za-z][A-Za-z\s]+),\s*([A-Za-z]{2,})\s*(?:,|$)',
        # Just "City, ST" pattern anywhere
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2})\b',
    ]
    
    for pattern in loc_patterns:
        loc_match = re.search(pattern, text_no_date)
        if loc_match:
            city = loc_match.group(1).strip().title()
            state = loc_match.group(2).strip()
            # Keep 2-letter state codes uppercase, title-case full names
            if len(state) == 2:
                state = state.upper()
            else:
                state = state.title()
            metadata.location = f"{city}, {state}"
            break
    
    return metadata


# =============================================================================
# NEWSPAPER EXTRACTOR
# =============================================================================

def extract_newspaper(url: str) -> CitationMetadata:
    """
    Extract newspaper article metadata from URL.
    
    Extracts:
    - Publication name from domain
    - Title from URL slug
    - Date from URL path (if present)
    
    Returns:
        CitationMetadata with newspaper fields populated
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    
    metadata = CitationMetadata(
        citation_type=CitationType.NEWSPAPER,
        raw_source=url,
        source_engine="Newspaper Extractor",
        url=url,
        access_date=datetime.now().strftime("%B %d, %Y")
    )
    
    # Get publication name
    metadata.newspaper = get_newspaper_name(domain)
    
    # =========================================================================
    # TITLE EXTRACTION FROM URL SLUG
    # =========================================================================
    
    path = parsed.path.rstrip('/')
    if path:
        # Get last segment of path (usually the slug)
        slug = path.split('/')[-1]
        
        # Remove file extensions
        slug = re.sub(r'\.(html?|php|aspx?)$', '', slug)
        
        # Convert slug to title
        clean_title = slug.replace('-', ' ').replace('_', ' ').title()
        
        # Fix common acronyms that get incorrectly title-cased
        acronym_fixes = {
            'Fda': 'FDA', 'Nih': 'NIH', 'Cdc': 'CDC',
            'Us': 'US', 'Uk': 'UK', 'Ai': 'AI',
            'Ceo': 'CEO', 'Cfo': 'CFO', 'Cto': 'CTO',
            'Nasa': 'NASA', 'Fbi': 'FBI', 'Cia': 'CIA',
            'Nba': 'NBA', 'Nfl': 'NFL', 'Mlb': 'MLB',
            'Covid': 'COVID', 'Dna': 'DNA', 'Rna': 'RNA',
        }
        for wrong, right in acronym_fixes.items():
            clean_title = re.sub(r'\b' + wrong + r'\b', right, clean_title)
        
        metadata.title = clean_title
    
    # =========================================================================
    # DATE EXTRACTION FROM URL PATH
    # Updated: 2025-12-05 - Added more date patterns
    # =========================================================================
    
    # Pattern 1: /2024/07/21/ in URL (NYT, WaPo style)
    date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if date_match:
        try:
            year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            dt = datetime(year, month, day)
            metadata.date = dt.strftime("%B %d, %Y")
            metadata.year = str(year)
        except ValueError:
            pass
    
    # Pattern 2: /2024-03-15/ in URL (LA Times style)
    if not metadata.date:
        date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})/', url)
        if date_match:
            try:
                year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                dt = datetime(year, month, day)
                metadata.date = dt.strftime("%B %d, %Y")
                metadata.year = str(year)
            except ValueError:
                pass
    
    # Pattern 3: /story/2024-03-15/ in URL (alternate style)
    if not metadata.date:
        date_match = re.search(r'/story/(\d{4})-(\d{2})-(\d{2})/', url)
        if date_match:
            try:
                year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                dt = datetime(year, month, day)
                metadata.date = dt.strftime("%B %d, %Y")
                metadata.year = str(year)
            except ValueError:
                pass
    
    return metadata


# =============================================================================
# GOVERNMENT DOCUMENT EXTRACTOR
# =============================================================================

def extract_government(url_or_text: str) -> CitationMetadata:
    """
    Extract government document metadata.
    
    Handles:
    - .gov URLs (extracts agency from domain)
    - Federal Register references
    
    Returns:
        CitationMetadata with government fields populated
    """
    clean = url_or_text.rstrip('.,;:)')
    is_url = clean.startswith(('http://', 'https://'))
    
    metadata = CitationMetadata(
        citation_type=CitationType.GOVERNMENT,
        raw_source=url_or_text,
        source_engine="Government Extractor",
        access_date=datetime.now().strftime("%B %d, %Y")
    )
    
    if is_url:
        metadata.url = clean
        parsed = urlparse(clean)
        domain = parsed.netloc.lower().replace('www.', '')
        
        # Get agency from domain
        metadata.agency = get_gov_agency(domain)
        
        # Extract title from path
        path = parsed.path.strip('/')
        if path:
            # Get last segment
            slug = path.split('/')[-1]
            # Remove file extensions
            slug = re.sub(r'\.[a-z]{2,4}$', '', slug)
            # Convert to title
            metadata.title = slug.replace('-', ' ').replace('_', ' ').title()
    else:
        # Not a URL - might be a Federal Register reference
        metadata.agency = "U.S. Government"
        
        # Check for FR reference: 88 FR 12345
        fr_match = re.search(r'(\d+)\s+FR\s+(\d+)', clean, re.IGNORECASE)
        if fr_match:
            vol, page = fr_match.groups()
            metadata.title = f"Federal Register Vol. {vol}, Page {page}"
            metadata.document_number = f"{vol} FR {page}"
    
    return metadata


# =============================================================================
# GENERIC URL EXTRACTOR
# =============================================================================

def extract_url(url: str) -> CitationMetadata:
    """
    Extract basic metadata from a generic URL.
    
    Returns:
        CitationMetadata with minimal URL-derived data
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    
    metadata = CitationMetadata(
        citation_type=CitationType.URL,
        raw_source=url,
        source_engine="URL Extractor",
        url=url,
        access_date=datetime.now().strftime("%B %d, %Y")
    )
    
    # Try to get title from path
    path = parsed.path.rstrip('/')
    if path:
        slug = path.split('/')[-1]
        slug = re.sub(r'\.[a-z]{2,4}$', '', slug)
        if slug:
            metadata.title = slug.replace('-', ' ').replace('_', ' ').title()
        else:
            metadata.title = domain
    else:
        metadata.title = domain
    
    return metadata


# =============================================================================
# EXTRACTOR ROUTER
# =============================================================================

def extract_by_type(text: str, citation_type: CitationType) -> Optional[CitationMetadata]:
    """
    Route to appropriate extractor based on citation type.
    
    Args:
        text: Raw input text
        citation_type: The type of citation to extract
        
    Returns:
        CitationMetadata from the appropriate extractor, or None if not extractable
    """
    extractors = {
        CitationType.INTERVIEW: extract_interview,
        CitationType.NEWSPAPER: extract_newspaper,
        CitationType.GOVERNMENT: extract_government,
        CitationType.URL: extract_url,
    }
    
    extractor = extractors.get(citation_type)
    if extractor:
        return extractor(text)
    
    return None
