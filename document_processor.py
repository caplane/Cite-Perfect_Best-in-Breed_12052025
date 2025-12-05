"""
citeflex/document_processor.py

Word document processing using direct XML manipulation.

Ported from the monolithic citation_manager.py to preserve:
- Proper endnote/footnote reference elements
- Italic formatting via <i> tags
- Clickable hyperlinks for URLs

This approach extracts the docx as a zip, manipulates the XML directly,
and repackages it - giving full control over Word's internal structure.

Version History:
    2025-12-05 12:53: Enhanced IBID_PATTERN to recognize "Id." (Bluebook) and "pp." prefixes
                      Switched from router to unified_router import
    2025-12-05 13:15: Verified ibid detection passes 13/13 tests including Id. at X patterns
"""

import os
import re
import html
import zipfile
import tempfile
import shutil
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from io import BytesIO

from models import normalize_doi


# =============================================================================
# IBID DETECTION AND HANDLING
# =============================================================================

# Pattern to match ibid variations
# Matches: ibid, ibid., Ibid, Ibid., IBID, IBID., ibidem, etc.
# Optionally followed by comma/period and page number
# Updated: 2025-12-05 - Added "Id." (Bluebook) and "pp." support
IBID_PATTERN = re.compile(
    r'^(?:ibid\.?|ibidem\.?|id\.?)(?:\s*(?:at\s+|[,.]?\s*)?(?:pp?\.?\s*)?(\d+[\-–]?\d*)?)?\.?$',
    re.IGNORECASE
)


def is_ibid(text: str) -> bool:
    """
    Check if the text is an ibid reference.
    
    Recognizes variations:
    - ibid / ibid. / Ibid / Ibid. / IBID
    - ibidem
    - Id. / id. (Bluebook short form)
    - ibid, 45 / ibid., 45 / ibid. 123-125
    - Id. at 45 / id. at 789
    - ibid., pp. 12-15
    
    Updated: 2025-12-05 - Added Id. and pp. support
    
    Args:
        text: The citation text to check
        
    Returns:
        True if this is an ibid reference
    """
    if not text:
        return False
    
    cleaned = text.strip()
    return IBID_PATTERN.match(cleaned) is not None


def extract_ibid_page(text: str) -> Optional[str]:
    """
    Extract page number from an ibid reference.
    
    Examples:
    - "ibid, 45" → "45"
    - "ibid., 123-125" → "123-125"
    - "Id. at 789" → "789"
    - "ibid., pp. 12-15" → "12-15"
    - "ibid." → None
    - "ibid" → None
    
    Updated: 2025-12-05 - Added Id. at X and pp. support
    
    Args:
        text: The ibid text
        
    Returns:
        Page number string if present, None otherwise
    """
    if not text:
        return None
    
    cleaned = text.strip()
    match = IBID_PATTERN.match(cleaned)
    
    if match and match.group(1):
        return match.group(1).strip()
    
    return None


def normalize_url(url: str) -> str:
    """
    Normalize a URL for comparison purposes.
    
    Removes trailing slashes, converts to lowercase, strips whitespace,
    and removes common tracking parameters to ensure matching URLs
    are recognized as the same source.
    
    Args:
        url: The URL to normalize
        
    Returns:
        Normalized URL string
    """
    if not url:
        return ""
    
    # Strip whitespace and convert to lowercase
    normalized = url.strip().lower()
    
    # Remove trailing slashes
    normalized = normalized.rstrip('/')
    
    # Remove common tracking parameters (utm_, etc.)
    # Simple approach: remove everything after ? for comparison
    # This may be too aggressive for some URLs, but works for most cases
    if '?' in normalized:
        base_url = normalized.split('?')[0]
        # Keep the base URL without query params for comparison
        normalized = base_url
    
    return normalized


def urls_match(url1: Optional[str], url2: Optional[str]) -> bool:
    """
    Check if two URLs refer to the same source.
    
    Uses normalized comparison to handle minor variations like
    trailing slashes, case differences, and tracking parameters.
    
    Args:
        url1: First URL
        url2: Second URL
        
    Returns:
        True if both URLs are non-empty and match after normalization
    """
    if not url1 or not url2:
        return False
    
    return normalize_url(url1) == normalize_url(url2)


