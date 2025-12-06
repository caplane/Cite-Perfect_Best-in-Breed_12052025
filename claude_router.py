"""
citeflex/claude_router.py

Claude AI-powered citation type detection and classification.
Used as the primary AI router for ambiguous citation queries.

Version History:
    2025-12-06: Initial production version with multi-option support
    
Usage:
    from claude_router import classify_with_claude, get_citation_options
    
    # Single classification (for unified_router.py)
    citation_type, metadata = classify_with_claude("Eric Caplan mind games")
    
    # Multiple options (returns up to 5 candidates for UI selection)
    options = get_citation_options("Eric Caplan mind games")
"""

import os
import re
import json
import requests
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from models import CitationType, CitationMetadata
from config import DEFAULT_TIMEOUT

# =============================================================================
# CONFIGURATION
# =============================================================================

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# =============================================================================
# CLAUDE CLIENT
# =============================================================================

def _get_client():
    """Get Anthropic client (lazy initialization)."""
    if not ANTHROPIC_API_KEY:
        return None
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# =============================================================================
# SINGLE CLASSIFICATION (for unified_router.py compatibility)
# =============================================================================

CLASSIFY_PROMPT = """You are a citation classification expert. Analyze the input and classify it.

Classify as one of:
- legal: Court cases, statutes, legal documents (contains "v." or "v ")
- book: Books, monographs
- journal: Academic journal articles, peer-reviewed papers
- newspaper: Newspaper/magazine articles
- government: Government reports, official documents
- medical: Medical/clinical content
- interview: Interviews, oral histories
- url: Websites, online resources
- unknown: Cannot determine

Respond in JSON only:
{"type": "...", "confidence": 0.0-1.0, "title": "", "authors": [], "year": "", "reasoning": "brief explanation"}"""


class ClaudeRouter:
    """Uses Claude to classify ambiguous citation queries."""
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.client = None
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def classify(self, text: str) -> Tuple[CitationType, Optional[CitationMetadata]]:
        """Classify a citation query and return type + metadata."""
        if not self.client:
            return CitationType.UNKNOWN, None
        
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                system=CLASSIFY_PROMPT,
                messages=[{"role": "user", "content": f"Classify this citation:\n\n{text}"}]
            )
            
            response_text = response.content[0].text
            return self._parse_response(response_text, text)
            
        except anthropic.RateLimitError:
            print("[ClaudeRouter] Rate limited")
            return CitationType.UNKNOWN, None
        except anthropic.AuthenticationError:
            print("[ClaudeRouter] Authentication failed - check ANTHROPIC_API_KEY")
            return CitationType.UNKNOWN, None
        except Exception as e:
            print(f"[ClaudeRouter] Error: {e}")
            return CitationType.UNKNOWN, None
    
    def _parse_response(self, response_text: str, original: str) -> Tuple[CitationType, Optional[CitationMetadata]]:
        """Parse Claude's JSON response."""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return CitationType.UNKNOWN, None
            
            data = json.loads(json_match.group())
            
            type_map = {
                'legal': CitationType.LEGAL,
                'book': CitationType.BOOK,
                'journal': CitationType.JOURNAL,
                'newspaper': CitationType.NEWSPAPER,
                'government': CitationType.GOVERNMENT,
                'medical': CitationType.MEDICAL,
                'interview': CitationType.INTERVIEW,
                'url': CitationType.URL,
            }
            
            citation_type = type_map.get(data.get('type', '').lower(), CitationType.UNKNOWN)
            
            if citation_type == CitationType.UNKNOWN:
                return citation_type, None
            
            metadata = CitationMetadata(
                citation_type=citation_type,
                raw_source=original,
                source_engine="Claude Router",
                title=data.get('title', ''),
                authors=data.get('authors', []),
                year=data.get('year'),
                confidence=data.get('confidence', 0.5),
                notes=data.get('reasoning', ''),
            )
            
            return citation_type, metadata
            
        except json.JSONDecodeError:
            return CitationType.UNKNOWN, None
        except Exception:
            return CitationType.UNKNOWN, None


def classify_with_claude(text: str) -> Tuple[CitationType, Optional[CitationMetadata]]:
    """Convenience function for unified_router.py compatibility."""
    return ClaudeRouter().classify(text)


