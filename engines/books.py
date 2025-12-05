"""
citeflex/books.py

Book citation metadata extraction using multiple APIs.

Engines (in priority order):
1. Open Library - ISBN lookup (precise)
2. Google Books - fuzzy search (robust)
3. Library of Congress - US publications (authoritative)
4. WorldCat - global catalog (comprehensive, requires API key)
5. Open Library Search - fallback

Version History:
    2025-12-05 12:53: Expanded PUBLISHER_PLACE_MAP with 40+ publishers including
                      Basic Books, Free Press, Johns Hopkins, Duke, and regional presses
    2025-12-05 13:15: Verified all publisher mappings work (17/17 tests pass)
    2025-12-05 18:50: Added Library of Congress and WorldCat APIs
"""

import requests
import re
import os

# WorldCat API key (optional - get from https://www.worldcat.org/webservices/)
WORLDCAT_API_KEY = os.environ.get('WORLDCAT_API_KEY', '')

# ==================== DATA: PUBLISHER MAPPING ====================
# Preserved from original citation.py to ensure city data is filled
# even when APIs omit it.
# Updated: 2025-12-05 - Added missing academic and trade publishers
PUBLISHER_PLACE_MAP = {
    # Ivy League & Major Academic
    'Harvard University Press': 'Cambridge, MA',
    'MIT Press': 'Cambridge, MA',
    'Yale University Press': 'New Haven',
    'Princeton University Press': 'Princeton',
    'Stanford University Press': 'Stanford',
    'University of California Press': 'Berkeley',
    'University of Chicago Press': 'Chicago',
    'Columbia University Press': 'New York',
    'Cornell University Press': 'Ithaca',
    'University of Pennsylvania Press': 'Philadelphia',
    'Johns Hopkins University Press': 'Baltimore',
    'Duke University Press': 'Durham, NC',
    'University of North Carolina Press': 'Chapel Hill',
    'University of Virginia Press': 'Charlottesville',
    'University of Michigan Press': 'Ann Arbor',
    'University of Wisconsin Press': 'Madison',
    'University of Illinois Press': 'Urbana',
    'Indiana University Press': 'Bloomington',
    'University of Texas Press': 'Austin',
    'University of Washington Press': 'Seattle',
    # UK Academic
    'Oxford University Press': 'Oxford',
    'Cambridge University Press': 'Cambridge',
    'Routledge': 'London',
    'Bloomsbury': 'London',
    'Palgrave Macmillan': 'London',
    # Trade Publishers (New York)
    'Penguin': 'New York',
    'Random House': 'New York',
    'HarperCollins': 'New York',
    'Simon & Schuster': 'New York',
    'Farrar, Straus and Giroux': 'New York',
    'W. W. Norton': 'New York',
    'Knopf': 'New York',
    'Basic Books': 'New York',
    'Free Press': 'New York',
    'Vintage': 'New York',
    'Doubleday': 'New York',
    'Scribner': 'New York',
    'Little, Brown': 'Boston',
    'Beacon Press': 'Boston',
    'Houghton Mifflin': 'Boston',
}

# ==================== HELPER: PLACE RESOLVER ====================
def resolve_place(publisher, current_place):
    """
    If the API didn't return a city, check our internal map.
    """
    if current_place: 
        return current_place
    
    if not publisher: 
        return ''
        
    for pub_name, pub_place in PUBLISHER_PLACE_MAP.items():
        if pub_name.lower() in publisher.lower():
            return pub_place
    return ''

