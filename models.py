"""
citeflex/models.py

Core data models for the citation system.
All modules communicate through these standardized structures.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum, auto


class CitationType(Enum):
    """Enumeration of supported citation types."""
    JOURNAL = auto()
    BOOK = auto()
    LEGAL = auto()
    INTERVIEW = auto()
    LETTER = auto()  # Correspondence: Person X to Person Y
    NEWSPAPER = auto()
    GOVERNMENT = auto()
    MEDICAL = auto()
    URL = auto()
    UNKNOWN = auto()


class CitationStyle(Enum):
    """Supported citation formatting styles."""
    CHICAGO = "chicago"
    APA = "apa"
    MLA = "mla"
    BLUEBOOK = "bluebook"
    OSCOLA = "oscola"
    
    @classmethod
    def from_string(cls, s: str) -> "CitationStyle":
        """Parse style from string, with common aliases."""
        mapping = {
            'chicago manual of style': cls.CHICAGO,
            'chicago': cls.CHICAGO,
            'apa 7': cls.APA,
            'apa': cls.APA,
            'mla 9': cls.MLA,
            'mla': cls.MLA,
            'bluebook': cls.BLUEBOOK,
            'oscola': cls.OSCOLA,
        }
        return mapping.get(s.lower().strip(), cls.CHICAGO)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_doi(doi: str) -> str:
    """
    Normalize a DOI to a consistent format for comparison.
    
    Handles various input formats:
    - 10.1234/abc
    - https://doi.org/10.1234/abc
    - http://doi.org/10.1234/abc
    - http://dx.doi.org/10.1234/abc
    - doi:10.1234/abc
    - DOI: 10.1234/abc
    
    Returns:
        Normalized DOI string (just the identifier, lowercase)
    """
    if not doi:
        return ""
    
    doi = doi.strip()
    
    # Remove common prefixes (case-insensitive)
    prefixes = [
        'https://doi.org/',
        'http://doi.org/',
        'https://dx.doi.org/',
        'http://dx.doi.org/',
        'doi:',
        'DOI:',
        'doi: ',
        'DOI: ',
    ]
    
    doi_lower = doi.lower()
    for prefix in prefixes:
        if doi_lower.startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    
    return doi.lower().strip()


@dataclass
class CitationMetadata:
    """
    Universal citation metadata container.
    
    This is the standard data contract that flows through the entire system:
    - Detectors identify the type
    - Engines/Extractors populate the fields
    - Normalizers standardize API responses into this format
    - Formatters consume this to produce citation strings
    
    All fields are optional because different source types use different subsets.
    """
    
    # Core identification
    citation_type: CitationType = CitationType.UNKNOWN
    raw_source: str = ""  # Original user input
    source_engine: str = ""  # Which engine/extractor produced this
    
    # Common fields (most types)
    title: str = ""
    authors: List[str] = field(default_factory=list)
    year: Optional[str] = None
    url: str = ""
    doi: str = ""
    
    # Journal/Medical article fields
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    pmid: str = ""
    
    # Book fields
    publisher: str = ""
    place: str = ""  # Publication place
    edition: str = ""
    isbn: str = ""
    
    # Legal case fields
    case_name: str = ""
    citation: str = ""  # Legal citation (e.g., "388 U.S. 1")
    court: str = ""
    jurisdiction: str = ""  # US, UK, etc.
    neutral_citation: str = ""  # UK-style citation
    
    # Interview fields
    interviewee: str = ""
    interviewer: str = ""
    location: str = ""
    date: str = ""
    
    # Letter/correspondence fields
    sender: str = ""
    recipient: str = ""
    # (also uses: date, location, url, title for subject/re line)
    
    # Newspaper fields
    newspaper: str = ""
    # (uses: author, title, date, url)
    
    @property
    def publication(self) -> str:
        """Alias for newspaper field (used by some formatters)."""
        return self.newspaper
    
    @publication.setter
    def publication(self, value: str):
        """Set newspaper via publication alias."""
        self.newspaper = value
    
    # Government document fields
    agency: str = ""
    document_number: str = ""
    # (uses: author, title, url, date)
    
    # Metadata
    access_date: str = ""
    confidence: float = 1.0  # How confident are we in this result (0-1)
    raw_data: Dict[str, Any] = field(default_factory=dict)  # Original API response
    
    def get_normalized_doi(self) -> str:
        """Get normalized DOI for comparison purposes."""
        return normalize_doi(self.doi)
    
    def has_minimum_data(self) -> bool:
        """Check if we have enough data to format a citation."""
        if self.citation_type == CitationType.LEGAL:
            return bool(self.case_name)
        elif self.citation_type == CitationType.INTERVIEW:
            return bool(self.interviewee or self.interviewer)
        elif self.citation_type == CitationType.LETTER:
            return bool(self.sender or self.recipient)
        elif self.citation_type == CitationType.NEWSPAPER:
            return bool(self.title or self.url)
        elif self.citation_type == CitationType.GOVERNMENT:
            return bool(self.title or self.url)
        else:  # JOURNAL, BOOK, MEDICAL
            return bool(self.title)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for backward compatibility)."""
        return {
            'type': self.citation_type.name.lower(),
            'raw_source': self.raw_source,
            'source_engine': self.source_engine,
            'title': self.title,
            'authors': self.authors,
            'year': self.year,
            'url': self.url,
            'doi': self.doi,
            'journal': self.journal,
            'volume': self.volume,
            'issue': self.issue,
            'pages': self.pages,
            'pmid': self.pmid,
            'publisher': self.publisher,
            'place': self.place,
            'edition': self.edition,
            'isbn': self.isbn,
            'case_name': self.case_name,
            'citation': self.citation,
            'court': self.court,
            'jurisdiction': self.jurisdiction,
            'neutral_citation': self.neutral_citation,
            'interviewee': self.interviewee,
            'interviewer': self.interviewer,
            'location': self.location,
            'date': self.date,
            'sender': self.sender,
            'recipient': self.recipient,
            'newspaper': self.newspaper,
            'agency': self.agency,
            'document_number': self.document_number,
            'access_date': self.access_date,
            'confidence': self.confidence,
            'raw_data': self.raw_data,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CitationMetadata":
        """Create from dictionary (for backward compatibility with old system)."""
        type_map = {
            'journal': CitationType.JOURNAL,
            'book': CitationType.BOOK,
            'legal': CitationType.LEGAL,
            'interview': CitationType.INTERVIEW,
            'letter': CitationType.LETTER,
            'newspaper': CitationType.NEWSPAPER,
            'government': CitationType.GOVERNMENT,
            'medical': CitationType.MEDICAL,
            'url': CitationType.URL,
        }
        
        return cls(
            citation_type=type_map.get(d.get('type', '').lower(), CitationType.UNKNOWN),
            raw_source=d.get('raw_source', ''),
            source_engine=d.get('source_engine', ''),
            title=d.get('title', ''),
            authors=d.get('authors', []),
            year=d.get('year'),
            url=d.get('url', ''),
            doi=d.get('doi', ''),
            journal=d.get('journal', ''),
            volume=d.get('volume', ''),
            issue=d.get('issue', ''),
            pages=d.get('pages', ''),
            pmid=d.get('pmid', ''),
            publisher=d.get('publisher', ''),
            place=d.get('place', ''),
            edition=d.get('edition', ''),
            isbn=d.get('isbn', ''),
            case_name=d.get('case_name', ''),
            citation=d.get('citation', ''),
            court=d.get('court', ''),
            jurisdiction=d.get('jurisdiction', ''),
            neutral_citation=d.get('neutral_citation', ''),
            interviewee=d.get('interviewee', ''),
            interviewer=d.get('interviewer', ''),
            location=d.get('location', ''),
            date=d.get('date', ''),
            sender=d.get('sender', ''),
            recipient=d.get('recipient', ''),
            newspaper=d.get('newspaper', ''),
            agency=d.get('agency', d.get('author', '')),  # Gov docs use 'author' for agency
            document_number=d.get('document_number', ''),
            access_date=d.get('access_date', ''),
            confidence=d.get('confidence', 1.0),
            raw_data=d.get('raw_data', {}),
        )


@dataclass
class DetectionResult:
    """Result from the detection layer."""
    citation_type: CitationType
    confidence: float = 1.0
    cleaned_query: str = ""  # Cleaned/normalized version of input for searching
    hints: Dict[str, Any] = field(default_factory=dict)  # Type-specific hints for extractors
