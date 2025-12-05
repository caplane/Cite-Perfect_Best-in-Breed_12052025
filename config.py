"""
citeflex/config.py

Configuration, constants, and shared settings.

Version History:
    2025-12-05: Added version tracking, fixed get_gov_agency to check specific domains first
"""

import os
from typing import Dict

# =============================================================================
# API KEYS (from environment)
# =============================================================================

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
COURTLISTENER_API_KEY = os.environ.get('CL_API_KEY', '')
PUBMED_API_KEY = os.environ.get('PUBMED_API_KEY', '')
SEMANTIC_SCHOLAR_API_KEY = os.environ.get('SEMANTIC_SCHOLAR_API_KEY', '')
GOOGLE_CSE_API_KEY = os.environ.get('GOOGLE_CSE_API_KEY', '')
GOOGLE_CSE_ID = os.environ.get('GOOGLE_CSE_ID', '')

# =============================================================================
# HTTP SETTINGS
# =============================================================================

DEFAULT_TIMEOUT = 10  # seconds
DEFAULT_HEADERS = {
    'User-Agent': 'CiteFlex/2.0 (mailto:user@example.com)',
    'Accept': 'application/json'
}

# =============================================================================
# GEMINI SETTINGS
# =============================================================================

GEMINI_MODEL = 'gemini-2.0-flash'

# =============================================================================
# NEWSPAPER DOMAIN MAPPING
# =============================================================================

NEWSPAPER_DOMAINS: Dict[str, str] = {
    'nytimes.com': 'The New York Times',
    'washingtonpost.com': 'The Washington Post',
    'wsj.com': 'The Wall Street Journal',
    'theguardian.com': 'The Guardian',
    'theatlantic.com': 'The Atlantic',
    'newyorker.com': 'The New Yorker',
    'slate.com': 'Slate',
    'politico.com': 'Politico',
    'bbc.com': 'BBC News',
    'reuters.com': 'Reuters',
    'apnews.com': 'Associated Press',
    'bloomberg.com': 'Bloomberg',
    'forbes.com': 'Forbes',
    'time.com': 'Time',
    'newsweek.com': 'Newsweek',
    'vox.com': 'Vox',
    'vice.com': 'Vice',
    'wired.com': 'Wired',
    'cnn.com': 'CNN',
    'foxnews.com': 'Fox News',
    'nbcnews.com': 'NBC News',
    'cbsnews.com': 'CBS News',
    'abcnews.go.com': 'ABC News',
    'latimes.com': 'Los Angeles Times',
    'chicagotribune.com': 'Chicago Tribune',
    'bostonglobe.com': 'The Boston Globe',
}

# =============================================================================
# GOVERNMENT AGENCY MAPPING
# =============================================================================

GOV_AGENCY_MAP: Dict[str, str] = {
    'fda.gov': 'U.S. Food and Drug Administration',
    'cdc.gov': 'Centers for Disease Control and Prevention',
    'nih.gov': 'National Institutes of Health',
    'epa.gov': 'Environmental Protection Agency',
    'regulations.gov': 'U.S. Government',
    'doe.gov': 'U.S. Department of Energy',
    'energy.gov': 'U.S. Department of Energy',
    'directives.doe.gov': 'U.S. Department of Energy',
    'whitehouse.gov': 'The White House',
    'congress.gov': 'U.S. Congress',
    'supremecourt.gov': 'Supreme Court of the United States',
    'justice.gov': 'U.S. Department of Justice',
    'state.gov': 'U.S. Department of State',
    'treasury.gov': 'U.S. Department of the Treasury',
    'defense.gov': 'U.S. Department of Defense',
    'ed.gov': 'U.S. Department of Education',
    'hhs.gov': 'U.S. Department of Health and Human Services',
    'dhs.gov': 'U.S. Department of Homeland Security',
    'usda.gov': 'U.S. Department of Agriculture',
    'commerce.gov': 'U.S. Department of Commerce',
    'labor.gov': 'U.S. Department of Labor',
    'transportation.gov': 'U.S. Department of Transportation',
    'va.gov': 'U.S. Department of Veterans Affairs',
    'archives.gov': 'National Archives',
    'loc.gov': 'Library of Congress',
    'census.gov': 'U.S. Census Bureau',
    'bls.gov': 'Bureau of Labor Statistics',
    'sec.gov': 'Securities and Exchange Commission',
    'ftc.gov': 'Federal Trade Commission',
    'fcc.gov': 'Federal Communications Commission',
    'federalreserve.gov': 'Federal Reserve',
    'cms.gov': 'Centers for Medicare & Medicaid Services',
    'samhsa.gov': 'Substance Abuse and Mental Health Services Administration',
    'nimh.nih.gov': 'National Institute of Mental Health',
    'ncbi.nlm.nih.gov': 'National Center for Biotechnology Information',
    'pubmed.gov': 'National Library of Medicine',
}

# =============================================================================
# PUBLISHER PLACE MAPPING (for books)
# =============================================================================

