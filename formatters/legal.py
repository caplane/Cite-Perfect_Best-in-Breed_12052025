"""
citeflex/formatters/legal.py

Legal citation formatters.
- BluebookFormatter: US legal citation (Bluebook 21st ed.)
- OSCOLAFormatter: UK legal citation (OSCOLA 4th ed.)

Version History:
    2025-12-05 13:05: Fixed OSCOLA _format_case to include year for US cases
                      Pattern: Case Name, Citation (Year) for US; Case Name [Year] for UK
"""

from models import CitationMetadata, CitationType, CitationStyle
from formatters.base import BaseFormatter


class BluebookFormatter(BaseFormatter):
    """
    Bluebook (21st edition) formatter.
    
    Standard for US legal citations.
    
    Key features:
    - Case names in italics (when not used in full caps)
    - Specific abbreviations for reporters and courts
    - Signals and parentheticals for additional info
    """
    
    style = CitationStyle.BLUEBOOK
    
    def format(self, metadata: CitationMetadata) -> str:
        """Format a Bluebook-style citation."""
        
        if metadata.citation_type == CitationType.LEGAL:
            return self._format_case(metadata)
        else:
            # Bluebook also has rules for other sources
            return self._format_other(metadata)
    
    def format_short(self, metadata: CitationMetadata) -> str:
        """Format short Bluebook citation: Case Name at Page."""
        if metadata.citation_type == CitationType.LEGAL:
            return self._format_case_short(metadata)
        return self._format_general_short(metadata)
    
    def _format_case(self, m: CitationMetadata) -> str:
        """
        Bluebook case citation.
        
        Pattern: Case Name, Volume Reporter Page (Court Year).
        Example: Brown v. Board of Education, 347 U.S. 483 (1954).
        """
        parts = []
        
        # Case name in italics
        if m.case_name:
            parts.append(f"<i>{m.case_name}</i>,")
        
        # Citation (Volume Reporter Page)
        if m.citation:
            parts.append(m.citation)
        elif m.neutral_citation:
            parts.append(m.neutral_citation)
        
        # Parenthetical: (Court Year)
        paren_parts = []
        
        # Court abbreviation (but not for Supreme Court in U.S. Reports)
        if m.court and m.citation:
            # Don't include court for U.S. Supreme Court in U.S. Reports
            if 'U.S.' in m.citation and 'Supreme Court' in m.court:
                pass  # Omit court
            else:
                paren_parts.append(m.court)
        
        if m.year:
            paren_parts.append(m.year)
        
        if paren_parts:
            parts.append(f"({' '.join(paren_parts)})")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    def _format_case_short(self, m: CitationMetadata) -> str:
        """
        Bluebook short form case citation.
        
        Pattern: Case Name, Volume Reporter at Pinpoint.
        Example: Brown, 347 U.S. at 495.
        """
        parts = []
        
        # Shortened case name (first party)
        if m.case_name:
            short_name = m.case_name.split(' v')[0].split(' v.')[0].strip()
            # Remove procedural phrases
            for phrase in ['In re ', 'Ex parte ', 'United States v. ', 'State v. ']:
                if m.case_name.startswith(phrase):
                    short_name = m.case_name[len(phrase):].split(' v')[0].split(' v.')[0].strip()
                    break
            parts.append(f"<i>{short_name}</i>,")
        
        # Volume and Reporter
        if m.citation:
            cit_parts = m.citation.split()
            if len(cit_parts) >= 2:
                # Volume Reporter at Page
                parts.append(f"{cit_parts[0]} {cit_parts[1]} at {cit_parts[-1]}")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    def _format_other(self, m: CitationMetadata) -> str:
        """Format non-case sources in Bluebook style."""
        # For non-legal sources, Bluebook follows similar patterns to Chicago
        parts = []
        
        if m.authors:
            parts.append(self._format_authors(m.authors) + ",")
        
        if m.title:
            if m.citation_type == CitationType.BOOK:
                parts.append(f"<i>{m.title}</i>")
            else:
                parts.append(f"<i>{m.title}</i>,")
        
        if m.journal:
            parts.append(f"{m.volume} {m.journal} {m.pages}" if m.volume else m.journal)
        
        if m.year:
            parts.append(f"({m.year})")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    def _format_general_short(self, m: CitationMetadata) -> str:
        """General short form for non-case citations."""
        parts = []
        
        if m.authors:
            last_name = self._get_last_name(m.authors[0])
            parts.append(last_name + ",")
        
        if m.title:
            words = m.title.split()[:3]
            short_title = " ".join(words)
            parts.append(f"<i>{short_title}</i>")
        
        result = " ".join(parts)
        return self._ensure_period(result)


