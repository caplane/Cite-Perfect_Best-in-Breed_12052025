"""
citeflex/engines/books.py

Book citation metadata extraction using multiple APIs.

Engines (in priority order):
1. Open Library - ISBN lookup (precise)
2. Google Books - fuzzy search (robust)
3. Library of Congress - US publications (authoritative)
4. WorldCat - global catalog (comprehensive, requires API key)
5. Internet Archive - historical books, scans
6. Open Library Search - fallback

Version History:
    2025-12-06 11:55: Expanded PUBLISHER_PLACE_MAP to 300+ publishers with abbreviations
                      (e.g., 'Univ of California Press', 'UC Press' → Berkeley)
    2025-12-05 12:53: Expanded PUBLISHER_PLACE_MAP with 40+ publishers including
                      Basic Books, Free Press, Johns Hopkins, Duke, and regional presses
    2025-12-05 13:15: Verified all publisher mappings work (17/17 tests pass)
    2025-12-05 18:50: Added Library of Congress and WorldCat APIs
    2025-12-05 20:30: Moved from root to engines/ directory
"""

import requests
import re
import os

# WorldCat API key (optional - get from https://www.worldcat.org/webservices/)
WORLDCAT_API_KEY = os.environ.get('WORLDCAT_API_KEY', '')

