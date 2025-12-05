"""
citeflex/detectors.py

Pattern detection for citation type classification.
This is Layer 1 of the hybrid architecture - fast, free, regex-based.

Each detector returns True/False. The router uses these to classify input.

Version History:
    2025-12-05 12:53: Fixed medical .gov URL routing (PubMed, NIH, NIMH now route to MEDICAL)
                      Excluded medical domains from is_government detection
    2025-12-05 13:15: Added Westlaw citation pattern (2024 WL 123456)
                      Verified Federal Reporter pattern (123 F.3d 456)
"""

import re
from urllib.parse import urlparse
from typing import Optional

from models import CitationType, DetectionResult
from config import NEWSPAPER_DOMAINS, LEGAL_DOMAINS, MEDICAL_TERMS


# =============================================================================
# INDIVIDUAL DETECTORS
# =============================================================================

def is_url(text: str) -> bool:
    """Check if text is a URL."""
    clean = text.strip()
    return clean.startswith(('http://', 'https://'))


def is_interview(text: str) -> bool:
    """
    Detect interview/oral history citations.
    
    Triggers:
    - "Name interview" pattern (interview as citation)
    - "Interview with Name" pattern
    - "oral history" phrase
    - "personal communication" phrase
    
    Does NOT trigger for:
    - "The history of interviews" (interview as subject noun)
    - "interview process" or "interview techniques" (interview as modifier)
    """
    lower = text.lower()
    
    # Strong patterns that definitely indicate an interview citation
    strong_patterns = [
        r'\boral history\b',
        r'\bpersonal communication\b',
        r'\bconversation with\b',
        r'\binterviewed?\s+by\b',  # "interviewed by" or "interview by"
        r'\binterview\s+with\b',    # "interview with"
        r'\binterview[,\s]+[A-Z]',  # "interview, City" or "interview Alexandria"
        r'^[A-Za-z\s]+interview\b', # "Name interview" at start
    ]
    
    for pattern in strong_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    # Weak pattern: "interview" somewhere in text
    # Check it's not just discussing interviews
    if 'interview' in lower:
        # Negative patterns that indicate we're NOT citing an interview
        negative_patterns = [
            r'\bhistory of interviews?\b',
            r'\binterview process\b',
            r'\binterview technique\b',
            r'\bjob interview\b',
            r'\binterview question\b',
            r'\binterview skill\b',
            r'\binterview method\b',
            r'\binterviews?\s+(in|about|on|of)\b',  # "interviews in journalism"
        ]
        
        for pattern in negative_patterns:
            if re.search(pattern, lower):
                return False
        
        # If we have a date/location pattern near "interview", it's likely a citation
        if re.search(r'interview.*\d{4}', lower):  # interview ... year
            return True
        if re.search(r'interview.*[A-Z][a-z]+,\s*[A-Z]{2}', text):  # interview ... City, ST
            return True
    
    return False


def is_legal(text: str) -> bool:
    """
    Detect legal case citations.
    
    Triggers:
    - "v." or "vs" pattern (but NOT version patterns like v1, v2)
    - UK neutral citation: [2024] UKSC 123
    - Legal website URLs
    - Court names or case reporters
    """
    if not text:
        return False
    clean = text.strip()
    
    # ==========================================================================
    # FIX: Exclude version patterns (v1, v2, v3.9, etc.)
    # ==========================================================================
    # If text contains version-like patterns, it's probably not legal
    if re.search(r'\bv\d', clean, re.IGNORECASE):
        return False
    if re.search(r'\bversion\s*\d', clean, re.IGNORECASE):
        return False
    
    # Exclude Federal Register patterns (these are government, not legal)
    if re.search(r'\b\d+\s*FR\s+\d+\b', clean, re.IGNORECASE):
        return False
    if re.search(r'\bfederal\s+register\b', clean, re.IGNORECASE):
        return False
    
    # UK neutral citation pattern: [2024] UKSC 123
    if '[' in clean and ']' in clean:
        if re.search(r'\[\d{4}\]', clean):
            return True
    
    # Legal website
    if is_url(clean):
        if any(d in clean.lower() for d in LEGAL_DOMAINS):
            return True
    
    # "v." or "vs" pattern (the classic case name indicator)
    # But require it to be between word characters (not "Team vs" at end)
    if re.search(r'\b[A-Z][a-z]+\s+(v|vs|versus)\.?\s+[A-Z]', clean):
        return True
    
    # Case reporter patterns - multiple patterns to catch variations
    # Updated: 2025-12-05 - Added Westlaw (WL) pattern
    reporter_patterns = [
        # U.S. Reports: 388 U.S. 1
        r'\d+\s+U\.S\.\s+\d+',
        # State reporters: 248 N.Y. 339, 17 Cal. 3d 425
        r'\d+\s+[A-Z][a-z]*\.?\s*\d*[a-z]*\.?\s+\d+',
        # Federal Reporter: 159 F.2d 169, 400 F.3d 123
        r'\d+\s+F\.\d+[a-z]*\s+\d+',
        # Federal Supplement: 400 F. Supp. 2d 707
        r'\d+\s+F\.\s*Supp\.\s*\d*[a-z]*\s+\d+',
        # Atlantic/Pacific/etc reporters: 355 A.2d 647
        r'\d+\s+[A-Z]\.\d+[a-z]*\s+\d+',
        # Westlaw: 2024 WL 123456
        r'\d{4}\s+WL\s+\d+',
        # Generic: Volume Reporter Page with periods
        r'\d+\s+[A-Z][A-Za-z\.]+\s+\d+',
    ]
    
    for pattern in reporter_patterns:
        if re.search(pattern, clean):
            return True
    
    return False


