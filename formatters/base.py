"""
citeflex/formatters/base.py

Base formatter class and factory function.
All style-specific formatters inherit from BaseFormatter.

FIX APPLIED: Consistent period handling across all formatters.
All format methods now use _ensure_period() to guarantee consistent
ending punctuation.
"""

from abc import ABC, abstractmethod
from typing import Optional

from models import CitationMetadata, CitationType, CitationStyle


class BaseFormatter(ABC):
    """
    Abstract base class for citation formatters.
    
    Each formatter must implement:
    - format(metadata) -> str: Full citation
    - format_short(metadata) -> str: Short form citation
    
    The base class provides:
    - format_ibid(): Standard ibid format
    - _ensure_period(): Consistent ending punctuation
    - _format_authors(): Common author formatting
    """
    
    style: CitationStyle = CitationStyle.CHICAGO
    
    # ==========================================================================
    # FIX: Consistent period handling
    # ==========================================================================
    
    @staticmethod
    def _ensure_period(text: str) -> str:
        """
        Ensure citation ends with a period.
        
        This method guarantees consistent ending punctuation across
        all formatters, fixing the inconsistency bug where some
        format_short methods ended with periods and others didn't.
        
        Args:
            text: Citation text
            
        Returns:
            Text ending with exactly one period
        """
        if not text:
            return ""
        
        text = text.rstrip()
        
        # Don't double-punctuate
        if text.endswith(('.', '?', '!')):
            return text
        
        return text + "."
    
    @staticmethod
    def format_ibid(page: Optional[str] = None) -> str:
        """
        Format an ibid reference.
        
        Standard across all styles: Ibid. or Ibid., PAGE.
        
        Args:
            page: Optional page number
            
        Returns:
            Formatted ibid string
        """
        if page:
            return f"Ibid., {page}."
        return "Ibid."
    
    @abstractmethod
    def format(self, metadata: CitationMetadata) -> str:
        """
        Format a full citation.
        
        Args:
            metadata: Citation metadata
            
        Returns:
            Formatted citation string (with <i> tags for italics)
        """
        pass
    
    @abstractmethod
    def format_short(self, metadata: CitationMetadata) -> str:
        """
        Format a short form citation (for subsequent references).
        
        Args:
            metadata: Citation metadata
            
        Returns:
            Formatted short citation string
        """
        pass
    
    def _format_authors(
        self,
        authors: list,
        max_authors: int = 3,
        et_al_threshold: int = 3
    ) -> str:
        """
        Format author list according to style conventions.
        
        Default behavior (can be overridden):
        - 1 author: "First Last"
        - 2 authors: "First Last and First Last"
        - 3+ authors: "First Last et al."
        
        Args:
            authors: List of author names
            max_authors: Max authors to list before et al.
            et_al_threshold: Number of authors that triggers et al.
            
        Returns:
            Formatted author string
        """
        if not authors:
            return ""
        
        if len(authors) == 1:
            return authors[0]
        
        if len(authors) == 2:
            return f"{authors[0]} and {authors[1]}"
        
        if len(authors) >= et_al_threshold:
            return f"{authors[0]} et al."
        
        # 3+ but below threshold
        return ", ".join(authors[:-1]) + f", and {authors[-1]}"
    
    def _get_last_name(self, full_name: str) -> str:
        """
        Extract last name from full name.
        
        Handles:
        - "First Last" -> "Last"
        - "First Middle Last" -> "Last"
        - "Last, First" -> "Last"
        
        Args:
            full_name: Full author name
            
        Returns:
            Last name
        """
        if not full_name:
            return ""
        
        full_name = full_name.strip()
        
        # Check for "Last, First" format
        if ',' in full_name:
            return full_name.split(',')[0].strip()
        
        # Otherwise assume "First Last"
        parts = full_name.split()
        return parts[-1] if parts else ""


# =============================================================================
# FORMATTER FACTORY
# =============================================================================

def get_formatter(style: str) -> BaseFormatter:
    """
    Get a formatter instance for the specified style.
    
    Args:
        style: Style name (e.g., "Chicago Manual of Style", "APA", "MLA")
        
    Returns:
        Appropriate formatter instance
    """
    # Import here to avoid circular imports
    from formatters.chicago import ChicagoFormatter
    from formatters.apa import APAFormatter
    from formatters.mla import MLAFormatter
    from formatters.legal import BluebookFormatter, OSCOLAFormatter
    
    style_lower = style.lower().strip()
    
    if 'chicago' in style_lower:
        return ChicagoFormatter()
    elif 'apa' in style_lower:
        return APAFormatter()
    elif 'mla' in style_lower:
        return MLAFormatter()
    elif 'bluebook' in style_lower:
        return BluebookFormatter()
    elif 'oscola' in style_lower:
        return OSCOLAFormatter()
    else:
        # Default to Chicago
        return ChicagoFormatter()