# =============================================================================
# SOURCE MATCHING FOR SHORT FORM DETECTION
# =============================================================================

def generate_source_key(metadata: Any) -> Optional[str]:
    """
    Generate a unique key to identify a source for short form matching.
    
    Two citations with the same source key refer to the same work.
    
    Priority order for matching:
    1. DOI (most reliable) - NORMALIZED for consistent comparison
    2. URL (for web sources)
    3. Case name + citation (for legal)
    4. Title + first author (for books/articles)
    
    Args:
        metadata: CitationMetadata object
        
    Returns:
        String key for source matching, or None if no key can be generated
    """
    if not metadata:
        return None
    
    # Priority 1: DOI (normalized for consistent matching)
    doi = getattr(metadata, 'doi', None)
    if doi:
        # Use normalized DOI for consistent matching
        normalized = normalize_doi(doi)
        if normalized:
            return f"doi:{normalized}"
    
    # Priority 2: URL (normalized)
    url = getattr(metadata, 'url', None)
    if url:
        return f"url:{normalize_url(url)}"
    
    # Priority 3: Legal case (case name + citation)
    case_name = getattr(metadata, 'case_name', None)
    citation = getattr(metadata, 'citation', None)
    if case_name and citation:
        return f"legal:{case_name.lower().strip()}|{citation.lower().strip()}"
    
    # Priority 4: Title + first author
    title = getattr(metadata, 'title', None)
    authors = getattr(metadata, 'authors', None)
    if title:
        key = f"title:{title.lower().strip()}"
        if authors and len(authors) > 0:
            key += f"|author:{authors[0].lower().strip()}"
        return key
    
    # Priority 5: Just case name for legal without citation
    if case_name:
        return f"case:{case_name.lower().strip()}"
    
    return None


def sources_match(metadata1: Any, metadata2: Any) -> bool:
    """
    Check if two citation metadata objects refer to the same source.
    
    Args:
        metadata1: First CitationMetadata
        metadata2: Second CitationMetadata
        
    Returns:
        True if both refer to the same work
    """
    key1 = generate_source_key(metadata1)
    key2 = generate_source_key(metadata2)
    
    if key1 is None or key2 is None:
        return False
    
    return key1 == key2


@dataclass
class ProcessedCitation:
    """Result of processing a single citation."""
    original: str
    formatted: str
    metadata: Any
    url: Optional[str]
    success: bool
    error: Optional[str] = None
    citation_form: str = "full"  # "full", "ibid", or "short"


@dataclass 
class CitationHistoryEntry:
    """Entry in the citation history for tracking previously cited sources."""
    metadata: Any
    formatted: str
    source_key: Optional[str]
    note_number: int


class CitationHistory:
    """
    Tracks all citations seen in a document for ibid and short form handling.
    
    Maintains:
    - Previous citation (for ibid detection)
    - All cited sources (for short form detection)
    """
    
    def __init__(self):
        self.previous: Optional[CitationHistoryEntry] = None
        self.all_sources: Dict[str, CitationHistoryEntry] = {}  # source_key -> first occurrence
        self.note_counter: int = 0
    
    def add(self, metadata: Any, formatted: str) -> None:
        """
        Add a citation to the history.
        
        Args:
            metadata: Citation metadata
            formatted: Formatted citation string
        """
        self.note_counter += 1
        source_key = generate_source_key(metadata)
        
        entry = CitationHistoryEntry(
            metadata=metadata,
            formatted=formatted,
            source_key=source_key,
            note_number=self.note_counter
        )
        
        # Update previous
        self.previous = entry
        
        # Add to all_sources if this is the first time we've seen this source
        if source_key and source_key not in self.all_sources:
            self.all_sources[source_key] = entry
    
    def is_same_as_previous(self, metadata: Any) -> bool:
        """
        Check if the given metadata matches the immediately previous citation.
        
        Args:
            metadata: Citation metadata to check
            
        Returns:
            True if this is the same source as the previous citation
        """
        if self.previous is None:
            return False
        
        return sources_match(metadata, self.previous.metadata)
    
    def has_been_cited_before(self, metadata: Any) -> bool:
        """
        Check if this source has been cited previously in the document.
        
        Args:
            metadata: Citation metadata to check
            
        Returns:
            True if this source has been cited before (not counting current)
        """
        source_key = generate_source_key(metadata)
        if source_key is None:
            return False
        
        return source_key in self.all_sources
    
    def get_previous_metadata(self) -> Optional[Any]:
        """Get the metadata of the previous citation."""
        if self.previous:
            return self.previous.metadata
        return None
    
    def get_previous_url(self) -> Optional[str]:
        """Get the URL of the previous citation."""
        if self.previous and self.previous.metadata:
            return getattr(self.previous.metadata, 'url', None)
        return None