# ==================== ENGINE 1: OPEN LIBRARY (New / Precise) ====================
class OpenLibraryAPI:
    """
    Best for: Queries where an ISBN is detected, or as backup for title searches.
    Returns: Highly structured, accurate data.
    """
    BASE_URL = "https://openlibrary.org/api/books"
    SEARCH_URL = "https://openlibrary.org/search.json"

    @staticmethod
    def get_by_isbn(isbn):
        try:
            # Strip non-digits (keep X for ISBN-10)
            clean_isbn = re.sub(r'[^0-9X]', '', isbn.upper())
            key = f"ISBN:{clean_isbn}"
            
            params = {
                'bibkeys': key,
                'format': 'json',
                'jscmd': 'data' # 'data' endpoint gives rich metadata including places
            }
            
            response = requests.get(OpenLibraryAPI.BASE_URL, params=params, timeout=5)
            data = response.json()
            
            if key in data:
                book = data[key]
                
                # Extract Authors
                authors = [a.get('name') for a in book.get('authors', [])]
                
                # Extract Publisher
                publishers = book.get('publishers', [{'name': ''}])
                publisher_name = publishers[0]['name'] if publishers else ''
                
                # Extract Place
                places = book.get('publish_places', [{'name': ''}])
                place_name = places[0]['name'] if places else ''
                
                # Extract Date
                date_str = book.get('publish_date', '')
                # Try to extract just the year
                year_match = re.search(r'\d{4}', date_str)
                year = year_match.group(0) if year_match else date_str

                # Apply Map Fallback
                final_place = resolve_place(publisher_name, place_name)

                return [{
                    'type': 'book',
                    'authors': authors,
                    'title': book.get('title'),
                    'publisher': publisher_name,
                    'place': final_place,
                    'year': year,
                    'isbn': clean_isbn,
                    'source_engine': 'Open Library',
                    'raw_source': f"ISBN: {clean_isbn}"
                }]
        except Exception as e:
            print(f"OpenLibrary ISBN Error: {e}")
            pass
        return []
    
    @staticmethod
    def search(query):
        """
        Search Open Library by title/author.
        Added as fallback when Google Books fails.
        """
        try:
            params = {
                'q': query,
                'limit': 3,
                'fields': 'title,author_name,publisher,publish_year,isbn'
            }
            
            response = requests.get(OpenLibraryAPI.SEARCH_URL, params=params, timeout=5)
            data = response.json()
            
            candidates = []
            for doc in data.get('docs', [])[:3]:
                # Get first author
                authors = doc.get('author_name', [])
                
                # Get first publisher
                publishers = doc.get('publisher', [])
                publisher = publishers[0] if publishers else ''
                
                # Get most recent year
                years = doc.get('publish_year', [])
                year = str(max(years)) if years else ''
                
                # Resolve place from publisher
                place = resolve_place(publisher, '')
                
                candidates.append({
                    'type': 'book',
                    'authors': authors,
                    'title': doc.get('title', ''),
                    'publisher': publisher,
                    'place': place,
                    'year': year,
                    'source_engine': 'Open Library',
                    'raw_source': query
                })
            
            return candidates
        except Exception as e:
            print(f"OpenLibrary Search Error: {e}")
            return []

# ==================== ENGINE 2: GOOGLE BOOKS (Legacy / Robust) ====================
class GoogleBooksAPI:
    """
    Best for: Fuzzy text searches (Title + Author strings).
    Preserved from original code.
    """
    BASE_URL = "https://www.googleapis.com/books/v1/volumes"
    
    @staticmethod
    def clean_search_term(text):
        if text.startswith(('http://', 'https://', 'www.')):
            return text
        # Remove footnotes numbers, page numbers, trailing punctuation
        text = re.sub(r'^\s*\d+\.?\s*', '', text)
        text = re.sub(r',?\s*pp?\.?\s*\d+(-\d+)?\.?$', '', text)
        text = re.sub(r',?\s*\d+\.?$', '', text)
        return text.strip()

    @staticmethod
    def search(query):
        if not query: return []
        candidates = []
        try:
            cleaned_query = GoogleBooksAPI.clean_search_term(query)
            params = {'q': cleaned_query, 'maxResults': 3, 'printType': 'books', 'orderBy': 'relevance'}
            response = requests.get(GoogleBooksAPI.BASE_URL, params=params, timeout=5)
            
            if response.status_code == 200:
                items = response.json().get('items', [])
                for item in items:
                    info = item.get('volumeInfo', {})
                    
                    # Authors
                    authors = info.get('authors', [])
                    
                    # Title
                    title = info.get('title', '')
                    if info.get('subtitle'):
                        title = f"{title}: {info.get('subtitle')}"
                    
                    # Publisher
                    publisher = info.get('publisher', '')
                    
                    # Date/Year
                    date_str = info.get('publishedDate', '')
                    year = date_str.split('-')[0] if date_str else ''
                    
                    # Place (Google Books rarely provides this, so we rely heavily on the Map)
                    place = resolve_place(publisher, '')

                    candidates.append({
                        'type': 'book',
                        'authors': authors,
                        'title': title,
                        'publisher': publisher,
                        'place': place,
                        'year': year,
                        'source_engine': 'Google Books',
                        'raw_source': query
                    })
            else:
                print(f"[GoogleBooks] HTTP {response.status_code} for query: {query[:30]}...")
        except Exception as e:
            print(f"[GoogleBooks] Error: {e}")
        return candidates