PUBLISHER_PLACE_MAP: Dict[str, str] = {
    'Harvard University Press': 'Cambridge, MA',
    'MIT Press': 'Cambridge, MA',
    'Yale University Press': 'New Haven',
    'Princeton University Press': 'Princeton',
    'Stanford University Press': 'Stanford',
    'University of California Press': 'Berkeley',
    'University of Chicago Press': 'Chicago',
    'Columbia University Press': 'New York',
    'Oxford University Press': 'Oxford',
    'Cambridge University Press': 'Cambridge',
    'Penguin': 'New York',
    'Random House': 'New York',
    'HarperCollins': 'New York',
    'Simon & Schuster': 'New York',
    'Farrar, Straus and Giroux': 'New York',
    'W. W. Norton': 'New York',
    'Knopf': 'New York',
    'Routledge': 'London',
    'Bloomsbury': 'London',
    'Sage Publications': 'Thousand Oaks',
    'Wiley': 'Hoboken',
    'Springer': 'New York',
    'Elsevier': 'Amsterdam',
    'Taylor & Francis': 'London',
    'Palgrave Macmillan': 'London',
    'Duke University Press': 'Durham',
    'Johns Hopkins University Press': 'Baltimore',
    'University of Pennsylvania Press': 'Philadelphia',
    'Cornell University Press': 'Ithaca',
    'University of Michigan Press': 'Ann Arbor',
    'University of North Carolina Press': 'Chapel Hill',
    'University of Texas Press': 'Austin',
    'University of Wisconsin Press': 'Madison',
    'Indiana University Press': 'Bloomington',
    'Northwestern University Press': 'Evanston',
    'Basic Books': 'New York',
    'Free Press': 'New York',
    'Vintage': 'New York',
    'Anchor Books': 'New York',
}

# =============================================================================
# LEGAL DOMAINS
# =============================================================================

LEGAL_DOMAINS = [
    'courtlistener.com',
    'oyez.org',
    'case.law',
    'justia.com',
    'supremecourt.gov',
    'law.cornell.edu',
    'findlaw.com',
    'heinonline.org',
    'westlaw.com',
    'lexisnexis.com',
]

# =============================================================================
# ACADEMIC PUBLISHER DOMAINS (for Google CSE parsing)
# =============================================================================

ACADEMIC_DOMAINS = {
    'jstor.org': 'JSTOR',
    'academic.oup.com': 'Oxford Academic',
    'oup.com': 'Oxford University Press',
    'cambridge.org': 'Cambridge University Press',
    'tandfonline.com': 'Taylor & Francis',
    'springer.com': 'Springer',
    'link.springer.com': 'Springer',
    'wiley.com': 'Wiley',
    'onlinelibrary.wiley.com': 'Wiley',
    'sagepub.com': 'SAGE',
    'projectmuse.org': 'Project MUSE',
    'sciencedirect.com': 'ScienceDirect',
    'pubmed.ncbi.nlm.nih.gov': 'PubMed',
    'scholar.google.com': 'Google Scholar',
    'hathitrust.org': 'HathiTrust',
    'archive.org': 'Internet Archive',
    'worldcat.org': 'WorldCat',
}

# =============================================================================
# MEDICAL TERMS (for detection)
# =============================================================================

MEDICAL_TERMS = [
    'clinical', 'patient', 'treatment', 'therapy', 'diagnosis',
    'disease', 'syndrome', 'pharmaceutical', 'drug', 'medicine',
    'medical', 'hospital', 'physician', 'pubmed', 'ncbi',
    'randomized', 'placebo', 'trial', 'efficacy', 'dosage',
    'pathology', 'prognosis', 'etiology', 'symptom', 'chronic',
    'acute', 'disorder', 'condition', 'intervention', 'outcome',
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def resolve_publisher_place(publisher: str, current_place: str = "") -> str:
    """Look up publication place for known publishers."""
    if current_place:
        return current_place
    if not publisher:
        return ''
    for pub_name, pub_place in PUBLISHER_PLACE_MAP.items():
        if pub_name.lower() in publisher.lower():
            return pub_place
    return ''


def get_newspaper_name(domain: str) -> str:
    """Get newspaper name from domain."""
    domain = domain.lower().replace('www.', '')
    for key, name in NEWSPAPER_DOMAINS.items():
        if key in domain:
            return name
    return "Unknown Publication"


def get_gov_agency(domain: str) -> str:
    """
    Get government agency name from domain.
    
    Updated: 2025-12-05 - Check longer/more specific domains first
    """
    domain = domain.lower().replace('www.', '')
    
    # Sort keys by length descending so more specific domains match first
    # e.g., 'nimh.nih.gov' should match before 'nih.gov'
    sorted_keys = sorted(GOV_AGENCY_MAP.keys(), key=len, reverse=True)
    
    for key in sorted_keys:
        if key in domain:
            return GOV_AGENCY_MAP[key]
    return "U.S. Government"
