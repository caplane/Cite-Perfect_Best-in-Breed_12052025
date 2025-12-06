"""
citeflex/formatters/chicago.py

Chicago Manual of Style (17th ed.) citation formatter.
Supports notes-bibliography format for humanities.
"""

from models import CitationMetadata, CitationType, CitationStyle
from formatters.base import BaseFormatter


class ChicagoFormatter(BaseFormatter):
    """
    Chicago Manual of Style (17th edition) formatter.
    
    Uses notes-bibliography format (N-B), the standard for
    humanities including history, literature, and arts.
    
    Key features:
    - Titles in italics (represented as <i> tags)
    - Full first reference, short subsequent
    - Author names: First Last format
    """
    
    style = CitationStyle.CHICAGO
    
    def format(self, metadata: CitationMetadata) -> str:
        """Format a full Chicago-style citation."""
        
        # Route to type-specific formatter
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
            # Default to journal format
            return self._format_journal(metadata)
    
    def format_short(self, metadata: CitationMetadata) -> str:
        """Format a short Chicago-style citation."""
        
        if metadata.citation_type == CitationType.LEGAL:
            return self._format_legal_short(metadata)
        elif metadata.citation_type == CitationType.INTERVIEW:
            return self._format_interview_short(metadata)
        elif metadata.citation_type == CitationType.LETTER:
            return self._format_letter_short(metadata)
        else:
            return self._format_general_short(metadata)
    
    # =========================================================================
    # JOURNAL/ARTICLE
    # =========================================================================
    
    def _format_journal(self, m: CitationMetadata) -> str:
        """
        Format journal article.
        
        Pattern: Author, "Title," Journal Volume, no. Issue (Year): Pages, URL.
        """
        parts = []
        
        # Authors
        if m.authors:
            parts.append(self._format_authors(m.authors))
        
        # Title in quotes
        if m.title:
            parts.append(f'"{m.title},"')
        
        # Journal in italics
        journal_part = []
        if m.journal:
            journal_part.append(f"<i>{m.journal}</i>")
        
        # Volume and issue
        if m.volume:
            journal_part.append(m.volume)
        if m.issue:
            journal_part.append(f"no. {m.issue}")
        
        # Year
        if m.year:
            journal_part.append(f"({m.year})")
        
        if journal_part:
            parts.append(" ".join(journal_part))
        
        # Pages
        if m.pages:
            parts.append(f": {m.pages}")
        
        # URL/DOI
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
        Format book.
        
        Pattern: Author, Title (Place: Publisher, Year), Pages.
        """
        parts = []
        
        # Authors
        if m.authors:
            parts.append(self._format_authors(m.authors) + ",")
        
        # Title in italics
        if m.title:
            parts.append(f"<i>{m.title}</i>")
        
        # Publication info in parentheses
        pub_parts = []
        if m.place:
            pub_parts.append(m.place)
        if m.publisher:
            pub_parts.append(m.publisher)
        if m.year:
            pub_parts.append(m.year)
        
        if pub_parts:
            if m.place and m.publisher:
                pub_info = f"{m.place}: {m.publisher}, {m.year}" if m.year else f"{m.place}: {m.publisher}"
            elif m.publisher and m.year:
                pub_info = f"{m.publisher}, {m.year}"
            elif m.year:
                pub_info = m.year
            else:
                pub_info = ", ".join(pub_parts)
            parts.append(f"({pub_info})")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # LEGAL
    # =========================================================================
    
    def _format_legal(self, m: CitationMetadata) -> str:
        """
        Format legal case.
        
        Pattern: Case Name, Citation (Court Year).
        """
        parts = []
        
        # Case name in italics
        if m.case_name:
            parts.append(f"<i>{m.case_name}</i>,")
        
        # Citation
        if m.citation:
            parts.append(m.citation)
        elif m.neutral_citation:
            parts.append(m.neutral_citation)
        
        # Court and year
        court_year = []
        if m.court:
            court_year.append(m.court)
        if m.year:
            court_year.append(m.year)
        
        if court_year:
            parts.append(f"({', '.join(court_year)})")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    def _format_legal_short(self, m: CitationMetadata) -> str:
        """Short form legal citation: Case Name at Page."""
        parts = []
        
        if m.case_name:
            # Use shortened case name (first party only)
            short_name = m.case_name.split(' v')[0].split(' v.')[0].strip()
            parts.append(f"<i>{short_name}</i>")
        
        if m.citation:
            # Extract page from citation if possible
            parts.append(f"at {m.citation.split()[-1]}" if m.citation else "")
        
        result = ", ".join(filter(None, parts))
        return self._ensure_period(result)
    
    # =========================================================================
    # INTERVIEW
    # =========================================================================
    
    def _format_interview(self, m: CitationMetadata) -> str:
        """
        Format interview.
        
        Pattern: Interviewee interview [by Interviewer], Date, Location.
        """
        parts = []
        
        # Interviewee
        if m.interviewee:
            parts.append(m.interviewee)
            parts.append("interview")
        elif m.interviewer:
            parts.append("Interview")
        
        # Interviewer
        if m.interviewer:
            parts.append(f"by {m.interviewer}")
        
        # Date
        if m.date:
            parts.append(m.date)
        
        # Location
        if m.location:
            parts.append(m.location)
        
        result = ", ".join(filter(None, parts))
        return self._ensure_period(result)
    
    def _format_interview_short(self, m: CitationMetadata) -> str:
        """Short form interview: Interviewee interview."""
        if m.interviewee:
            return self._ensure_period(f"{m.interviewee} interview")
        return self._ensure_period("Interview")
    
    # =========================================================================
    # LETTER/CORRESPONDENCE
    # =========================================================================
    
    def _format_letter(self, m: CitationMetadata) -> str:
        """
        Format letter/correspondence.
        
        Chicago 17th ed. pattern for personal communications:
        Sender to Recipient, Date, Collection/Location. URL.
        
        With subject: Sender to Recipient, "Subject," Date, Collection. URL.
        """
        parts = []
        
        # Sender to Recipient
        if m.sender and m.recipient:
            parts.append(f"{m.sender} to {m.recipient}")
        elif m.sender:
            parts.append(m.sender)
        elif m.recipient:
            parts.append(f"Letter to {m.recipient}")
        
        # Subject/title in quotes (if present)
        if m.title:
            parts.append(f'"{m.title}"')
        
        # Date
        if m.date:
            parts.append(m.date)
        
        # Location/Collection
        if m.location:
            parts.append(m.location)
        
        # URL
        if m.url:
            parts.append(m.url)
        
        result = ", ".join(filter(None, parts))
        return self._ensure_period(result)
    
    def _format_letter_short(self, m: CitationMetadata) -> str:
        """Short form letter: Sender to Recipient, Date."""
        parts = []
        
        if m.sender and m.recipient:
            # Use last names only for short form
            sender_last = self._get_last_name(m.sender)
            recipient_last = self._get_last_name(m.recipient)
            parts.append(f"{sender_last} to {recipient_last}")
        elif m.sender:
            parts.append(self._get_last_name(m.sender))
        
        if m.date:
            parts.append(m.date)
        
        result = ", ".join(filter(None, parts))
        return self._ensure_period(result)
    
    # =========================================================================
    # NEWSPAPER
    # =========================================================================
    
    def _format_newspaper(self, m: CitationMetadata) -> str:
        """
        Format newspaper article.
        
        Pattern: Author, "Title," Publication, Date, URL.
        """
        parts = []
        
        # Author
        if m.authors:
            parts.append(self._format_authors(m.authors) + ",")
        
        # Title in quotes
        if m.title:
            parts.append(f'"{m.title},"')
        
        # Publication in italics (use newspaper or publication property)
        pub_name = m.newspaper or getattr(m, 'publication', '')
        if pub_name:
            parts.append(f"<i>{pub_name}</i>,")
        
        # Date
        if m.date:
            parts.append(m.date + ",")
        
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
        Format government document.
        
        Pattern: Agency, "Title," URL.
        """
        parts = []
        
        # Agency
        if m.agency:
            parts.append(m.agency + ",")
        
        # Title in quotes
        if m.title:
            parts.append(f'"{m.title},"')
        
        # Document number
        if m.document_number:
            parts.append(m.document_number + ",")
        
        # URL
        if m.url:
            parts.append(m.url)
        
        # Access date
        if m.access_date:
            parts.append(f"accessed {m.access_date}")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # URL (GENERIC)
    # =========================================================================
    
    def _format_url(self, m: CitationMetadata) -> str:
        """
        Format generic URL.
        
        Pattern: "Title," URL, accessed Date.
        """
        parts = []
        
        if m.title:
            parts.append(f'"{m.title},"')
        
        if m.url:
            parts.append(m.url)
        
        if m.access_date:
            parts.append(f"accessed {m.access_date}")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    # =========================================================================
    # SHORT FORM (GENERAL)
    # =========================================================================
    
    def _format_general_short(self, m: CitationMetadata) -> str:
        """
        Short form for articles/books: Last Name, "Short Title."
        """
        parts = []
        
        # First author's last name
        if m.authors:
            last_name = self._get_last_name(m.authors[0])
            if last_name:
                parts.append(last_name + ",")
        
        # Shortened title (first few words)
        if m.title:
            words = m.title.split()
            short_title = " ".join(words[:4])
            if len(words) > 4:
                short_title += "..."
            
            if m.citation_type == CitationType.BOOK:
                parts.append(f"<i>{short_title}</i>")
            else:
                parts.append(f'"{short_title}"')
        
        result = " ".join(parts)
        return self._ensure_period(result)