# =============================================================================
# MULTI-OPTION SEARCH (for advanced UI)
# =============================================================================

IDENTIFY_PROMPT = """You are a citation identification expert. Given a messy, incomplete, or fragmentary reference, identify what it MIGHT be.

Respond in JSON only:
{
    "possible_types": ["book", "journal", "legal"],
    "search_queries": ["query1", "query2"],
    "case_name": "for legal: the case name if applicable",
    "authors": ["possible author names"],
    "title_keywords": ["key words from title"],
    "reasoning": "brief explanation"
}

Generate 2-3 search queries optimized for different APIs (books, journals, legal).
Do NOT invent specific details - just extract what's in the input."""


def _identify_with_claude(messy_note: str) -> dict:
    """Have Claude identify what the citation might be."""
    client = _get_client()
    if not client:
        return {"possible_types": ["unknown"], "search_queries": [messy_note]}
    
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            system=IDENTIFY_PROMPT,
            messages=[{"role": "user", "content": f"Identify this citation:\n\n{messy_note}"}]
        )
        text = response.content[0].text.strip()
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"    [Claude error: {e}]")
    return {"possible_types": ["unknown"], "search_queries": [messy_note]}


# =============================================================================
# EXTERNAL API SEARCH FUNCTIONS
# =============================================================================

def _format_authors(authors: list) -> str:
    """Format author list for citation."""
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    elif len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    elif len(authors) <= 3:
        return ", ".join(authors[:-1]) + f", and {authors[-1]}"
    else:
        return f"{authors[0]} et al."


def _get_publisher_place(publisher: str) -> str:
    """Get publication place from publisher name."""
    if not publisher:
        return ""
    
    publisher_places = {
        "simon & schuster": "New York",
        "simon and schuster": "New York",
        "penguin": "New York",
        "random house": "New York",
        "harpercollins": "New York",
        "knopf": "New York",
        "oxford university press": "Oxford",
        "cambridge university press": "Cambridge",
        "harvard university press": "Cambridge, MA",
        "yale university press": "New Haven",
        "princeton university press": "Princeton",
        "university of california press": "Berkeley",
        "university of chicago press": "Chicago",
        "columbia university press": "New York",
        "mit press": "Cambridge, MA",
        "routledge": "London",
        "johns hopkins": "Baltimore",
        "jhu press": "Baltimore",
    }
    
    pub_lower = publisher.lower()
    for pub_key, place in publisher_places.items():
        if pub_key in pub_lower:
            return place
    return ""


def _search_google_books(query: str, limit: int = 3) -> list:
    """Search Google Books, return multiple results."""
    results = []
    try:
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {"q": query, "maxResults": limit * 2, "orderBy": "relevance"}
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            
            for item in items[:limit * 2]:
                info = item.get("volumeInfo", {})
                title = info.get("title", "")
                
                # Skip knockoffs
                if any(skip in title.lower() for skip in ["summary of", "study guide", "analysis of"]):
                    continue
                
                authors = info.get("authors", [])
                if not authors:
                    continue
                
                publisher = info.get("publisher", "")
                year = info.get("publishedDate", "")[:4] if info.get("publishedDate") else ""
                subtitle = info.get("subtitle", "")
                place = _get_publisher_place(publisher)
                
                author_str = _format_authors(authors)
                full_title = f"{title}: {subtitle}" if subtitle else title
                
                cite = f"{author_str}, {full_title}"
                if place or publisher or year:
                    cite += " ("
                    if place:
                        cite += f"{place}: "
                    if publisher:
                        cite += publisher
                    if year:
                        cite += f", {year}"
                    cite += ")"
                cite += "."
                
                results.append({
                    "citation": cite,
                    "source": "Google Books",
                    "title": title,
                    "authors": authors,
                    "year": year
                })
                
                if len(results) >= limit:
                    break
                    
    except Exception as e:
        print(f"    [Google Books error: {e}]")
    return results


