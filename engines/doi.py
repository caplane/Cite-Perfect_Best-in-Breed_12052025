"""
citeflex/engines/doi.py

DOI extraction and academic publisher URL handling.
"""

import re
from typing import Optional
from urllib.parse import urlparse

from models import CitationMetadata


# Academic publisher domains and their DOI URL patterns
ACADEMIC_PUBLISHER_DOMAINS = {
    'jstor.org': r'/stable/(\d+)',
    'academic.oup.com': r'/doi/(\d+\.\d+/[^?]+)',
    'oup.com': r'/doi/(\d+\.\d+/[^?]+)',
    'cambridge.org': r'/doi/(\d+\.\d+/[^?]+)',
    'tandfonline.com': r'/doi/(?:abs|full)/(\d+\.\d+/[^?]+)',
    'springer.com': r'/article/(\d+\.\d+/[^?]+)',
    'link.springer.com': r'/article/(\d+\.\d+/[^?]+)',
    'wiley.com': r'/doi/(?:abs|full|pdf)/(\d+\.\d+/[^?]+)',
    'onlinelibrary.wiley.com': r'/doi/(?:abs|full|pdf)/(\d+\.\d+/[^?]+)',
    'sagepub.com': r'/doi/(\d+\.\d+/[^?]+)',
    'sciencedirect.com': r'/pii/([A-Z0-9]+)',  # ScienceDirect uses PII, not DOI
    'nature.com': r'/articles/([^?/]+)',
    'science.org': r'/doi/(\d+\.\d+/[^?]+)',
    'pnas.org': r'/doi/(\d+\.\d+/[^?]+)',
    'cell.com': r'/doi/(\d+\.\d+/[^?]+)',
    'biorxiv.org': r'/content/(\d+\.\d+/[^?]+)',
    'medrxiv.org': r'/content/(\d+\.\d+/[^?]+)',
    'arxiv.org': r'/abs/(\d+\.\d+)',  # arXiv IDs, not DOIs
    'doi.org': r'/(\d+\.\d+/.+)$',
    'dx.doi.org': r'/(\d+\.\d+/.+)$',
}


def extract_doi_from_url(url: str) -> Optional[str]:
    """
    Extract DOI from an academic publisher URL.
    
    Handles URLs from JSTOR, Oxford, Cambridge, Springer, Wiley,
    Taylor & Francis, SAGE, and other major publishers.
    
    Args:
        url: The URL to extract DOI from
        
    Returns:
        DOI string if found, None otherwise
    """
    if not url:
        return None
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        full_url = url.lower()
        
        # Direct DOI URLs
        if 'doi.org' in domain:
            # Handle both doi.org and dx.doi.org
            path = parsed.path.lstrip('/')
            if path.startswith('10.'):
                return path
        
        # Check each publisher pattern
        for pub_domain, pattern in ACADEMIC_PUBLISHER_DOMAINS.items():
            if pub_domain in domain:
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    extracted = match.group(1)
                    # For ScienceDirect, we got PII not DOI
                    if 'sciencedirect' in domain:
                        return None  # Need different handling
                    # Ensure it looks like a DOI
                    if extracted.startswith('10.'):
                        return extracted
                    return None
        
        # Generic DOI pattern in URL
        doi_match = re.search(r'(10\.\d{4,}/[^\s&?#]+)', url)
        if doi_match:
            return doi_match.group(1).rstrip('.')
        
        return None
        
    except Exception:
        return None


def is_academic_publisher_url(url: str) -> bool:
    """
    Check if a URL is from a known academic publisher.
    
    Args:
        url: URL to check
        
    Returns:
        True if from academic publisher, False otherwise
    """
    if not url:
        return False
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        
        for pub_domain in ACADEMIC_PUBLISHER_DOMAINS:
            if pub_domain in domain:
                return True
        
        return False
        
    except Exception:
        return False


def fetch_crossref_by_doi(doi: str) -> Optional[CitationMetadata]:
    """
    Fetch citation metadata from Crossref using DOI.
    
    This is a convenience function that imports CrossrefEngine
    to avoid circular imports at module level.
    
    Args:
        doi: The DOI to look up
        
    Returns:
        CitationMetadata if found, None otherwise
    """
    from engines.academic import CrossrefEngine
    
    engine = CrossrefEngine()
    return engine.get_by_id(doi)


def extract_arxiv_id(url: str) -> Optional[str]:
    """
    Extract arXiv ID from URL.
    
    Args:
        url: arXiv URL
        
    Returns:
        arXiv ID if found, None otherwise
    """
    if not url or 'arxiv' not in url.lower():
        return None
    
    # Patterns: arxiv.org/abs/2301.12345 or arxiv.org/pdf/2301.12345
    match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Old format: arxiv.org/abs/hep-th/9901001
    match = re.search(r'arxiv\.org/(?:abs|pdf)/([a-z-]+/\d+)', url, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


def extract_pmid_from_url(url: str) -> Optional[str]:
    """
    Extract PubMed ID from URL.
    
    Args:
        url: PubMed URL
        
    Returns:
        PMID if found, None otherwise
    """
    if not url:
        return None
    
    # Pattern: pubmed.ncbi.nlm.nih.gov/12345678/
    match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Pattern: ncbi.nlm.nih.gov/pubmed/12345678
    match = re.search(r'ncbi\.nlm\.nih\.gov/pubmed/(\d+)', url, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None