class OSCOLAFormatter(BaseFormatter):
    """
    OSCOLA (4th edition) formatter.
    
    Oxford University Standard for Citation of Legal Authorities.
    Standard for UK legal citations.
    
    Key features:
    - Case names in italics
    - Neutral citations preferred (e.g., [2020] UKSC 1)
    - No full stop at end of case citations
    - Footnote-style formatting
    """
    
    style = CitationStyle.OSCOLA
    
    def format(self, metadata: CitationMetadata) -> str:
        """Format an OSCOLA-style citation."""
        
        if metadata.citation_type == CitationType.LEGAL:
            return self._format_case(metadata)
        else:
            return self._format_other(metadata)
    
    def format_short(self, metadata: CitationMetadata) -> str:
        """Format short OSCOLA citation."""
        if metadata.citation_type == CitationType.LEGAL:
            return self._format_case_short(metadata)
        return self._format_general_short(metadata)
    
    def _format_case(self, m: CitationMetadata) -> str:
        """
        OSCOLA case citation.
        
        UK Pattern: Case Name [Year] Court Number
        Example: R v Brown [1994] 1 AC 212
        
        US Pattern: Case Name, Citation (Year)
        Example: Loving v Virginia, 388 U.S. 1 (1967)
        
        Note: OSCOLA traditionally doesn't end case citations with a period,
        but we apply _ensure_period for consistency across the system.
        """
        parts = []
        
        # Case name in italics (no comma after in OSCOLA for UK)
        if m.case_name:
            parts.append(f"<i>{m.case_name}</i>")
        
        # UK neutral citation (already includes year in [Year] format)
        if m.neutral_citation:
            parts.append(m.neutral_citation)
        elif m.citation:
            # US-style citation - add year in parentheses
            parts.append(m.citation)
            if m.year:
                parts.append(f"({m.year})")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    def _format_case_short(self, m: CitationMetadata) -> str:
        """
        OSCOLA short form case citation.
        
        Pattern: Case Name (n X)
        Where X is the footnote number (we use "above" as placeholder)
        """
        parts = []
        
        # Shortened case name
        if m.case_name:
            short_name = m.case_name.split(' v ')[0].strip()
            # Handle R v cases
            if m.case_name.startswith('R v '):
                short_name = m.case_name.split(' v ')[1].split()[0] if ' v ' in m.case_name else m.case_name
            parts.append(f"<i>{short_name}</i>")
        
        parts.append("(n above)")
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    def _format_other(self, m: CitationMetadata) -> str:
        """Format non-case sources in OSCOLA style."""
        parts = []
        
        # Authors (First Last format)
        if m.authors:
            parts.append(self._format_authors(m.authors) + ",")
        
        # Title
        if m.title:
            if m.citation_type == CitationType.BOOK:
                parts.append(f"<i>{m.title}</i>")
            elif m.citation_type == CitationType.JOURNAL:
                parts.append(f"'{m.title}'")
            else:
                parts.append(f"'{m.title}'")
        
        # Publication info
        if m.citation_type == CitationType.BOOK:
            pub_parts = []
            if m.publisher:
                pub_parts.append(m.publisher)
            if m.year:
                pub_parts.append(m.year)
            if pub_parts:
                parts.append(f"({', '.join(pub_parts)})")
        elif m.journal:
            # Journal: [Year] Volume Journal FirstPage
            journal_cite = []
            if m.year:
                journal_cite.append(f"[{m.year}]")
            if m.volume:
                journal_cite.append(m.volume)
            journal_cite.append(m.journal)
            if m.pages:
                first_page = m.pages.split('-')[0].split('–')[0]
                journal_cite.append(first_page)
            parts.append(" ".join(journal_cite))
        
        result = " ".join(parts)
        return self._ensure_period(result)
    
    def _format_general_short(self, m: CitationMetadata) -> str:
        """General short form: Author (n above)."""
        parts = []
        
        if m.authors:
            last_name = self._get_last_name(m.authors[0])
            parts.append(last_name)
        
        parts.append("(n above)")
        
        result = " ".join(parts)
        return self._ensure_period(result)