def _search_crossref(query: str, limit: int = 3) -> list:
    """Search Crossref, return multiple results."""
    results = []
    try:
        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": limit * 2}
        headers = {"User-Agent": "CiteFlex/1.0 (mailto:contact@citeflex.com)"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            items = resp.json().get("message", {}).get("items", [])
            
            for item in items:
                item_type = item.get("type", "")
                title = item.get("title", [""])[0] if item.get("title") else ""
                
                authors = []
                for a in item.get("author", []):
                    given = a.get('given', '')
                    family = a.get('family', '')
                    if given and family:
                        authors.append(f"{given} {family}")
                    elif family:
                        authors.append(family)
                
                if not authors:
                    continue
                
                year = ""
                if item.get("published"):
                    year = str(item["published"].get("date-parts", [[""]])[0][0])
                elif item.get("issued"):
                    year = str(item["issued"].get("date-parts", [[""]])[0][0])
                
                journal = item.get("container-title", [""])[0] if item.get("container-title") else ""
                volume = item.get("volume", "")
                issue = item.get("issue", "")
                pages = item.get("page", "")
                doi = item.get("DOI", "")
                publisher = item.get("publisher", "")
                
                # Format based on type
                author_str = _format_authors(authors)
                if item_type in ["book", "monograph"]:
                    place = _get_publisher_place(publisher)
                    cite = f"{author_str}, {title}"
                    if place or publisher or year:
                        cite += " ("
                        if place:
                            cite += f"{place}: "
                        if publisher:
                            cite += publisher
                        if year:
                            cite += f", {year}"
                        cite += ")"
                    cite += "."
                else:
                    # Journal article
                    cite = f'{author_str}, "{title},"'
                    if journal:
                        cite += f" {journal}"
                    if volume:
                        cite += f" {volume}"
                    if issue:
                        cite += f", no. {issue}"
                    if year:
                        cite += f" ({year})"
                    if pages:
                        cite += f": {pages}"
                    cite += "."
                    if doi:
                        cite += f" https://doi.org/{doi}."
                
                results.append({
                    "citation": cite,
                    "source": f"Crossref ({item_type})",
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "doi": doi
                })
                
                if len(results) >= limit:
                    break
                    
    except Exception as e:
        print(f"    [Crossref error: {e}]")
    return results


def _search_pubmed(query: str, limit: int = 3) -> list:
    """Search PubMed for medical/scientific articles."""
    results = []
    try:
        # Step 1: Search for PMIDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"}
        search_resp = requests.get(search_url, params=search_params, timeout=10)
        
        if search_resp.status_code != 200:
            return results
        
        pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return results
        
        # Step 2: Fetch details
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        fetch_params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
        fetch_resp = requests.get(fetch_url, params=fetch_params, timeout=10)
        
        if fetch_resp.status_code != 200:
            return results
        
        data = fetch_resp.json().get("result", {})
        
        for pmid in pmids:
            if pmid not in data:
                continue
            
            article = data[pmid]
            title = article.get("title", "").rstrip(".")
            
            authors = [a.get("name", "") for a in article.get("authors", []) if a.get("name")]
            if not authors:
                continue
            
            journal = article.get("fulljournalname", "") or article.get("source", "")
            volume = article.get("volume", "")
            issue = article.get("issue", "")
            pages = article.get("pages", "")
            year = article.get("pubdate", "")[:4]
            
            author_str = _format_authors(authors)
            cite = f'{author_str}, "{title},"'
            if journal:
                cite += f" {journal}"
            if volume:
                cite += f" {volume}"
            if issue:
                cite += f", no. {issue}"
            if year:
                cite += f" ({year})"
            if pages:
                cite += f": {pages}"
            cite += f". PMID: {pmid}."
            
            results.append({
                "citation": cite,
                "source": "PubMed",
                "title": title,
                "authors": authors,
                "year": year,
                "pmid": pmid
            })
            
    except Exception as e:
        print(f"    [PubMed error: {e}]")
    return results


# Famous cases cache
FAMOUS_CASES = {
    "roe v. wade": "Roe v. Wade, 410 U.S. 113 (1973).",
    "roe v wade": "Roe v. Wade, 410 U.S. 113 (1973).",
    "osheroff v. chestnut lodge": "Osheroff v. Chestnut Lodge, Inc., 490 A.2d 720 (Md. Ct. Spec. App. 1985).",
    "osheroff v chestnut lodge": "Osheroff v. Chestnut Lodge, Inc., 490 A.2d 720 (Md. Ct. Spec. App. 1985).",
    "brown v. board of education": "Brown v. Board of Education, 347 U.S. 483 (1954).",
    "loving v. virginia": "Loving v. Virginia, 388 U.S. 1 (1967).",
    "miranda v. arizona": "Miranda v. Arizona, 384 U.S. 436 (1966).",
    "marbury v. madison": "Marbury v. Madison, 5 U.S. 137 (1803).",
}


def _search_famous_cases(query: str) -> list:
    """Check famous cases cache."""
    results = []
    lookup = query.lower().strip()
    if lookup in FAMOUS_CASES:
        results.append({
            "citation": FAMOUS_CASES[lookup],
            "source": "Famous Cases Cache",
            "title": query
        })
    return results


def _dedupe_results(results: list) -> list:
    """Remove duplicate results based on title similarity."""
    seen_titles = set()
    deduped = []
    
    for r in results:
        title = r.get("title", "").lower()[:40]
        if title and title in seen_titles:
            continue
        seen_titles.add(title)
        deduped.append(r)
    
    return deduped


# =============================================================================
# MAIN MULTI-OPTION FUNCTION
# =============================================================================

def get_citation_options(messy_note: str, max_options: int = 5) -> list:
    """
    Generate up to max_options candidate citations from multiple sources.
    Returns list of {citation, source, title, ...} dicts.
    
    This is the main function for the multi-option UI.
    """
    all_results = []
    
    # Check for DOI in input
    doi_match = re.search(r'(10\.\d{4,}/[^\s\'"<>]+)', messy_note)
    if doi_match:
        doi = doi_match.group(1).rstrip('.,;')
        # Direct DOI lookup via Crossref
        try:
            url = f"https://api.crossref.org/works/{doi}"
            headers = {"User-Agent": "CiteFlex/1.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                item = resp.json().get("message", {})
                title = item.get("title", [""])[0] if item.get("title") else ""
                authors = []
                for a in item.get("author", []):
                    given = a.get('given', '')
                    family = a.get('family', '')
                    if given and family:
                        authors.append(f"{given} {family}")
                
                year = ""
                if item.get("published"):
                    year = str(item["published"].get("date-parts", [[""]])[0][0])
                
                journal = item.get("container-title", [""])[0] if item.get("container-title") else ""
                volume = item.get("volume", "")
                issue = item.get("issue", "")
                pages = item.get("page", "")
                
                author_str = _format_authors(authors)
                cite = f'{author_str}, "{title},"'
                if journal:
                    cite += f" {journal}"
                if volume:
                    cite += f" {volume}"
                if issue:
                    cite += f", no. {issue}"
                if year:
                    cite += f" ({year})"
                if pages:
                    cite += f": {pages}"
                cite += f". https://doi.org/{doi}."
                
                all_results.append({
                    "citation": cite,
                    "source": "Crossref (DOI lookup)",
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "doi": doi
                })
        except Exception:
            pass
    
    # Check for legal case (contains "v." or "v ")
    if " v. " in messy_note or " v " in messy_note:
        all_results.extend(_search_famous_cases(messy_note))
    
    # If we already have good results, maybe we're done
    if len(all_results) >= max_options:
        return _dedupe_results(all_results)[:max_options]
    
    # Get Claude's analysis
    identified = _identify_with_claude(messy_note)
    queries = identified.get("search_queries", [messy_note])
    if not queries:
        queries = [messy_note]
    
    # Search multiple APIs in parallel
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = []
        
        for query in queries[:2]:
            futures.append(executor.submit(_search_google_books, query, 2))
            futures.append(executor.submit(_search_crossref, query, 2))
            futures.append(executor.submit(_search_pubmed, query, 2))
        
        if messy_note not in queries:
            futures.append(executor.submit(_search_google_books, messy_note, 2))
            futures.append(executor.submit(_search_crossref, messy_note, 2))
            futures.append(executor.submit(_search_pubmed, messy_note, 2))
        
        for future in as_completed(futures, timeout=20):
            try:
                results = future.result(timeout=5)
                all_results.extend(results)
            except Exception:
                pass
    
    return _dedupe_results(all_results)[:max_options]
