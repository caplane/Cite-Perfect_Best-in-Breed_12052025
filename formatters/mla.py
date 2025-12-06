"""
citeflex/formatters/mla.py

MLA (9th edition) citation formatter.
Standard for humanities, especially literature and language studies.
"""

from models import CitationMetadata, CitationType, CitationStyle
from formatters.base import BaseFormatter


class MLAFormatter(BaseFormatter):
    """
    MLA 9th Edition formatter.
    
    Key features:
    - Author names: Last, First format
    - Titles in quotes (articles) or italics (books/journals)
    - Container model (journal is container for article)
    - No "accessed" date unless content might change
    """
    
    style = CitationStyle.MLA
    
    def format(self, metadata: CitationMetadata) -> str:
        """Format a full MLA-style citation."""
        
        if metadata.citation_type == CitationType.LEGAL:
            return self._format_legal(metadata)
        elif metadata.citation_type == CitationType.INTERVIEW:
            return self._format_interview(metadata)
        elif metadata.citation_type == CitationType.LETTER:
            return self._format_letter(metadata)
        elif metadata.citation_type == CitationType.NEWSPAPER:
            return self._format_newspaper(metadata)
        elif metadata.citation_type == CitationType.GOVERNMENT:
            return self._format_government(metadata)
        elif metadata.citation_type == CitationType.BOOK:
            return self._format_book(metadata)
        elif metadata.citation_type in [CitationType.JOURNAL, CitationType.MEDICAL]:
            return self._format_journal(metadata)
        elif metadata.citation_type == CitationType.URL:
            return self._format_url(metadata)
        else:
            return self._format_journal(metadata)
    
    def format_short(self, metadata: CitationMetadata) -> str:
        """MLA short form: (Author Page) or (Author)."""
        parts = []
        
        if metadata.authors:
            last_name = self._get_last_name(metadata.authors[0])
            if len(metadata.authors) > 2:
                parts.append(f"{last_name} et al.")
            elif len(metadata.authors) == 2:
                last_name2 = self._get_last_name(metadata.authors[1])
                parts.append(f"{last_name} and {last_name2}")
            else:
                parts.append(last_name)
        
        result = "(" + " ".join(parts) + ")"
        return self._ensure_period(result)
    
    def _format_authors_mla(self, authors: list) -> str:
        """
        Format authors in MLA style: Last, First.
        
        Rules:
        - 1 author: Last, First.
        - 2 authors: Last, First, and First Last.
        - 3+: Last, First, et al.
        """
        if not authors:
            return ""
        
        def format_first(name: str) -> str:
            """Format first author: Last, First."""
            parts = name.strip().split()
            if len(parts) == 0:
                return ""
            if len(parts) == 1:
                return parts[0]
            if ',' in name:
                return name  # Already formatted
            return f"{parts[-1]}, {' '.join(parts[:-1])}"
        
        def format_other(name: str) -> str:
            """Format subsequent authors: First Last."""
            if ',' in name:
                # Convert "Last, First" to "First Last"
                parts = name.split(',')
                return f"{parts[1].strip()} {parts[0].strip()}"
            return name
        
        if len(authors) == 1:
            return format_first(authors[0])
        elif len(authors) == 2:
            return f"{format_first(authors[0])}, and {format_other(authors[1])}"
        else:
            return f"{format_first(authors[0])}, et al."
    
    # =========================================================================
    # JOURNAL
    # =========================================================================
    
    def _format_journal(self, m: CitationMetadata) -> str:
        """
        MLA journal article.
        
        Pattern: Author. "Title." Container, vol. #, no. #, Year, pp. #-#. DOI.
        """
        parts = []
        
        # Author
        if m.authors:
            parts.append(self._format_authors_mla(m.authors) + ".")
        
        # Title in quotes
        if m.title:
            parts.append(f'"{m.title}."')
        
        # Container (journal) in italics
        container_parts = []
        if m.journal:
            container_parts.append(f"<i>{m.journal}</i>")
        
        # Volume and issue
        if m.volume:
            container_parts.append(f"vol. {m.volume}")
        if m.issue:
            container_parts.append(f"no. {m.issue}")
        
        # Year
        if m.year:
            container_parts.append(m.year)
        
        # Pages
        if m.pages:
            container_parts.append(f"pp. {m.pages}")
        
        if container_parts:
            parts.append(", ".join(container_parts) + ".")
        
        # DOI or URL
        if m.doi:
            parts.append(f"https://doi.org/{m.doi}.")
        elif m.url:
            parts.append(m.url + ".")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # BOOK
    # =========================================================================
    
    def _format_book(self, m: CitationMetadata) -> str:
        """
        MLA book.
        
        Pattern: Author. Title. Edition, Publisher, Year.
        """
        parts = []
        
        # Author
        if m.authors:
            parts.append(self._format_authors_mla(m.authors) + ".")
        
        # Title in italics
        if m.title:
            parts.append(f"<i>{m.title}</i>.")
        
        # Edition
        if m.edition:
            parts.append(m.edition + ",")
        
        # Publisher
        if m.publisher:
            parts.append(m.publisher + ",")
        
        # Year
        if m.year:
            parts.append(m.year + ".")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # LEGAL
    # =========================================================================
    
    def _format_legal(self, m: CitationMetadata) -> str:
        """
        MLA legal case.
        
        Pattern: Case Name. Citation. Court, Year.
        """
        parts = []
        
        # Case name in italics
        if m.case_name:
            parts.append(f"<i>{m.case_name}</i>.")
        
        # Citation
        if m.citation:
            parts.append(m.citation + ".")
        elif m.neutral_citation:
            parts.append(m.neutral_citation + ".")
        
        # Court and Year
        if m.court:
            parts.append(m.court + ",")
        if m.year:
            parts.append(m.year + ".")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # INTERVIEW
    # =========================================================================
    
    def _format_interview(self, m: CitationMetadata) -> str:
        """
        MLA interview.
        
        Pattern: Interviewee. Interview. By Interviewer. Date.
        """
        parts = []
        
        # Interviewee
        if m.interviewee:
            parts.append(self._format_authors_mla([m.interviewee]) + ".")
        
        # Type
        parts.append("Interview.")
        
        # Interviewer
        if m.interviewer:
            parts.append(f"By {m.interviewer}.")
        
        # Date
        if m.date:
            parts.append(m.date + ".")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # LETTER/CORRESPONDENCE
    # =========================================================================
    
    def _format_letter(self, m: CitationMetadata) -> str:
        """
        MLA letter/correspondence.
        
        Pattern: Sender. Letter to Recipient. Date. Collection, Location.
        Or: Sender. "Subject." Letter to Recipient. Date.
        """
        parts = []
        
        # Sender (MLA author format: Last, First)
        if m.sender:
            parts.append(self._format_authors_mla([m.sender]) + ".")
        
        # Subject in quotes (if present)
        if m.title:
            parts.append(f'"{m.title}."')
        
        # Letter description
        if m.recipient:
            parts.append(f"Letter to {m.recipient}.")
        else:
            parts.append("Letter.")
        
        # Date
        if m.date:
            parts.append(m.date + ".")
        
        # Collection/location
        if m.location:
            parts.append(m.location + ".")
        
        # URL
        if m.url:
            parts.append(m.url + ".")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # NEWSPAPER
    # =========================================================================
    
    def _format_newspaper(self, m: CitationMetadata) -> str:
        """
        MLA newspaper article.
        
        Pattern: Author. "Title." Publication, Date, URL.
        """
        parts = []
        
        # Author
        if m.authors:
            parts.append(self._format_authors_mla(m.authors) + ".")
        
        # Title in quotes
        if m.title:
            parts.append(f'"{m.title}."')
        
        # Publication in italics
        pub_name = m.newspaper or getattr(m, 'publication', '')
        if pub_name:
            parts.append(f"<i>{pub_name}</i>,")
        
        # Date
        if m.date:
            parts.append(m.date + ",")
        
        # URL
        if m.url:
            parts.append(m.url + ".")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # GOVERNMENT
    # =========================================================================
    
    def _format_government(self, m: CitationMetadata) -> str:
        """
        MLA government document.
        
        Pattern: Agency. Title. Publisher, Year. URL.
        """
        parts = []
        
        # Agency as author
        if m.agency:
            parts.append(m.agency + ".")
        
        # Title in italics
        if m.title:
            parts.append(f"<i>{m.title}</i>.")
        
        # Publisher (often same as agency)
        if m.publisher and m.publisher != m.agency:
            parts.append(m.publisher + ",")
        
        # Year
        if m.year:
            parts.append(m.year + ".")
        
        # URL
        if m.url:
            parts.append(m.url + ".")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # URL
    # =========================================================================
    
    def _format_url(self, m: CitationMetadata) -> str:
        """
        MLA web page.
        
        Pattern: Author. "Title." Site Name, Date, URL.
        """
        parts = []
        
        # Author
        if m.authors:
            parts.append(self._format_authors_mla(m.authors) + ".")
        
        # Title in quotes
        if m.title:
            parts.append(f'"{m.title}."')
        
        # Date
        if m.date:
            parts.append(m.date + ",")
        elif m.year:
            parts.append(m.year + ",")
        
        # URL
        if m.url:
            parts.append(m.url + ".")
        
        result = " ".join(parts)
        return self._ensure_period(result)