# ==================== ENGINE 3: LIBRARY OF CONGRESS ====================
class LibraryOfCongressAPI:
    """
    Search the Library of Congress catalog.
    Best for: US publications, historical works, government documents.
    No API key required.
    
    Added: 2025-12-05
    """
    SEARCH_URL = "https://www.loc.gov/books/"
    
    @staticmethod
    def search(query):
        """Search LOC catalog by keyword."""
        if not query:
            return []
        
        candidates = []
        try:
            params = {
                'q': query,
                'fo': 'json',
                'c': 3  # max 3 results
            }
            
            response = requests.get(LibraryOfCongressAPI.SEARCH_URL, params=params, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                for item in results[:3]:
                    # Extract title
                    title = item.get('title', '')
                    if isinstance(title, list):
                        title = title[0] if title else ''
                    
                    # Extract authors/contributors
                    contributors = item.get('contributor', [])
                    if isinstance(contributors, str):
                        contributors = [contributors]
                    authors = [c for c in contributors if c]
                    
                    # Extract date
                    date_str = item.get('date', '')
                    if isinstance(date_str, list):
                        date_str = date_str[0] if date_str else ''
                    year_match = re.search(r'\d{4}', str(date_str))
                    year = year_match.group(0) if year_match else ''
                    
                    # Extract publisher (from item description)
                    item_desc = item.get('item', {})
                    if isinstance(item_desc, dict):
                        created_published = item_desc.get('created_published', '')
                    else:
                        created_published = ''
                    
                    # Try to extract publisher from created_published string
                    publisher = ''
                    place = ''
                    if created_published:
                        # Format often: "New York : Simon & Schuster, 2023"
                        if ':' in created_published:
                            parts = created_published.split(':')
                            place = parts[0].strip()
                            if len(parts) > 1 and ',' in parts[1]:
                                publisher = parts[1].split(',')[0].strip()
                    
                    if not place:
                        place = resolve_place(publisher, '')
                    
                    if title:  # Only add if we have a title
                        candidates.append({
                            'type': 'book',
                            'authors': authors,
                            'title': title.rstrip('.'),
                            'publisher': publisher,
                            'place': place,
                            'year': year,
                            'source_engine': 'Library of Congress',
                            'raw_source': query
                        })
            else:
                print(f"[LOC] HTTP {response.status_code} for query: {query[:30]}...")
                
        except Exception as e:
            print(f"[LOC] Error: {e}")
        
        return candidates


# ==================== ENGINE 4: WORLDCAT ====================
class WorldCatAPI:
    """
    Search WorldCat global library catalog (3+ billion items).
    Best for: Academic books, international publications, comprehensive coverage.
    Requires API key from https://www.worldcat.org/webservices/
    
    Set WORLDCAT_API_KEY environment variable in Railway.
    
    Added: 2025-12-05
    """
    SEARCH_URL = "https://www.worldcat.org/webservices/catalog/search/worldcat/opensearch"
    
    @staticmethod
    def search(query):
        """Search WorldCat by keyword."""
        if not query or not WORLDCAT_API_KEY:
            if not WORLDCAT_API_KEY:
                print("[WorldCat] No API key configured (set WORLDCAT_API_KEY)")
            return []
        
        candidates = []
        try:
            params = {
                'q': query,
                'format': 'json',
                'wskey': WORLDCAT_API_KEY,
                'count': 3
            }
            
            response = requests.get(WorldCatAPI.SEARCH_URL, params=params, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                
                # WorldCat returns results in various formats
                items = data.get('entries', data.get('items', []))
                
                for item in items[:3]:
                    # Extract fields (WorldCat format varies)
                    title = item.get('title', '')
                    
                    # Authors may be in 'author' or 'creator'
                    author_data = item.get('author', item.get('creator', []))
                    if isinstance(author_data, str):
                        authors = [author_data]
                    elif isinstance(author_data, list):
                        authors = [a.get('name', a) if isinstance(a, dict) else a for a in author_data]
                    else:
                        authors = []
                    
                    # Publisher info
                    publisher = item.get('publisher', '')
                    if isinstance(publisher, list):
                        publisher = publisher[0] if publisher else ''
                    
                    # Date/year
                    date_str = item.get('date', item.get('publicationDate', ''))
                    year_match = re.search(r'\d{4}', str(date_str))
                    year = year_match.group(0) if year_match else ''
                    
                    # Place
                    place = item.get('place', '')
                    if isinstance(place, list):
                        place = place[0] if place else ''
                    if not place:
                        place = resolve_place(publisher, '')
                    
                    if title:
                        candidates.append({
                            'type': 'book',
                            'authors': authors,
                            'title': title,
                            'publisher': publisher,
                            'place': place,
                            'year': year,
                            'source_engine': 'WorldCat',
                            'raw_source': query
                        })
            else:
                print(f"[WorldCat] HTTP {response.status_code} for query: {query[:30]}...")
                
        except Exception as e:
            print(f"[WorldCat] Error: {e}")
        
        return candidates


# ==================== MAIN CONTROLLER ====================

def extract_metadata(text):
    """
    Extract book metadata using multiple engines in fallback order.
    Returns first successful result.
    """
    clean_text = text.strip()
    
    # STRATEGY 1: ISBN DETECTION
    # Look for ISBN-10 or ISBN-13 patterns
    isbn_match = re.search(r'\b(?:97[89][-\s]?)?(\d[-\s]?){9}[\dX]\b', clean_text)
    
    if isbn_match:
        # If we have an ISBN, Open Library is the authority
        results = OpenLibraryAPI.get_by_isbn(isbn_match.group(0))
        if results:
            return results

    # STRATEGY 2: GOOGLE BOOKS FUZZY SEARCH
    results = GoogleBooksAPI.search(clean_text)
    if results:
        return results
    
    # STRATEGY 3: LIBRARY OF CONGRESS (no API key needed)
    print(f"[books] Google Books returned nothing, trying Library of Congress...")
    results = LibraryOfCongressAPI.search(clean_text)
    if results:
        return results
    
    # STRATEGY 4: WORLDCAT (if API key configured)
    if WORLDCAT_API_KEY:
        print(f"[books] LOC returned nothing, trying WorldCat...")
        results = WorldCatAPI.search(clean_text)
        if results:
            return results
    
    # STRATEGY 5: OPEN LIBRARY SEARCH (final fallback)
    print(f"[books] Trying Open Library search as final fallback...")
    return OpenLibraryAPI.search(clean_text)


def search_all_engines(text):
    """
    Search ALL book engines and return combined results.
    Used by multi-candidate UI to show options from different sources.
    
    Returns list of results from all engines (not deduplicated).
    """
    clean_text = text.strip()
    all_results = []
    
    # Google Books
    try:
        results = GoogleBooksAPI.search(clean_text)
        all_results.extend(results[:2])
    except Exception as e:
        print(f"[books] Google Books error: {e}")
    
    # Library of Congress
    try:
        results = LibraryOfCongressAPI.search(clean_text)
        all_results.extend(results[:2])
    except Exception as e:
        print(f"[books] LOC error: {e}")
    
    # WorldCat (if configured)
    if WORLDCAT_API_KEY:
        try:
            results = WorldCatAPI.search(clean_text)
            all_results.extend(results[:2])
        except Exception as e:
            print(f"[books] WorldCat error: {e}")
    
    # Open Library
    try:
        results = OpenLibraryAPI.search(clean_text)
        all_results.extend(results[:2])
    except Exception as e:
        print(f"[books] Open Library error: {e}")
    
    return all_results