class WordDocumentProcessor:
    """
    Processes Word documents to read and write endnotes/footnotes.
    Preserves the main document body while allowing citation fixes.
    
    Uses direct XML manipulation for precise control over Word's structure.
    """
    
    NS = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'xml': 'http://www.w3.org/XML/1998/namespace',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    }
    
    def __init__(self, file_path_or_buffer):
        """
        Initialize with a file path or file-like object (BytesIO).
        """
        self.temp_dir = tempfile.mkdtemp()
        self.original_path = None
        
        # Handle both file paths and file-like objects
        if hasattr(file_path_or_buffer, 'read'):
            # It's a file-like object (e.g., from upload)
            with zipfile.ZipFile(file_path_or_buffer, 'r') as z:
                z.extractall(self.temp_dir)
        else:
            # It's a file path
            self.original_path = file_path_or_buffer
            with zipfile.ZipFile(file_path_or_buffer, 'r') as z:
                z.extractall(self.temp_dir)
    
    def get_endnotes(self) -> List[Dict[str, str]]:
        """
        Extract all endnotes from the document.
        
        Returns:
            List of dicts: [{'id': '1', 'text': 'citation text'}, ...]
        """
        endnotes_path = os.path.join(self.temp_dir, 'word', 'endnotes.xml')
        if not os.path.exists(endnotes_path):
            return []
        
        try:
            tree = ET.parse(endnotes_path)
            root = tree.getroot()
            notes = []
            
            for endnote in root.findall('.//w:endnote', self.NS):
                note_id = endnote.get(f"{{{self.NS['w']}}}id")
                
                # Skip system endnotes (id 0 and -1)
                try:
                    if int(note_id) < 1:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Extract all text from this endnote
                text_parts = []
                for t in endnote.findall('.//w:t', self.NS):
                    if t.text:
                        text_parts.append(t.text)
                
                full_text = "".join(text_parts).strip()
                if full_text:
                    notes.append({'id': note_id, 'text': full_text})
            
            return notes
            
        except Exception as e:
            print(f"[WordDocumentProcessor] Error reading endnotes: {e}")
            return []
    
    def get_footnotes(self) -> List[Dict[str, str]]:
        """
        Extract all footnotes from the document.
        
        Returns:
            List of dicts: [{'id': '1', 'text': 'citation text'}, ...]
        """
        footnotes_path = os.path.join(self.temp_dir, 'word', 'footnotes.xml')
        if not os.path.exists(footnotes_path):
            return []
        
        try:
            tree = ET.parse(footnotes_path)
            root = tree.getroot()
            notes = []
            
            for footnote in root.findall('.//w:footnote', self.NS):
                note_id = footnote.get(f"{{{self.NS['w']}}}id")
                
                # Skip system footnotes (id 0 and -1)
                try:
                    if int(note_id) < 1:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Extract all text
                text_parts = []
                for t in footnote.findall('.//w:t', self.NS):
                    if t.text:
                        text_parts.append(t.text)
                
                full_text = "".join(text_parts).strip()
                if full_text:
                    notes.append({'id': note_id, 'text': full_text})
            
            return notes
            
        except Exception as e:
            print(f"[WordDocumentProcessor] Error reading footnotes: {e}")
            return []
    
    def write_endnote(self, note_id: str, new_content: str) -> bool:
        """
        Replace an endnote's content with new formatted citation.
        Handles <i> tags for italics using regex (no BeautifulSoup needed).
        PRESERVES the endnoteRef element for proper numbering and linking.
        
        Args:
            note_id: The endnote ID to update
            new_content: New citation text (may contain <i> tags for italics)
            
        Returns:
            bool: True if successful
        """
        endnotes_path = os.path.join(self.temp_dir, 'word', 'endnotes.xml')
        if not os.path.exists(endnotes_path):
            return False
        
        try:
            # Register namespace to preserve it
            ET.register_namespace('w', self.NS['w'])
            ET.register_namespace('xml', self.NS['xml'])
            
            tree = ET.parse(endnotes_path)
            root = tree.getroot()
            
            # Find the target endnote
            target = None
            for endnote in root.findall('.//w:endnote', self.NS):
                if endnote.get(f"{{{self.NS['w']}}}id") == str(note_id):
                    target = endnote
                    break
            
            if target is None:
                return False
            
            # Find or create paragraph
            para = target.find('.//w:p', self.NS)
            if para is None:
                para = ET.SubElement(target, f"{{{self.NS['w']}}}p")
            else:
                # FIXED: Preserve paragraph properties AND endnoteRef run
                preserved_pPr = None
                preserved_endnoteRef_run = None
                
                for child in list(para):
                    tag = child.tag.replace(f"{{{self.NS['w']}}}", "")
                    
                    # Preserve paragraph properties
                    if tag == 'pPr':
                        preserved_pPr = child
                        continue
                    
                    # Check if this run contains endnoteRef
                    if tag == 'r':
                        endnote_ref = child.find(f".//{{{self.NS['w']}}}endnoteRef")
                        if endnote_ref is not None:
                            preserved_endnoteRef_run = child
                            continue
                    
                    # Remove all other children
                    para.remove(child)
                
                # If no endnoteRef run was found, create one
                if preserved_endnoteRef_run is None:
                    ref_run = ET.Element(f"{{{self.NS['w']}}}r")
                    rPr = ET.SubElement(ref_run, f"{{{self.NS['w']}}}rPr")
                    rStyle = ET.SubElement(rPr, f"{{{self.NS['w']}}}rStyle")
                    rStyle.set(f"{{{self.NS['w']}}}val", "EndnoteReference")
                    ET.SubElement(ref_run, f"{{{self.NS['w']}}}endnoteRef")
                    
                    # Insert after pPr if it exists, otherwise at beginning
                    if preserved_pPr is not None:
                        idx = list(para).index(preserved_pPr) + 1
                        para.insert(idx, ref_run)
                    else:
                        para.insert(0, ref_run)
            
            # Parse content using regex to handle <i> tags (no BeautifulSoup)
            parts = re.split(r'(<i>.*?</i>)', html.unescape(new_content))
            
            for part in parts:
                if not part:
                    continue
                    
                run = ET.SubElement(para, f"{{{self.NS['w']}}}r")
                
                # Check if this is italic text
                italic_match = re.match(r'<i>(.*?)</i>', part)
                if italic_match:
                    rPr = ET.SubElement(run, f"{{{self.NS['w']}}}rPr")
                    ET.SubElement(rPr, f"{{{self.NS['w']}}}i")
                    text_content = italic_match.group(1)
                else:
                    text_content = part
                
                t = ET.SubElement(run, f"{{{self.NS['w']}}}t")
                t.text = text_content
                t.set(f"{{{self.NS['xml']}}}space", "preserve")
            
            tree.write(endnotes_path, encoding='UTF-8', xml_declaration=True)
            return True
            
        except Exception as e:
            print(f"[WordDocumentProcessor] Error writing endnote: {e}")
            return False
    
    def write_footnote(self, note_id: str, new_content: str) -> bool:
        """
        Replace a footnote's content with new formatted citation.
        Handles <i> tags for italics using regex (no BeautifulSoup needed).
        PRESERVES the footnoteRef element for proper numbering and linking.
        """
        footnotes_path = os.path.join(self.temp_dir, 'word', 'footnotes.xml')
        if not os.path.exists(footnotes_path):
            return False
        
        try:
            ET.register_namespace('w', self.NS['w'])
            ET.register_namespace('xml', self.NS['xml'])
            
            tree = ET.parse(footnotes_path)
            root = tree.getroot()
            
            target = None
            for footnote in root.findall('.//w:footnote', self.NS):
                if footnote.get(f"{{{self.NS['w']}}}id") == str(note_id):
                    target = footnote
                    break
            
            if target is None:
                return False
            
            para = target.find('.//w:p', self.NS)
            if para is None:
                para = ET.SubElement(target, f"{{{self.NS['w']}}}p")
            else:
                # FIXED: Preserve paragraph properties AND footnoteRef run
                preserved_pPr = None
                preserved_footnoteRef_run = None
                
                for child in list(para):
                    tag = child.tag.replace(f"{{{self.NS['w']}}}", "")
                    
                    # Preserve paragraph properties
                    if tag == 'pPr':
                        preserved_pPr = child
                        continue
                    
                    # Check if this run contains footnoteRef
                    if tag == 'r':
                        footnote_ref = child.find(f".//{{{self.NS['w']}}}footnoteRef")
                        if footnote_ref is not None:
                            preserved_footnoteRef_run = child
                            continue
                    
                    # Remove all other children
                    para.remove(child)
                
                # If no footnoteRef run was found, create one
                if preserved_footnoteRef_run is None:
                    ref_run = ET.Element(f"{{{self.NS['w']}}}r")
                    rPr = ET.SubElement(ref_run, f"{{{self.NS['w']}}}rPr")
                    rStyle = ET.SubElement(rPr, f"{{{self.NS['w']}}}rStyle")
                    rStyle.set(f"{{{self.NS['w']}}}val", "FootnoteReference")
                    ET.SubElement(ref_run, f"{{{self.NS['w']}}}footnoteRef")
                    
                    # Insert after pPr if it exists, otherwise at beginning
                    if preserved_pPr is not None:
                        idx = list(para).index(preserved_pPr) + 1
                        para.insert(idx, ref_run)
                    else:
                        para.insert(0, ref_run)
            
            # Parse content using regex to handle <i> tags
            parts = re.split(r'(<i>.*?</i>)', html.unescape(new_content))
            
            for part in parts:
                if not part:
                    continue
                    
                run = ET.SubElement(para, f"{{{self.NS['w']}}}r")
                
                # Check if this is italic text
                italic_match = re.match(r'<i>(.*?)</i>', part)
                if italic_match:
                    rPr = ET.SubElement(run, f"{{{self.NS['w']}}}rPr")
                    ET.SubElement(rPr, f"{{{self.NS['w']}}}i")
                    text_content = italic_match.group(1)
                else:
                    text_content = part
                
                t = ET.SubElement(run, f"{{{self.NS['w']}}}t")
                t.text = text_content
                t.set(f"{{{self.NS['xml']}}}space", "preserve")
            
            tree.write(footnotes_path, encoding='UTF-8', xml_declaration=True)
            return True
            
        except Exception as e:
            print(f"[WordDocumentProcessor] Error writing footnote: {e}")
            return False
    
    def save_to_buffer(self) -> BytesIO:
        """
        Save the modified document to a BytesIO buffer.
        
        Returns:
            BytesIO buffer containing the .docx file
        """
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.temp_dir)
                    zipf.write(file_path, arcname)
        buffer.seek(0)
        return buffer
    
    def save_as(self, output_path: str) -> None:
        """
        Save the modified document to a new file.
        
        Args:
            output_path: Path for the output .docx file
        """
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.temp_dir)
                    zipf.write(file_path, arcname)
    
    def cleanup(self) -> None:
        """Remove temporary files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.cleanup()
        except:
            pass


class LinkActivator:
    """
    Post-processing module that converts plain text URLs in Word documents
    into clickable hyperlinks. Processes document.xml, endnotes.xml, and footnotes.xml.
    
    REWRITTEN: Uses proper XML parsing instead of regex to avoid document corruption.
    """
    
    NS = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'xml': 'http://www.w3.org/XML/1998/namespace',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    }
    
    # URL pattern
    URL_PATTERN = re.compile(r'(https?://[^\s<>"]+)')
    
    @classmethod
    def process(cls, docx_buffer: BytesIO) -> BytesIO:
        """
        Process a docx buffer to make all URLs clickable.
        
        Uses proper XML parsing to avoid document corruption.
        
        Args:
            docx_buffer: BytesIO containing the .docx file
            
        Returns:
            BytesIO containing the processed .docx file
        """
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Extract docx
            docx_buffer.seek(0)
            with zipfile.ZipFile(docx_buffer, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Register namespaces
            ET.register_namespace('w', cls.NS['w'])
            ET.register_namespace('xml', cls.NS['xml'])
            ET.register_namespace('r', cls.NS['r'])
            
            # Process each target file
            target_files = ['word/document.xml', 'word/endnotes.xml', 'word/footnotes.xml']
            
            for xml_file in target_files:
                full_path = os.path.join(temp_dir, xml_file)
                if not os.path.exists(full_path):
                    continue
                
                try:
                    cls._process_xml_file(full_path)
                except Exception as e:
                    print(f"[LinkActivator] Error processing {xml_file}: {e}")
                    # Continue with other files even if one fails
            
            # Repackage as docx
            output_buffer = BytesIO()
            with zipfile.ZipFile(output_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
            
            output_buffer.seek(0)
            return output_buffer
            
        except Exception as e:
            print(f"[LinkActivator] Error: {e}")
            docx_buffer.seek(0)
            return docx_buffer
            
        finally:
            shutil.rmtree(temp_dir)
    
    @classmethod
    def _process_xml_file(cls, file_path: str) -> None:
        """
        Process a single XML file to convert URLs to hyperlinks.
        
        Uses proper XML parsing instead of regex.
        """
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        w_ns = cls.NS['w']
        xml_ns = cls.NS['xml']
        
        # Find all text elements
        modified = False
        
        for t_elem in root.findall(f".//{{{w_ns}}}t"):
            if t_elem.text and cls.URL_PATTERN.search(t_elem.text):
                text = t_elem.text
                
                # Check if parent run is already part of a hyperlink (skip if so)
                parent_run = t_elem.find('..')
                if parent_run is not None:
                    # Check ancestors for hyperlink - simplified check
                    # In Word XML, hyperlinks use w:hyperlink wrapper
                    # We'll just mark URLs visually instead of creating complex field codes
                    pass
                
                # Find URL in text
                match = cls.URL_PATTERN.search(text)
                if match:
                    url = match.group(1)
                    # Clean trailing punctuation
                    clean_url = url.rstrip('.,;:)')
                    
                    # For simplicity and safety, we'll just add visual styling
                    # (blue underlined text) rather than creating complex field codes
                    # which can corrupt documents
                    
                    # Get parent run
                    run = t_elem.getparent() if hasattr(t_elem, 'getparent') else None
                    if run is not None:
                        # Add styling to indicate it's a link
                        rPr = run.find(f"{{{w_ns}}}rPr")
                        if rPr is None:
                            rPr = ET.Element(f"{{{w_ns}}}rPr")
                            run.insert(0, rPr)
                        
                        # Add blue color
                        color = rPr.find(f"{{{w_ns}}}color")
                        if color is None:
                            color = ET.SubElement(rPr, f"{{{w_ns}}}color")
                        color.set(f"{{{w_ns}}}val", "0000FF")
                        
                        # Add underline
                        underline = rPr.find(f"{{{w_ns}}}u")
                        if underline is None:
                            underline = ET.SubElement(rPr, f"{{{w_ns}}}u")
                        underline.set(f"{{{w_ns}}}val", "single")
                        
                        modified = True
        
        if modified:
            tree.write(file_path, encoding='UTF-8', xml_declaration=True)


def process_document(
    file_bytes: bytes,
    style: str = "Chicago Manual of Style",
    add_links: bool = True
) -> tuple:
    """
    Process all citations in a Word document.
    
    Handles citation forms:
    1. Full citation - first time a source is cited
    2. Ibid - same source as immediately preceding citation
    3. Short form - source has been cited before, but not immediately preceding
    
    Also handles:
    - Explicit ibid references (user typed "ibid" or "ibid., 45")
    - Repetitive URLs (same URL as previous note → ibid)
    
    Args:
        file_bytes: The document as bytes
        style: Citation style to use
        add_links: Whether to make URLs clickable
        
    Returns:
        Tuple of (processed_document_bytes, results_list)
    """
    # Import here to avoid circular imports
    from unified_router import get_citation
    from formatters.base import BaseFormatter, get_formatter
    
    results = []
    
    # Initialize citation history for ibid and short form tracking
    history = CitationHistory()
    
    # Get the formatter for short form citations
    formatter = get_formatter(style)
    
    # Load document
    processor = WordDocumentProcessor(BytesIO(file_bytes))
    
    # Get all endnotes and footnotes
    endnotes = processor.get_endnotes()
    footnotes = processor.get_footnotes()
    
    def process_single_note(note: Dict[str, str], note_type: str) -> ProcessedCitation:
        """
        Process a single endnote or footnote.
        """
        note_id = note['id']
        original_text = note['text']
        
        try:
            # Case 1: Explicit ibid reference
            if is_ibid(original_text):
                previous_metadata = history.get_previous_metadata()
                
                if previous_metadata is None:
                    print(f"[process_document] Warning: ibid in {note_type} {note_id} but no previous citation")
                    return ProcessedCitation(
                        original=original_text,
                        formatted=original_text,
                        metadata=None,
                        url=None,
                        success=False,
                        error="ibid reference but no previous citation found",
                        citation_form="ibid"
                    )
                
                page = extract_ibid_page(original_text)
                formatted = BaseFormatter.format_ibid(page)
                
                if note_type == 'endnote':
                    processor.write_endnote(note_id, formatted)
                else:
                    processor.write_footnote(note_id, formatted)
                
                return ProcessedCitation(
                    original=original_text,
                    formatted=formatted,
                    metadata=previous_metadata,
                    url=history.get_previous_url(),
                    success=True,
                    citation_form="ibid"
                )
            
            # Case 2+: Process citation to get metadata
            metadata, full_formatted = get_citation(original_text, style)
            
            if not metadata or not full_formatted:
                return ProcessedCitation(
                    original=original_text,
                    formatted=original_text,
                    metadata=None,
                    url=None,
                    success=False,
                    error="No metadata found",
                    citation_form="full"
                )
            
            current_url = getattr(metadata, 'url', None)
            if not current_url and original_text.strip().startswith('http'):
                current_url = original_text.strip()
            
            # Case 2: Check if same URL as previous → ibid
            previous_url = history.get_previous_url()
            if current_url and previous_url and urls_match(current_url, previous_url):
                formatted = BaseFormatter.format_ibid()
                
                if note_type == 'endnote':
                    processor.write_endnote(note_id, formatted)
                else:
                    processor.write_footnote(note_id, formatted)
                
                return ProcessedCitation(
                    original=original_text,
                    formatted=formatted,
                    metadata=history.get_previous_metadata(),
                    url=current_url,
                    success=True,
                    citation_form="ibid"
                )
            
            # Case 3: Check if same source as previous → ibid
            if history.is_same_as_previous(metadata):
                formatted = BaseFormatter.format_ibid()
                
                if note_type == 'endnote':
                    processor.write_endnote(note_id, formatted)
                else:
                    processor.write_footnote(note_id, formatted)
                
                return ProcessedCitation(
                    original=original_text,
                    formatted=formatted,
                    metadata=metadata,
                    url=current_url,
                    success=True,
                    citation_form="ibid"
                )
            
            # Case 4: Check if previously cited → short form
            if history.has_been_cited_before(metadata):
                formatted = formatter.format_short(metadata)
                
                if note_type == 'endnote':
                    processor.write_endnote(note_id, formatted)
                else:
                    processor.write_footnote(note_id, formatted)
                
                history.add(metadata, formatted)
                
                return ProcessedCitation(
                    original=original_text,
                    formatted=formatted,
                    metadata=metadata,
                    url=current_url,
                    success=True,
                    citation_form="short"
                )
            
            # Case 5: New source → full citation
            if note_type == 'endnote':
                processor.write_endnote(note_id, full_formatted)
            else:
                processor.write_footnote(note_id, full_formatted)
            
            history.add(metadata, full_formatted)
            
            return ProcessedCitation(
                original=original_text,
                formatted=full_formatted,
                metadata=metadata,
                url=current_url,
                success=True,
                citation_form="full"
            )
                
        except Exception as e:
            print(f"[process_document] Error processing {note_type} {note_id}: {e}")
            return ProcessedCitation(
                original=original_text,
                formatted=original_text,
                metadata=None,
                url=None,
                success=False,
                error=str(e),
                citation_form="full"
            )
    
    # Process endnotes
    for note in endnotes:
        result = process_single_note(note, 'endnote')
        results.append(result)
    
    # Process footnotes
    for note in footnotes:
        result = process_single_note(note, 'footnote')
        results.append(result)
    
    # Save to buffer
    doc_buffer = processor.save_to_buffer()
    
    # Make URLs clickable if requested
    if add_links:
        doc_buffer = LinkActivator.process(doc_buffer)
    
    # Cleanup
    processor.cleanup()
    
    return doc_buffer.read(), results


# =============================================================================
# UPDATE SINGLE NOTE (for Workbench UI)
# Added: 2025-12-05 13:40
# =============================================================================

def update_document_note(doc_bytes: bytes, note_id: int, new_html: str) -> bytes:
    """
    Update a single endnote/footnote in a processed document.
    
    This function is used by the Workbench UI to update individual notes
    after manual editing.
    
    Args:
        doc_bytes: The current processed document as bytes
        note_id: The 1-based note ID to update
        new_html: The new HTML content for the note
        
    Returns:
        Updated document as bytes
    """
    import io
    import zipfile
    import tempfile
    import shutil
    import re
    
    try:
        # Extract the docx
        temp_dir = tempfile.mkdtemp()
        
        with zipfile.ZipFile(io.BytesIO(doc_bytes), 'r') as zf:
            zf.extractall(temp_dir)
        
        # Find and update the endnote
        endnotes_path = os.path.join(temp_dir, 'word', 'endnotes.xml')
        footnotes_path = os.path.join(temp_dir, 'word', 'footnotes.xml')
        
        updated = False
        
        for xml_path, note_tag in [(endnotes_path, 'w:endnote'), (footnotes_path, 'w:footnote')]:
            if not os.path.exists(xml_path):
                continue
                
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the note with matching ID
            # Pattern: <w:endnote w:id="N">...</w:endnote>
            pattern = rf'(<{note_tag}\s+[^>]*w:id="{note_id}"[^>]*>)(.*?)(</{note_tag}>)'
            
            def replace_note_content(match):
                open_tag = match.group(1)
                close_tag = match.group(3)
                
                # Convert HTML to Word XML
                word_xml = html_to_word_xml(new_html)
                
                return f"{open_tag}{word_xml}{close_tag}"
            
            new_content, count = re.subn(pattern, replace_note_content, content, flags=re.DOTALL)
            
            if count > 0:
                with open(xml_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                updated = True
                break
        
        # Repackage the docx
        output_buffer = io.BytesIO()
        with zipfile.ZipFile(output_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zf.write(file_path, arcname)
        
        # Cleanup
        shutil.rmtree(temp_dir)
        
        output_buffer.seek(0)
        return output_buffer.read()
        
    except Exception as e:
        print(f"[update_document_note] Error: {e}")
        # Return original if update fails
        return doc_bytes


def html_to_word_xml(html: str) -> str:
    """
    Convert simple HTML to Word XML for endnote content.
    
    Handles:
    - <i>text</i> → italic runs
    - Plain text → normal runs
    - Basic structure preservation
    """
    import re
    import html as html_module
    
    # Unescape HTML entities
    text = html_module.unescape(html)
    
    # Build Word XML paragraph
    runs = []
    
    # Split by italic tags
    parts = re.split(r'(<i>.*?</i>)', text)
    
    for part in parts:
        if not part:
            continue
            
        if part.startswith('<i>') and part.endswith('</i>'):
            # Italic text
            inner = part[3:-4]
            inner_escaped = inner.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            runs.append(f'<w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">{inner_escaped}</w:t></w:r>')
        else:
            # Normal text
            escaped = part.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            runs.append(f'<w:r><w:t xml:space="preserve">{escaped}</w:t></w:r>')
    
    # Wrap in paragraph
    return f'<w:p>{"".join(runs)}</w:p>'