def is_newspaper(text: str) -> bool:
    """
    Detect newspaper/magazine article citations.
    
    Triggers:
    - URLs from known newspaper domains
    - Newspaper names in text
    """
    if not text:
        return False
    
    clean = text.strip()
    lower = clean.lower()
    
    # Check for URL to newspaper
    if is_url(clean):
        try:
            domain = urlparse(clean).netloc.lower().replace('www.', '')
            if any(nd in domain for nd in NEWSPAPER_DOMAINS):
                return True
        except:
            pass
    
    # Check for newspaper names in text
    newspaper_names = [
        'new york times',
        'wall street journal',
        'washington post',
        'los angeles times',
        'chicago tribune',
        'boston globe',
        'the guardian',
        'the economist',
        'financial times',
        'usa today',
        'atlantic',
        'new yorker',
        'politico',
        'huffington post',
        'huffpost',
        'buzzfeed',
        'daily beast',
        'slate',
        'vox',
        'reuters',
        'associated press',
        'ap news',
    ]
    
    for name in newspaper_names:
        if name in lower:
            return True
    
    return False


def is_government(text: str) -> bool:
    """
    Detect government document sources.
    
    Triggers:
    - .gov domain (excluding medical domains like NIH, PubMed, NLM)
    - Federal Register citation pattern
    
    Updated: 2025-12-05 - Exclude medical .gov domains
    """
    if not text:
        return False
    clean = text.rstrip('.,;:)').lower()
    
    # .gov domain - but exclude medical sites
    if re.search(r'\.gov(/|$)', clean):
        # Medical .gov domains should route to MEDICAL, not GOVERNMENT
        medical_gov_domains = [
            'pubmed.ncbi.nlm.nih.gov',
            'ncbi.nlm.nih.gov',
            'nlm.nih.gov',
            'nih.gov',
            'nimh.nih.gov',
            'nci.nih.gov',
            'clinicaltrials.gov',
            'medlineplus.gov',
        ]
        for domain in medical_gov_domains:
            if domain in clean:
                return False
        return True
    
    # Federal Register pattern: 88 FR 12345 or 87 Federal Register 11111
    if re.search(r'\b\d+\s+FR\s+\d+\b', clean, re.IGNORECASE):
        return True
    if re.search(r'\b\d+\s+federal\s+register\s+\d+\b', clean, re.IGNORECASE):
        return True
    
    return False


def is_medical(text: str) -> bool:
    """
    Detect medical/clinical citations.
    
    Triggers:
    - Medical .gov domains (PubMed, NIH, NLM, NIMH, etc.)
    - PMID reference
    - Medical terminology density
    
    Updated: 2025-12-05 - Added medical .gov URL detection
    """
    if not text:
        return False
    lower = text.lower()
    
    # Medical .gov domains
    medical_gov_domains = [
        'pubmed.ncbi.nlm.nih.gov',
        'ncbi.nlm.nih.gov',
        'nlm.nih.gov',
        'nih.gov',
        'nimh.nih.gov',
        'nci.nih.gov',
        'clinicaltrials.gov',
        'medlineplus.gov',
    ]
    for domain in medical_gov_domains:
        if domain in lower:
            return True
    
    # Explicit PMID patterns
    pmid_patterns = [
        r'pmid:?\s*\d+',
        r'pubmed\s*id:?\s*\d+',
        r'pubmed:\s*\d+',
    ]
    for pattern in pmid_patterns:
        if re.search(pattern, lower):
            return True
    
    # Strong medical indicators (single term enough)
    strong_indicators = [
        'randomized controlled trial',
        'double-blind',
        'placebo-controlled',
        'meta-analysis',
        'systematic review',
        'clinical trial',
        'clinical efficacy',
        'treatment-resistant',
    ]
    for indicator in strong_indicators:
        if indicator in lower:
            return True
    
    # Medical terminology (need at least 2 terms for confidence)
    term_count = sum(1 for term in MEDICAL_TERMS if term in lower)
    return term_count >= 2