# ==================== DATA: PUBLISHER MAPPING ====================
# Preserved from original citation.py to ensure city data is filled
# even when APIs omit it.
# Updated: 2025-12-06 - Massively expanded with abbreviations and 300+ publishers
PUBLISHER_PLACE_MAP = {
    # === MAJOR TRADE PUBLISHERS (Big 5 and imprints) ===
    'Simon & Schuster': 'New York',
    'Simon and Schuster': 'New York',
    'Scribner': 'New York',
    'Atria': 'New York',
    'Gallery Books': 'New York',
    'Pocket Books': 'New York',
    'Threshold': 'New York',
    
    'Penguin': 'New York',
    'Penguin Random House': 'New York',
    'Penguin Books': 'New York',
    'Penguin Press': 'New York',
    'Viking': 'New York',
    'Dutton': 'New York',
    'Putnam': 'New York',
    'Putnam Juvenile': 'New York',
    'Berkley': 'New York',
    'Ace Books': 'New York',
    'Plume': 'New York',
    'Riverhead': 'New York',
    
    'Random House': 'New York',
    'Knopf': 'New York',
    'Alfred A. Knopf': 'New York',
    'Doubleday': 'New York',
    'Crown': 'New York',
    'Ballantine': 'New York',
    'Bantam': 'New York',
    'Dell': 'New York',
    'Anchor Books': 'New York',
    'Anchor': 'New York',
    'Vintage': 'New York',
    'Vintage Books': 'New York',
    'Pantheon': 'New York',
    'Modern Library': 'New York',
    
    'HarperCollins': 'New York',
    'Harper': 'New York',
    'Harper & Row': 'New York',
    'Harper Perennial': 'New York',
    'William Morrow': 'New York',
    'Morrow': 'New York',
    'Avon': 'New York',
    'Ecco': 'New York',
    'HarperOne': 'New York',
    
    'Hachette': 'New York',
    'Little, Brown': 'Boston',
    'Little Brown': 'Boston',
    'Grand Central': 'New York',
    'Twelve': 'New York',
    'Basic Books': 'New York',
    'PublicAffairs': 'New York',
    'Public Affairs': 'New York',
    
    'Macmillan': 'New York',
    "St. Martin's": 'New York',
    "St Martin's": 'New York',
    "St. Martin's Press": 'New York',
    "St Martin's Press": 'New York',
    'St. Martins': 'New York',
    'Henry Holt': 'New York',
    'Holt': 'New York',
    'Farrar, Straus': 'New York',
    'Farrar Straus': 'New York',
    'Farrar, Straus and Giroux': 'New York',
    'FSG': 'New York',
    'Hill and Wang': 'New York',
    'Picador': 'New York',
    'Flatiron': 'New York',
    'Tor Books': 'New York',
    'Tor': 'New York',
    
    # === OTHER MAJOR TRADE ===
    'Norton': 'New York',
    'W. W. Norton': 'New York',
    'W.W. Norton': 'New York',
    'Liveright': 'New York',
    'Bloomsbury': 'New York',
    'Grove': 'New York',
    'Grove Atlantic': 'New York',
    'Grove Press': 'New York',
    'Atlantic Monthly': 'New York',
    'Algonquin': 'Chapel Hill',
    'Workman': 'New York',
    'Artisan': 'New York',
    'Abrams': 'New York',
    'Chronicle Books': 'San Francisco',
    'Ten Speed': 'Berkeley',
    'Clarkson Potter': 'New York',
    'Potter': 'New York',
    'Rizzoli': 'New York',
    'Phaidon': 'London',
    'Taschen': 'Cologne',
    'DK': 'New York',
    'Dorling Kindersley': 'New York',
    'National Geographic': 'Washington, DC',
    'Smithsonian': 'Washington, DC',
    'Time Life': 'New York',
    "Reader's Digest": 'New York',
    'Rodale': 'New York',
    'Hay House': 'Carlsbad, CA',
    'Sounds True': 'Boulder',
    'Shambhala': 'Boulder',
    'New World Library': 'Novato, CA',
    'Berrett-Koehler': 'San Francisco',
    'Jossey-Bass': 'San Francisco',
    'Wiley': 'Hoboken',
    'John Wiley': 'Hoboken',
    'For Dummies': 'Hoboken',
    'McGraw-Hill': 'New York',
    'McGraw Hill': 'New York',
    'Pearson': 'New York',
    'Cengage': 'Boston',
    'Wadsworth': 'Belmont, CA',
    'SAGE': 'Thousand Oaks, CA',
    'Sage Publications': 'Thousand Oaks, CA',
    'Free Press': 'New York',
    'Beacon Press': 'Boston',
    'Houghton Mifflin': 'Boston',
    'Houghton Mifflin Harcourt': 'Boston',
    
    # === UNIVERSITY PRESSES (full names and abbreviations) ===
    'Oxford University Press': 'Oxford',
    'Oxford Univ Press': 'Oxford',
    'OUP': 'Oxford',
    'Cambridge University Press': 'Cambridge',
    'Cambridge Univ Press': 'Cambridge',
    'CUP': 'Cambridge',
    'Cambridge Scholars': 'Newcastle upon Tyne',
    'Cambridge Scholars Publishing': 'Newcastle upon Tyne',
    'Harvard University Press': 'Cambridge, MA',
    'Harvard Univ Press': 'Cambridge, MA',
    'Yale University Press': 'New Haven',
    'Yale Univ Press': 'New Haven',
    'Princeton University Press': 'Princeton',
    'Princeton Univ Press': 'Princeton',
    'Columbia University Press': 'New York',
    'Columbia Univ Press': 'New York',
    'MIT Press': 'Cambridge, MA',
    'Stanford University Press': 'Stanford',
    'Stanford Univ Press': 'Stanford',
    'University of Chicago Press': 'Chicago',
    'Univ of Chicago Press': 'Chicago',
    'U of Chicago Press': 'Chicago',
    'Chicago University Press': 'Chicago',
    'University of California Press': 'Berkeley',
    'Univ of California Press': 'Berkeley',
    'U of California Press': 'Berkeley',
    'UC Press': 'Berkeley',
    'California University Press': 'Berkeley',
    'Johns Hopkins University Press': 'Baltimore',
    'Johns Hopkins Univ Press': 'Baltimore',
    'JHU Press': 'Baltimore',
    'Johns Hopkins': 'Baltimore',
    'Duke University Press': 'Durham',
    'Duke Univ Press': 'Durham',
    'Cornell University Press': 'Ithaca',
    'Cornell Univ Press': 'Ithaca',
    'University of Pennsylvania Press': 'Philadelphia',
    'Univ of Pennsylvania Press': 'Philadelphia',
    'Penn Press': 'Philadelphia',
    'UPenn Press': 'Philadelphia',
    'University of North Carolina Press': 'Chapel Hill',
    'Univ of North Carolina Press': 'Chapel Hill',
    'UNC Press': 'Chapel Hill',
    'University of Virginia Press': 'Charlottesville',
    'Univ of Virginia Press': 'Charlottesville',
    'UVA Press': 'Charlottesville',
    'University of Texas Press': 'Austin',
    'Univ of Texas Press': 'Austin',
    'UT Press': 'Austin',
    'University of Michigan Press': 'Ann Arbor',
    'Univ of Michigan Press': 'Ann Arbor',
    'Michigan University Press': 'Ann Arbor',
    'University of Illinois Press': 'Urbana',
    'Univ of Illinois Press': 'Urbana',
    'Illinois University Press': 'Urbana',
    'University of Wisconsin Press': 'Madison',
    'Univ of Wisconsin Press': 'Madison',
    'Wisconsin University Press': 'Madison',
    'University of Minnesota Press': 'Minneapolis',
    'Univ of Minnesota Press': 'Minneapolis',
    'Minnesota University Press': 'Minneapolis',
    'Indiana University Press': 'Bloomington',
    'Indiana Univ Press': 'Bloomington',
    'IU Press': 'Bloomington',
    'Ohio State University Press': 'Columbus',
    'Ohio State Univ Press': 'Columbus',
    'OSU Press': 'Columbus',
    'Penn State University Press': 'University Park',
    'Penn State Univ Press': 'University Park',
    'PSU Press': 'University Park',
    'University of Georgia Press': 'Athens',
    'Univ of Georgia Press': 'Athens',
    'UGA Press': 'Athens',
    'Louisiana State University Press': 'Baton Rouge',
    'LSU Press': 'Baton Rouge',
    'University of Washington Press': 'Seattle',
    'Univ of Washington Press': 'Seattle',
    'UW Press': 'Seattle',
    'University of Arizona Press': 'Tucson',
    'Univ of Arizona Press': 'Tucson',
    'University of New Mexico Press': 'Albuquerque',
    'Univ of New Mexico Press': 'Albuquerque',
    'UNM Press': 'Albuquerque',
    'University of Oklahoma Press': 'Norman',
    'Univ of Oklahoma Press': 'Norman',
    'OU Press': 'Norman',
    'University of Nebraska Press': 'Lincoln',
    'Univ of Nebraska Press': 'Lincoln',
    'Nebraska University Press': 'Lincoln',
    'University of Iowa Press': 'Iowa City',
    'Univ of Iowa Press': 'Iowa City',
    'Iowa University Press': 'Iowa City',
    'University of Missouri Press': 'Columbia, MO',
    'Univ of Missouri Press': 'Columbia, MO',
    'University of Kansas Press': 'Lawrence',
    'Univ of Kansas Press': 'Lawrence',
    'University of Colorado Press': 'Boulder',
    'Univ of Colorado Press': 'Boulder',
    'University of Utah Press': 'Salt Lake City',
    'Univ of Utah Press': 'Salt Lake City',
    'University of Hawaii Press': 'Honolulu',
    'Univ of Hawaii Press': 'Honolulu',
    'University of Toronto Press': 'Toronto',
    'Univ of Toronto Press': 'Toronto',
    'UTP': 'Toronto',
    "McGill-Queen's University Press": 'Montreal',
    "McGill-Queens University Press": 'Montreal',
    "McGill Queen's": 'Montreal',
    'University of British Columbia Press': 'Vancouver',
    'UBC Press': 'Vancouver',
    'Edinburgh University Press': 'Edinburgh',
    'Manchester University Press': 'Manchester',
    'University of Wales Press': 'Cardiff',
    'Liverpool University Press': 'Liverpool',
    'Bristol University Press': 'Bristol',
    'Amsterdam University Press': 'Amsterdam',
    'Leiden University Press': 'Leiden',
    'Rutgers University Press': 'New Brunswick',
    'Rutgers Univ Press': 'New Brunswick',
    'NYU Press': 'New York',
    'New York University Press': 'New York',
    'SUNY Press': 'Albany',
    'State University of New York Press': 'Albany',
    'Temple University Press': 'Philadelphia',
    'Fordham University Press': 'New York',
    'Georgetown University Press': 'Washington, DC',
    'Catholic University of America Press': 'Washington, DC',
    'University of Notre Dame Press': 'Notre Dame',
    'Baylor University Press': 'Waco',
    'University of South Carolina Press': 'Columbia, SC',
    'University of Tennessee Press': 'Knoxville',
    'University of Kentucky Press': 'Lexington',
    'University of Alabama Press': 'Tuscaloosa',
    'University of Arkansas Press': 'Fayetteville',
    'Texas A&M University Press': 'College Station',
    'University of Nevada Press': 'Reno',
    'Oregon State University Press': 'Corvallis',
    'University of Massachusetts Press': 'Amherst',
    'Wesleyan University Press': 'Middletown',
    'University Press of Florida': 'Gainesville',
    'University Press of Kansas': 'Lawrence',
    'University Press of Kentucky': 'Lexington',
    'University Press of Mississippi': 'Jackson',
    'University Press of New England': 'Hanover',
    'University Press of Colorado': 'Louisville, CO',
    
    # === ACADEMIC/SCHOLARLY PUBLISHERS ===
    'Routledge': 'London',
    'Taylor & Francis': 'London',
    'Taylor and Francis': 'London',
    'CRC Press': 'Boca Raton',
    'Brill': 'Leiden',
    'Elsevier': 'Amsterdam',
    'Springer': 'New York',
    'Springer Nature': 'New York',
    'Springer Verlag': 'Berlin',
    'Springer-Verlag': 'Berlin',
    'Springer Science': 'New York',
    'Palgrave': 'London',
    'Palgrave Macmillan': 'London',
    'De Gruyter': 'Berlin',
    'Walter de Gruyter': 'Berlin',
    'Mouton de Gruyter': 'Berlin',
    'Academic Press': 'San Diego',
    'Blackwell': 'Oxford',
    'Wiley-Blackwell': 'Oxford',
    'Polity': 'Cambridge',
    'Polity Press': 'Cambridge',
    'Verso': 'London',
    'Zed Books': 'London',
    'Pluto Press': 'London',
    'Berg': 'Oxford',
    'Ashgate': 'Farnham',
    'Edward Elgar': 'Cheltenham',
    'Peter Lang': 'New York',
    'Lexington Books': 'Lanham',
    'Rowman & Littlefield': 'Lanham',
    'Rowman and Littlefield': 'Lanham',
    'Scarecrow': 'Lanham',
    'University Press of America': 'Lanham',
    'UPA': 'Lanham',
    'Continuum': 'London',
    'T&T Clark': 'London',
    'T & T Clark': 'London',
    'Fortress Press': 'Minneapolis',
    'Westminster John Knox': 'Louisville',
    'WJK': 'Louisville',
    'Eerdmans': 'Grand Rapids',
    'Baker Academic': 'Grand Rapids',
    'InterVarsity Press': 'Downers Grove',
    'IVP': 'Downers Grove',
    'Zondervan': 'Grand Rapids',
    'Abingdon': 'Nashville',
    'Broadman & Holman': 'Nashville',
    'B&H': 'Nashville',
    'Moody': 'Chicago',
    'Crossway': 'Wheaton',
    'Psychology Press': 'Hove',
    'Psychology Press/Routledge': 'London',
    'Infobase': 'New York',
    'Infobase Publishing': 'New York',
    'Facts on File': 'New York',
    'Greenwood': 'Westport',
    'Praeger': 'Westport',
    'ABC-CLIO': 'Santa Barbara',
    'McFarland': 'Jefferson, NC',
    "BoD": 'Norderstedt',
    "Books on Demand": 'Norderstedt',
    
    # === LAW PUBLISHERS ===
    'West': 'St. Paul',
    'West Publishing': 'St. Paul',
    'Thomson West': 'St. Paul',
    'LexisNexis': 'New York',
    'Lexis Nexis': 'New York',
    'Matthew Bender': 'New York',
    'Wolters Kluwer': 'New York',
    'Aspen': 'New York',
    'Aspen Publishers': 'New York',
    'Foundation Press': 'St. Paul',
    'Carolina Academic Press': 'Durham',
    'CAP': 'Durham',
    
    # === MEDICAL/SCIENCE ===
    'Lippincott': 'Philadelphia',
    'Lippincott Williams': 'Philadelphia',
    'LWW': 'Philadelphia',
    'Saunders': 'Philadelphia',
    'Mosby': 'St. Louis',
    'Elsevier Health': 'Philadelphia',
    'Thieme': 'New York',
    'Karger': 'Basel',
    'Nature Publishing': 'London',
    'Cold Spring Harbor': 'Cold Spring Harbor',
    'CSHL Press': 'Cold Spring Harbor',
    'ASM Press': 'Washington, DC',
    'American Chemical Society': 'Washington, DC',
    'ACS': 'Washington, DC',
    'American Psychological Association': 'Washington, DC',
    'APA': 'Washington, DC',
    'American Psychiatric': 'Washington, DC',
    'Guilford': 'New York',
    'Guilford Press': 'New York',
    
    # === ARTS/HUMANITIES ===
    'Yale Art': 'New Haven',
    'Metropolitan Museum': 'New York',
    'Met Publications': 'New York',
    'Getty': 'Los Angeles',
    'Getty Publications': 'Los Angeles',
    'Prestel': 'Munich',
    'Thames & Hudson': 'London',
    'Thames and Hudson': 'London',
    'Laurence King': 'London',
    
    # === TECH ===
    "O'Reilly": 'Sebastopol',
    'OReilly': 'Sebastopol',
    'Addison-Wesley': 'Boston',
    'Addison Wesley': 'Boston',
    'Prentice Hall': 'Upper Saddle River',
    'Apress': 'New York',
    'Manning': 'Shelter Island',
    'No Starch': 'San Francisco',
    'No Starch Press': 'San Francisco',
    'Pragmatic': 'Raleigh',
    'Pragmatic Bookshelf': 'Raleigh',
    'Packt': 'Birmingham',
    'Sams': 'Indianapolis',
    'Que': 'Indianapolis',
    'New Riders': 'Berkeley',
    'Peachpit': 'San Francisco',
    
    # === INTERNATIONAL ===
    'Gallimard': 'Paris',
    'Flammarion': 'Paris',
    'Seuil': 'Paris',
    'Albin Michel': 'Paris',
    'Fayard': 'Paris',
    'Hachette Livre': 'Paris',
    'PUF': 'Paris',
    'Suhrkamp': 'Frankfurt',
    'Fischer': 'Frankfurt',
    'Rowohlt': 'Hamburg',
    'Hanser': 'Munich',
    'Beck': 'Munich',
    'C.H. Beck': 'Munich',
    'DTV': 'Munich',
    'Einaudi': 'Turin',
    'Mondadori': 'Milan',
    'Feltrinelli': 'Milan',
    'Laterza': 'Rome',
    'Alianza': 'Madrid',
    'Anagrama': 'Barcelona',
    'Tusquets': 'Barcelona',
    'Fondo de Cultura': 'Mexico City',
    'Siglo XXI': 'Mexico City',
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
            
            # Try multiple query strategies
            queries_to_try = [cleaned_query]
            
            # If query looks like "Author Title", try intitle: and inauthor:
            words = cleaned_query.split()
            if len(words) >= 3:
                # Try: first word as author, rest as title
                # e.g. "ilyon woo master slave" -> inauthor:ilyon+intitle:master slave
                potential_author = words[0]
                potential_title = ' '.join(words[1:])
                queries_to_try.append(f'inauthor:{potential_author}+intitle:{potential_title}')
                
                # Try: first two words as author
                # e.g. "ilyon woo master slave" -> inauthor:ilyon woo+intitle:master slave
                if len(words) >= 4:
                    potential_author = ' '.join(words[:2])
                    potential_title = ' '.join(words[2:])
                    queries_to_try.append(f'inauthor:{potential_author}+intitle:{potential_title}')
            
            for q in queries_to_try:
                params = {'q': q, 'maxResults': 3, 'printType': 'books', 'orderBy': 'relevance'}
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
                    
                    # If we got results, stop trying other queries
                    if candidates:
                        break
                else:
                    print(f"[GoogleBooks] HTTP {response.status_code} for query: {q[:30]}...")
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


# ==================== ENGINE 5: INTERNET ARCHIVE ====================
class InternetArchiveAPI:
    """
    Search Internet Archive's Open Library and book collections.
    Best for: Historical books, out-of-print titles, scanned books.
    No API key required.
    
    Added: 2025-12-05
    """
    SEARCH_URL = "https://archive.org/advancedsearch.php"
    
    @staticmethod
    def search(query):
        """Search Internet Archive by keyword."""
        if not query:
            return []
        
        candidates = []
        try:
            params = {
                'q': f'title:({query}) AND mediatype:texts',
                'fl[]': ['title', 'creator', 'publisher', 'date', 'year'],
                'sort[]': 'downloads desc',
                'rows': 3,
                'page': 1,
                'output': 'json'
            }
            
            response = requests.get(InternetArchiveAPI.SEARCH_URL, params=params, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                docs = data.get('response', {}).get('docs', [])
                
                for doc in docs[:3]:
                    title = doc.get('title', '')
                    if isinstance(title, list):
                        title = title[0] if title else ''
                    
                    # Creator/author
                    creator = doc.get('creator', [])
                    if isinstance(creator, str):
                        authors = [creator]
                    elif isinstance(creator, list):
                        authors = creator[:3]  # Max 3 authors
                    else:
                        authors = []
                    
                    # Publisher
                    publisher = doc.get('publisher', '')
                    if isinstance(publisher, list):
                        publisher = publisher[0] if publisher else ''
                    
                    # Year
                    year = doc.get('year', doc.get('date', ''))
                    if isinstance(year, list):
                        year = year[0] if year else ''
                    year_match = re.search(r'\d{4}', str(year))
                    year = year_match.group(0) if year_match else ''
                    
                    # Place from publisher
                    place = resolve_place(publisher, '')
                    
                    if title:
                        candidates.append({
                            'type': 'book',
                            'authors': authors,
                            'title': title,
                            'publisher': publisher,
                            'place': place,
                            'year': year,
                            'source_engine': 'Internet Archive',
                            'raw_source': query
                        })
            else:
                print(f"[InternetArchive] HTTP {response.status_code} for query: {query[:30]}...")
                
        except Exception as e:
            print(f"[InternetArchive] Error: {e}")
        
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
        print(f"[books] Searching Google Books for: {clean_text[:30]}...")
        results = GoogleBooksAPI.search(clean_text)
        print(f"[books] Google Books returned {len(results)} results")
        all_results.extend(results[:2])
    except Exception as e:
        print(f"[books] Google Books error: {e}")
    
    # Library of Congress
    try:
        print(f"[books] Searching Library of Congress...")
        results = LibraryOfCongressAPI.search(clean_text)
        print(f"[books] LOC returned {len(results)} results")
        all_results.extend(results[:2])
    except Exception as e:
        print(f"[books] LOC error: {e}")
    
    # Internet Archive (free, no key needed)
    try:
        print(f"[books] Searching Internet Archive...")
        results = InternetArchiveAPI.search(clean_text)
        print(f"[books] Internet Archive returned {len(results)} results")
        all_results.extend(results[:2])
    except Exception as e:
        print(f"[books] Internet Archive error: {e}")
    
    # WorldCat (if configured)
    if WORLDCAT_API_KEY:
        try:
            print(f"[books] Searching WorldCat...")
            results = WorldCatAPI.search(clean_text)
            print(f"[books] WorldCat returned {len(results)} results")
            all_results.extend(results[:2])
        except Exception as e:
            print(f"[books] WorldCat error: {e}")
    
    # Open Library
    try:
        print(f"[books] Searching Open Library...")
        results = OpenLibraryAPI.search(clean_text)
        print(f"[books] Open Library returned {len(results)} results")
        all_results.extend(results[:2])
    except Exception as e:
        print(f"[books] Open Library error: {e}")
    
    print(f"[books] Total results from all engines: {len(all_results)}")
    return all_results
