"""
citeflex/formatters/apa.py

APA (7th edition) citation formatter.
Standard for social sciences and psychology.
"""

from models import CitationMetadata, CitationType, CitationStyle
from formatters.base import BaseFormatter


class APAFormatter(BaseFormatter):
    """
    APA 7th Edition formatter.
    
    Key features:
    - Author names: Last, F. M. format
    - Year in parentheses after author
    - Titles in sentence case
    - Journal names in italics with volume
    """
    
    style = CitationStyle.APA
    
    def format(self, metadata: CitationMetadata) -> str:
        """Format a full APA-style citation."""
        
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
        """Format short APA citation (Author, Year)."""
        parts = []
        
        if metadata.authors:
            last_name = self._get_last_name(metadata.authors[0])
            if len(metadata.authors) == 2:
                last_name2 = self._get_last_name(metadata.authors[1])
                parts.append(f"{last_name} & {last_name2}")
            elif len(metadata.authors) > 2:
                parts.append(f"{last_name} et al.")
            else:
                parts.append(last_name)
        
        if metadata.year:
            parts.append(f"({metadata.year})")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    def _format_authors_apa(self, authors: list) -> str:
        """
        Format authors in APA style: Last, F. M.
        
        Rules:
        - Up to 20 authors: list all
        - 21+: list first 19, ellipsis, last author
        """
        if not authors:
            return ""
        
        def format_one(name: str) -> str:
            """Convert 'First Middle Last' to 'Last, F. M.'"""
            parts = name.strip().split()
            if len(parts) == 0:
                return ""
            if len(parts) == 1:
                return parts[0]
            
            # Check for "Last, First" format already
            if ',' in name:
                return name
            
            last = parts[-1]
            initials = ". ".join(p[0].upper() for p in parts[:-1] if p) + "."
            return f"{last}, {initials}"
        
        formatted = [format_one(a) for a in authors]
        
        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]}, & {formatted[1]}"
        elif len(formatted) <= 20:
            return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
        else:
            # 21+ authors
            first_19 = ", ".join(formatted[:19])
            return f"{first_19}, ... {formatted[-1]}"
    
    # =========================================================================
    # JOURNAL
    # =========================================================================
    
    def _format_journal(self, m: CitationMetadata) -> str:
        """
        APA journal article.
        
        Pattern: Author, A. A. (Year). Title. Journal, Volume(Issue), Pages. DOI
        """
        parts = []
        
        # Authors
        if m.authors:
            parts.append(self._format_authors_apa(m.authors))
        
        # Year
        if m.year:
            parts.append(f"({m.year}).")
        
        # Title (sentence case, no italics)
        if m.title:
            parts.append(m.title + ".")
        
        # Journal (italics), Volume(Issue), Pages
        journal_parts = []
        if m.journal:
            journal_parts.append(f"<i>{m.journal}</i>")
        
        if m.volume:
            vol_str = f"<i>{m.volume}</i>"
            if m.issue:
                vol_str += f"({m.issue})"
            journal_parts.append(vol_str)
        
        if m.pages:
            journal_parts.append(m.pages)
        
        if journal_parts:
            parts.append(", ".join(journal_parts) + ".")
        
        # DOI or URL
        if m.doi:
            parts.append(f"https://doi.org/{m.doi}")
        elif m.url:
            parts.append(m.url)
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # BOOK
    # =========================================================================
    
    def _format_book(self, m: CitationMetadata) -> str:
        """
        APA book.
        
        Pattern: Author, A. A. (Year). Title (Edition). Publisher. DOI
        """
        parts = []
        
        # Authors
        if m.authors:
            parts.append(self._format_authors_apa(m.authors))
        
        # Year
        if m.year:
            parts.append(f"({m.year}).")
        
        # Title in italics
        title_part = f"<i>{m.title}</i>" if m.title else ""
        if m.edition:
            title_part += f" ({m.edition})"
        if title_part:
            parts.append(title_part + ".")
        
        # Publisher
        if m.publisher:
            parts.append(m.publisher + ".")
        
        # DOI or URL
        if m.doi:
            parts.append(f"https://doi.org/{m.doi}")
        elif m.url:
            parts.append(m.url)
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # LEGAL (APA has different legal style from Bluebook)
    # =========================================================================
    
    def _format_legal(self, m: CitationMetadata) -> str:
        """
        APA legal case.
        
        Pattern: Name v. Name, Citation (Court Year).
        """
        parts = []
        
        # Case name (italics in APA)
        if m.case_name:
            parts.append(f"<i>{m.case_name}</i>,")
        
        # Citation
        if m.citation:
            parts.append(m.citation)
        elif m.neutral_citation:
            parts.append(m.neutral_citation)
        
        # Court and Year
        court_year = []
        if m.court:
            court_year.append(m.court)
        if m.year:
            court_year.append(m.year)
        if court_year:
            parts.append(f"({' '.join(court_year)})")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # INTERVIEW
    # =========================================================================
    
    def _format_interview(self, m: CitationMetadata) -> str:
        """
        APA interview (personal communication).
        
        Note: APA doesn't include interviews in reference lists;
        they're cited in-text only. This provides a reference-style format.
        """
        parts = []
        
        # Interviewee as author
        if m.interviewee:
            # Convert to APA author format
            parts.append(self._format_authors_apa([m.interviewee]))
        
        # Year
        if m.year:
            parts.append(f"({m.year}).")
        elif m.date:
            parts.append(f"({m.date}).")
        
        # Type of communication
        parts.append("[Personal interview].")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # LETTER/CORRESPONDENCE
    # =========================================================================
    
    def _format_letter(self, m: CitationMetadata) -> str:
        """
        APA letter (personal communication).
        
        Note: APA treats letters as personal communications, typically
        cited in-text only. This provides a reference-style format.
        
        Pattern: Sender, S. (Date). [Letter to Recipient]. Collection.
        """
        parts = []
        
        # Sender as author
        if m.sender:
            parts.append(self._format_authors_apa([m.sender]))
        
        # Date
        if m.date:
            parts.append(f"({m.date}).")
        elif m.year:
            parts.append(f"({m.year}).")
        
        # Description with recipient
        if m.recipient:
            parts.append(f"[Letter to {m.recipient}].")
        else:
            parts.append("[Personal correspondence].")
        
        # Subject if present
        if m.title:
            parts.append(f'"{m.title}."')
        
        # Collection/location
        if m.location:
            parts.append(m.location + ".")
        
        # URL
        if m.url:
            parts.append(m.url)
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # NEWSPAPER
    # =========================================================================
    
    def _format_newspaper(self, m: CitationMetadata) -> str:
        """
        APA newspaper article.
        
        Pattern: Author, A. A. (Year, Month Day). Title. Publication. URL
        """
        parts = []
        
        # Authors
        if m.authors:
            parts.append(self._format_authors_apa(m.authors))
        
        # Date
        if m.date:
            parts.append(f"({m.date}).")
        elif m.year:
            parts.append(f"({m.year}).")
        
        # Title
        if m.title:
            parts.append(m.title + ".")
        
        # Publication (italics)
        pub_name = m.newspaper or getattr(m, 'publication', '')
        if pub_name:
            parts.append(f"<i>{pub_name}</i>.")
        
        # URL
        if m.url:
            parts.append(m.url)
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # GOVERNMENT
    # =========================================================================
    
    def _format_government(self, m: CitationMetadata) -> str:
        """
        APA government document.
        
        Pattern: Agency. (Year). Title (Publication No.). Publisher. URL
        """
        parts = []
        
        # Agency as author
        if m.agency:
            parts.append(m.agency + ".")
        
        # Year
        if m.year:
            parts.append(f"({m.year}).")
        
        # Title in italics
        if m.title:
            title_part = f"<i>{m.title}</i>"
            if m.document_number:
                title_part += f" ({m.document_number})"
            parts.append(title_part + ".")
        
        # URL
        if m.url:
            parts.append(m.url)
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # URL
    # =========================================================================
    
    def _format_url(self, m: CitationMetadata) -> str:
        """
        APA web page.
        
        Pattern: Author. (Year). Title. Site Name. URL
        """
        parts = []
        
        # Authors or site as author
        if m.authors:
            parts.append(self._format_authors_apa(m.authors))
        
        # Year or n.d.
        if m.year:
            parts.append(f"({m.year}).")
        else:
            parts.append("(n.d.).")
        
        # Title in italics
        if m.title:
            parts.append(f"<i>{m.title}</i>.")
        
        # URL
        if m.url:
            parts.append(m.url)
        
        result = " ".join(parts)
        return self._ensure_period(result)