def is_journal(text: str) -> bool:
    """
    Detect journal article citations.
    
    Triggers:
    - DOI pattern
    - Volume/issue patterns
    - Page range patterns
    """
    if not text:
        return False
    lower = text.lower()
    
    # DOI pattern: 10.1234/something
    if re.search(r'10\.\d{4,}/', lower):
        return True
    
    # Volume/issue patterns: "23(4)" or "vol. 23"
    if re.search(r'\b\d+\s*\(\d+\)', lower):
        return True
    if re.search(r'\bvol\.?\s*\d+', lower):
        return True
    
    # Page range patterns: "pp. 45-67" or "123-145"
    if re.search(r'\bpp\.?\s*\d+\s*[-–]\s*\d+', lower):
        return True
    if re.search(r'\bpages?\s*\d+\s*[-–]\s*\d+', lower):
        return True
    
    return False


def is_book(text: str) -> bool:
    """
    Detect book citations.
    
    Triggers:
    - ISBN pattern
    - Publisher name
    - Edition indicators
    - "book" keyword
    """
    if not text:
        return False
    lower = text.lower()
    
    # ISBN patterns
    if re.search(r'\b(?:97[89][-\s]?)?(\d[-\s]?){9}[\dX]\b', text, re.IGNORECASE):
        return True
    if 'isbn' in lower:
        return True
    
    # Edition indicators
    if re.search(r'\b\d+(?:st|nd|rd|th)\s+(?:ed|edition)', lower):
        return True
    if re.search(r'\bedition\b', lower):
        return True
    
    # Publisher keywords
    publisher_hints = ['press', 'publishers', 'publishing', 'books']
    if any(hint in lower for hint in publisher_hints):
        return True
    
    # Explicit "book" keyword
    if re.search(r'\bbook\b', lower):
        return True
    
    return False


# =============================================================================
# MAIN DETECTION ROUTER
# =============================================================================

def detect_type(text: str) -> DetectionResult:
    """
    Main detection function. Runs all detectors and returns the best match.
    
    Priority order (most specific to least):
    1. Interview (explicit keywords)
    2. Legal (v. pattern, neutral citation)
    3. Government (.gov URL)
    4. Newspaper (news URL)
    5. Medical (clinical terms)
    6. Journal (DOI, volume/issue)
    7. Book (ISBN, publisher)
    8. URL (generic)
    9. Unknown (fallback)
    
    Returns:
        DetectionResult with type, confidence, and cleaned query
    """
    if not text or not text.strip():
        return DetectionResult(
            citation_type=CitationType.UNKNOWN,
            confidence=0.0,
            cleaned_query=""
        )
    
    clean_text = text.strip()
    
    # Check each type in priority order
    
    # 1. Interview - very specific keywords
    if is_interview(clean_text):
        return DetectionResult(
            citation_type=CitationType.INTERVIEW,
            confidence=0.95,
            cleaned_query=clean_text
        )
    
    # 2. Legal - "v." pattern or legal domains
    if is_legal(clean_text):
        # Extract case name for searching
        query = clean_text
        # Remove citation numbers for cleaner search
        query = re.sub(r'\d+\s+[A-Z][a-z]*\.?\s*\d*[a-z]*\.?\s+\d+', '', query).strip()
        return DetectionResult(
            citation_type=CitationType.LEGAL,
            confidence=0.9,
            cleaned_query=query or clean_text
        )
    
    # 3. Government - .gov URLs
    if is_government(clean_text):
        return DetectionResult(
            citation_type=CitationType.GOVERNMENT,
            confidence=0.95,
            cleaned_query=clean_text
        )
    
    # 4. Newspaper - news site URLs
    if is_newspaper(clean_text):
        return DetectionResult(
            citation_type=CitationType.NEWSPAPER,
            confidence=0.95,
            cleaned_query=clean_text
        )
    
    # 5. Medical - clinical terminology
    if is_medical(clean_text):
        return DetectionResult(
            citation_type=CitationType.MEDICAL,
            confidence=0.8,
            cleaned_query=clean_text
        )
    
    # 6. Journal - DOI, volume/issue patterns
    if is_journal(clean_text):
        return DetectionResult(
            citation_type=CitationType.JOURNAL,
            confidence=0.85,
            cleaned_query=clean_text
        )
    
    # 7. Book - ISBN, publisher patterns
    if is_book(clean_text):
        return DetectionResult(
            citation_type=CitationType.BOOK,
            confidence=0.8,
            cleaned_query=clean_text
        )
    
    # 8. Generic URL
    if is_url(clean_text):
        return DetectionResult(
            citation_type=CitationType.URL,
            confidence=0.7,
            cleaned_query=clean_text
        )
    
    # 9. Unknown - will need Gemini or default journal search
    return DetectionResult(
        citation_type=CitationType.UNKNOWN,
        confidence=0.0,
        cleaned_query=clean_text
    )


# =============================================================================
# CONVENIENCE FUNCTION (backward compatibility)
# =============================================================================

def detect_citation_type(text: str) -> str:
    """
    Backward-compatible detection function.
    Returns string type name instead of enum.
    """
    result = detect_type(text)
    return result.citation_type.name
