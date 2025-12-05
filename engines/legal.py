"""
citeflex/engines/legal.py

Legal case search engines.
- FamousCasesCache: Fast lookup for landmark cases (US and UK)
- CourtListenerEngine: Multi-attempt search for case law
- UKCitationParser: Parse UK neutral citations
"""

import re
import difflib
from typing import Optional, List, Dict

from engines.base import SearchEngine, MultiAttemptEngine
from models import CitationMetadata, CitationType
from config import COURTLISTENER_API_KEY


# =============================================================================
# FAMOUS CASES CACHE (US + UK)
# =============================================================================

FAMOUS_CASES: Dict[str, dict] = {
    # =========================================================================
    # US SUPREME COURT - FOUNDATIONAL
    # =========================================================================
    'marbury v madison': {'case_name': 'Marbury v. Madison', 'citation': '5 U.S. 137', 'year': '1803', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'mcculloch v maryland': {'case_name': 'McCulloch v. Maryland', 'citation': '17 U.S. 316', 'year': '1819', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'gibbons v ogden': {'case_name': 'Gibbons v. Ogden', 'citation': '22 U.S. 1', 'year': '1824', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'dred scott v sandford': {'case_name': 'Dred Scott v. Sandford', 'citation': '60 U.S. 393', 'year': '1857', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'plessy v ferguson': {'case_name': 'Plessy v. Ferguson', 'citation': '163 U.S. 537', 'year': '1896', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'lochner v new york': {'case_name': 'Lochner v. New York', 'citation': '198 U.S. 45', 'year': '1905', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'schenck v united states': {'case_name': 'Schenck v. United States', 'citation': '249 U.S. 47', 'year': '1919', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'korematsu v united states': {'case_name': 'Korematsu v. United States', 'citation': '323 U.S. 214', 'year': '1944', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    
    # CIVIL RIGHTS ERA
    'brown v board': {'case_name': 'Brown v. Board of Education', 'citation': '347 U.S. 483', 'year': '1954', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'brown v board of education': {'case_name': 'Brown v. Board of Education', 'citation': '347 U.S. 483', 'year': '1954', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'mapp v ohio': {'case_name': 'Mapp v. Ohio', 'citation': '367 U.S. 643', 'year': '1961', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'gideon v wainwright': {'case_name': 'Gideon v. Wainwright', 'citation': '372 U.S. 335', 'year': '1963', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'nyt v sullivan': {'case_name': 'New York Times Co. v. Sullivan', 'citation': '376 U.S. 254', 'year': '1964', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'new york times v sullivan': {'case_name': 'New York Times Co. v. Sullivan', 'citation': '376 U.S. 254', 'year': '1964', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'griswold v connecticut': {'case_name': 'Griswold v. Connecticut', 'citation': '381 U.S. 479', 'year': '1965', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'loving v virginia': {'case_name': 'Loving v. Virginia', 'citation': '388 U.S. 1', 'year': '1967', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'miranda v arizona': {'case_name': 'Miranda v. Arizona', 'citation': '384 U.S. 436', 'year': '1966', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'tinker v des moines': {'case_name': 'Tinker v. Des Moines Indep. Community School Dist.', 'citation': '393 U.S. 503', 'year': '1969', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'brandenburg v ohio': {'case_name': 'Brandenburg v. Ohio', 'citation': '395 U.S. 444', 'year': '1969', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    
    # 1970s-1980s
    'roe v wade': {'case_name': 'Roe v. Wade', 'citation': '410 U.S. 113', 'year': '1973', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'united states v nixon': {'case_name': 'United States v. Nixon', 'citation': '418 U.S. 683', 'year': '1974', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'regents v bakke': {'case_name': 'Regents of the University of California v. Bakke', 'citation': '438 U.S. 265', 'year': '1978', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'chevron v nrdc': {'case_name': 'Chevron U.S.A. Inc. v. Natural Resources Defense Council, Inc.', 'citation': '467 U.S. 837', 'year': '1984', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    
    # MODERN ERA
    'bush v gore': {'case_name': 'Bush v. Gore', 'citation': '531 U.S. 98', 'year': '2000', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'lawrence v texas': {'case_name': 'Lawrence v. Texas', 'citation': '539 U.S. 558', 'year': '2003', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'dc v heller': {'case_name': 'District of Columbia v. Heller', 'citation': '554 U.S. 570', 'year': '2008', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'district of columbia v heller': {'case_name': 'District of Columbia v. Heller', 'citation': '554 U.S. 570', 'year': '2008', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'citizens united v fec': {'case_name': 'Citizens United v. FEC', 'citation': '558 U.S. 310', 'year': '2010', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'obergefell v hodges': {'case_name': 'Obergefell v. Hodges', 'citation': '576 U.S. 644', 'year': '2015', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'montgomery v louisiana': {'case_name': 'Montgomery v. Louisiana', 'citation': '577 U.S. 190', 'year': '2016', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'dobbs v jackson': {'case_name': "Dobbs v. Jackson Women's Health Organization", 'citation': '597 U.S. 215', 'year': '2022', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    
    # STATE COURTS
    'palsgraf v lirr': {'case_name': 'Palsgraf v. Long Island R.R. Co.', 'citation': '248 N.Y. 339', 'year': '1928', 'court': 'N.Y.', 'jurisdiction': 'US'},
    'macpherson v buick': {'case_name': 'MacPherson v. Buick Motor Co.', 'citation': '217 N.Y. 382', 'year': '1916', 'court': 'N.Y.', 'jurisdiction': 'US'},
    'tarasoff v regents': {'case_name': 'Tarasoff v. Regents of the University of California', 'citation': '17 Cal. 3d 425', 'year': '1976', 'court': 'Cal.', 'jurisdiction': 'US'},
    'in re quinlan': {'case_name': 'In re Quinlan', 'citation': '355 A.2d 647', 'year': '1976', 'court': 'N.J.', 'jurisdiction': 'US'},
    'greenspan v osheroff': {'case_name': 'Greenspan v. Osheroff', 'citation': '232 Va. 388', 'year': '1986', 'court': 'Supreme Court of Virginia', 'jurisdiction': 'US'},
    
    # FEDERAL CIRCUIT
    'united states v carroll towing': {'case_name': 'United States v. Carroll Towing Co.', 'citation': '159 F.2d 169', 'year': '1947', 'court': '2d Cir.', 'jurisdiction': 'US'},
    'kitzmiller v dover': {'case_name': 'Kitzmiller v. Dover Area School Dist.', 'citation': '400 F. Supp. 2d 707', 'year': '2005', 'court': 'M.D. Pa.', 'jurisdiction': 'US'},
    
    # =========================================================================
    # UK CASES - FOUNDATIONAL
    # =========================================================================
    'donoghue v stevenson': {'case_name': 'Donoghue v Stevenson', 'citation': '[1932] AC 562', 'year': '1932', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'carlill v carbolic smoke ball': {'case_name': 'Carlill v Carbolic Smoke Ball Company', 'citation': '[1893] 1 QB 256', 'year': '1893', 'court': 'Court of Appeal', 'jurisdiction': 'UK'},
    'hadley v baxendale': {'case_name': 'Hadley v Baxendale', 'citation': '(1854) 9 Exch 341', 'year': '1854', 'court': 'Court of Exchequer', 'jurisdiction': 'UK'},
    'rylands v fletcher': {'case_name': 'Rylands v Fletcher', 'citation': '(1868) LR 3 HL 330', 'year': '1868', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'salomon v salomon': {'case_name': 'Salomon v A Salomon & Co Ltd', 'citation': '[1897] AC 22', 'year': '1897', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    
    # UK CRIMINAL LAW
    'r v woollin': {'case_name': 'R v Woollin', 'citation': '[1999] 1 AC 82', 'year': '1999', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'r v brown': {'case_name': 'R v Brown', 'citation': '[1994] 1 AC 212', 'year': '1994', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'r v nedrick': {'case_name': 'R v Nedrick', 'citation': '[1986] 1 WLR 1025', 'year': '1986', 'court': 'Court of Appeal', 'jurisdiction': 'UK'},
    'r v cunningham': {'case_name': 'R v Cunningham', 'citation': '[1957] 2 QB 396', 'year': '1957', 'court': "Queen's Bench", 'jurisdiction': 'UK'},
    'r v ghosh': {'case_name': 'R v Ghosh', 'citation': '[1982] QB 1053', 'year': '1982', 'court': 'Court of Appeal', 'jurisdiction': 'UK'},
    'r v dica': {'case_name': 'R v Dica', 'citation': '[2004] EWCA Crim 1103', 'year': '2004', 'court': 'Court of Appeal', 'jurisdiction': 'UK'},
    
    # UK TORT LAW
    'caparo v dickman': {'case_name': 'Caparo Industries plc v Dickman', 'citation': '[1990] 2 AC 605', 'year': '1990', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'anns v merton': {'case_name': 'Anns v Merton London Borough Council', 'citation': '[1978] AC 728', 'year': '1978', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'hedley byrne v heller': {'case_name': 'Hedley Byrne & Co Ltd v Heller & Partners Ltd', 'citation': '[1964] AC 465', 'year': '1964', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'bolton v stone': {'case_name': 'Bolton v Stone', 'citation': '[1951] AC 850', 'year': '1951', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    
    # UK CONTRACT LAW
    'balfour v balfour': {'case_name': 'Balfour v Balfour', 'citation': '[1919] 2 KB 571', 'year': '1919', 'court': 'Court of Appeal', 'jurisdiction': 'UK'},
    'williams v roffey': {'case_name': 'Williams v Roffey Bros & Nicholls (Contractors) Ltd', 'citation': '[1991] 1 QB 1', 'year': '1991', 'court': 'Court of Appeal', 'jurisdiction': 'UK'},
    'central london property v high trees': {'case_name': 'Central London Property Trust Ltd v High Trees House Ltd', 'citation': '[1947] KB 130', 'year': '1947', 'court': "King's Bench", 'jurisdiction': 'UK'},
    'hong kong fir v kawasaki': {'case_name': 'Hong Kong Fir Shipping Co Ltd v Kawasaki Kisen Kaisha Ltd', 'citation': '[1962] 2 QB 26', 'year': '1962', 'court': 'Court of Appeal', 'jurisdiction': 'UK'},
    
    # UK CONSTITUTIONAL/PUBLIC LAW
    'entick v carrington': {'case_name': 'Entick v Carrington', 'citation': '(1765) 19 St Tr 1029', 'year': '1765', 'court': 'Court of Common Pleas', 'jurisdiction': 'UK'},
    'r v secretary of state ex parte factortame': {'case_name': 'R v Secretary of State for Transport, ex parte Factortame Ltd (No 2)', 'citation': '[1991] 1 AC 603', 'year': '1991', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'factortame': {'case_name': 'R v Secretary of State for Transport, ex parte Factortame Ltd (No 2)', 'citation': '[1991] 1 AC 603', 'year': '1991', 'court': 'House of Lords', 'jurisdiction': 'UK'},
    'r miller v secretary of state': {'case_name': 'R (Miller) v Secretary of State for Exiting the European Union', 'citation': '[2017] UKSC 5', 'year': '2017', 'court': 'Supreme Court', 'jurisdiction': 'UK'},
    'miller': {'case_name': 'R (Miller) v Secretary of State for Exiting the European Union', 'citation': '[2017] UKSC 5', 'year': '2017', 'court': 'Supreme Court', 'jurisdiction': 'UK'},
    'cherry miller': {'case_name': 'R (Miller) v The Prime Minister', 'citation': '[2019] UKSC 41', 'year': '2019', 'court': 'Supreme Court', 'jurisdiction': 'UK'},
    'gchq': {'case_name': 'Council of Civil Service Unions v Minister for the Civil Service', 'citation': '[1985] AC 374', 'year': '1985', 'court': 'House of Lords', 'jurisdiction': 'UK'},
}


def _normalize_case_key(text: str) -> str:
    """Normalize text for cache lookup."""
    text = text.lower()
    text = text.replace('.', '').replace(',', '').replace(':', '').replace(';', '')
    text = re.sub(r'\b(vs|versus)\b', 'v', text)
    return " ".join(text.split())


class FamousCasesCache(SearchEngine):
    """
    Fast lookup for landmark cases.
    No API calls - instant results for ~65+ famous US and UK cases.
    """
    
    name = "Famous Cases Cache"
    
    # Short-form aliases for common searches
    ALIASES = {
        'dobbs': 'dobbs v jackson',
        'obergefell': 'obergefell v hodges',
        'citizens united': 'citizens united v fec',
        'heller': 'dc v heller',
        'dred scott': 'dred scott v sandford',
        'miranda': 'miranda v arizona',
        'roe': 'roe v wade',
        'brown': 'brown v board',
        'loving': 'loving v virginia',
        'marbury': 'marbury v madison',
        'chevron': 'chevron v nrdc',
        'griswold': 'griswold v connecticut',
        'gideon': 'gideon v wainwright',
        'mapp': 'mapp v ohio',
        'tinker': 'tinker v des moines',
        'lawrence': 'lawrence v texas',
        'bush': 'bush v gore',
        'bakke': 'regents v bakke',
        'nixon': 'united states v nixon',
        'korematsu': 'korematsu v united states',
        'schenck': 'schenck v united states',
        'plessy': 'plessy v ferguson',
        'lochner': 'lochner v new york',
        'palsgraf': 'palsgraf v lirr',
        'tarasoff': 'tarasoff v regents',
        'quinlan': 'in re quinlan',
        'osheroff': 'greenspan v osheroff',
        # UK aliases
        'donoghue': 'donoghue v stevenson',
        'snail': 'donoghue v stevenson',
        'carbolic smoke ball': 'carlill v carbolic smoke ball',
        'carlill': 'carlill v carbolic smoke ball',
        'hadley': 'hadley v baxendale',
        'rylands': 'rylands v fletcher',
        'salomon': 'salomon v salomon',
        'woollin': 'r v woollin',
        'caparo': 'caparo v dickman',
        'hedley byrne': 'hedley byrne v heller',
        'balfour': 'balfour v balfour',
        'high trees': 'central london property v high trees',
        'hong kong fir': 'hong kong fir v kawasaki',
        'entick': 'entick v carrington',
    }
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        clean_key = _normalize_case_key(query)
        
        # Exact match
        if clean_key in FAMOUS_CASES:
            return self._from_cache(FAMOUS_CASES[clean_key], query)
        
        # Check aliases
        for alias, full_key in self.ALIASES.items():
            if alias in clean_key:
                if full_key in FAMOUS_CASES:
                    return self._from_cache(FAMOUS_CASES[full_key], query)
        
        # Fuzzy match with lower cutoff for short queries
        cutoff = 0.5 if len(clean_key) < 15 else 0.6
        matches = difflib.get_close_matches(clean_key, FAMOUS_CASES.keys(), n=1, cutoff=cutoff)
        if matches:
            return self._from_cache(FAMOUS_CASES[matches[0]], query)
        
        return None
    
    def search_multiple(self, query: str, limit: int = 5) -> List[CitationMetadata]:
        """
        Search for multiple matches. For famous cases, we typically have one match,
        but we can return fuzzy matches if requested.
        """
        results = []
        clean_key = _normalize_case_key(query)
        
        # Exact match
        if clean_key in FAMOUS_CASES:
            results.append(self._from_cache(FAMOUS_CASES[clean_key], query))
            if len(results) >= limit:
                return results
        
        # Check aliases
        for alias, full_key in self.ALIASES.items():
            if alias in clean_key and full_key in FAMOUS_CASES:
                result = self._from_cache(FAMOUS_CASES[full_key], query)
                if not any(r.case_name == result.case_name for r in results):
                    results.append(result)
                    if len(results) >= limit:
                        return results
        
        # Fuzzy matches
        cutoff = 0.4  # Lower cutoff to get more matches
        matches = difflib.get_close_matches(clean_key, FAMOUS_CASES.keys(), n=limit, cutoff=cutoff)
        for match_key in matches:
            result = self._from_cache(FAMOUS_CASES[match_key], query)
            if not any(r.case_name == result.case_name for r in results):
                results.append(result)
                if len(results) >= limit:
                    break
        
        return results
    
    def _from_cache(self, data: dict, raw_source: str) -> CitationMetadata:
        return CitationMetadata(
            citation_type=CitationType.LEGAL,
            raw_source=raw_source,
            source_engine=self.name,
            case_name=data.get('case_name', ''),
            citation=data.get('citation', ''),
            year=data.get('year'),
            court=data.get('court', ''),
            jurisdiction=data.get('jurisdiction', 'US'),
        )


# =============================================================================
# UK CITATION PARSER
# =============================================================================

class UKCitationParser(SearchEngine):
    """
    Parse UK neutral citations like [2024] UKSC 123.
    No API calls - purely regex-based extraction.
    """
    
    name = "UK Citation Parser"
    
    UK_COURTS = {
        'UKSC': 'Supreme Court',
        'UKHL': 'House of Lords',
        'UKPC': 'Privy Council',
        'EWCA': 'Court of Appeal',
        'EWHC': 'High Court',
        'EWCOP': 'Court of Protection',
        'UKUT': 'Upper Tribunal',
        'UKFTT': 'First-tier Tribunal',
        'EWFC': 'Family Court',
        'UKIPO': 'Intellectual Property Office',
        'UKEAT': 'Employment Appeal Tribunal',
    }
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        # Pattern: [YEAR] COURT NUMBER
        pattern = r'\[(\d{4})\]\s*([A-Z]{2,6})\s*(?:\([^)]+\))?\s*(\d+)'
        match = re.search(pattern, query)
        
        if not match:
            return None
        
        year, court_code, number = match.groups()
        
        court_name = self.UK_COURTS.get(court_code, court_code)
        neutral_citation = f"[{year}] {court_code} {number}"
        
        return CitationMetadata(
            citation_type=CitationType.LEGAL,
            raw_source=query,
            source_engine=self.name,
            neutral_citation=neutral_citation,
            year=year,
            court=court_name,
            jurisdiction='UK',
            case_name=query,  # Use raw query as case name placeholder
        )


# =============================================================================
# COURTLISTENER ENGINE
# =============================================================================

class CourtListenerEngine(MultiAttemptEngine):
    """
    Search CourtListener for US case law.
    
    Uses a 4-attempt strategy:
    1. Exact phrase search
    2. Keyword search
    3. Fuzzy search
    4. Plaintiff-only (for cases like "Smith v. Jones")
    """
    
    name = "CourtListener"
    base_url = "https://www.courtlistener.com/api/rest/v4/search/"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key or COURTLISTENER_API_KEY
        super().__init__(**kwargs)
    
    def get_headers(self) -> dict:
        headers = {
            'User-Agent': 'CiteFlex/2.0 (Academic Citation Tool)',
            'Accept': 'application/json',
        }
        if self.api_key:
            headers['Authorization'] = f'Token {self.api_key}'
        return headers
    
    def get_search_attempts(self, query: str) -> List[dict]:
        """Define 4-attempt search strategy."""
        # Clean query
        smart_query = self._clean_query(query)
        fuzzy_query = self._make_fuzzy(smart_query)
        plaintiff, defendant = self._extract_parties(query)
        
        attempts = [
            # Attempt 1: Exact phrase
            {
                'name': 'phrase',
                'params': {'q': f'"{query}"', 'type': 'o', 'order_by': 'score desc', 'format': 'json'}
            },
            # Attempt 2: Keywords
            {
                'name': 'keyword',
                'params': {'q': smart_query, 'type': 'o', 'order_by': 'score desc', 'format': 'json'}
            },
            # Attempt 3: Fuzzy
            {
                'name': 'fuzzy',
                'params': {'q': fuzzy_query, 'type': 'o', 'order_by': 'score desc', 'format': 'json'}
            },
        ]
        
        # Attempt 4: Plaintiff-only (if extracted and not generic)
        if plaintiff and len(plaintiff) > 4:
            generic = ['state', 'people', 'united', 'states', 'board', 'city', 'county', 'in re']
            if plaintiff.lower() not in generic:
                attempts.append({
                    'name': f'plaintiff ({plaintiff})',
                    'params': {'q': plaintiff, 'type': 'o', 'order_by': 'score desc', 'format': 'json'},
                    'match_plaintiff': plaintiff.lower()
                })
        
        return attempts
    
    def parse_response(self, response, query: str) -> Optional[CitationMetadata]:
        """Parse CourtListener response."""
        try:
            data = response.json()
            results = data.get('results', [])
            
            for result in results[:10]:
                case_name = result.get('caseName') or result.get('case_name')
                if case_name:
                    return self._normalize(result, query)
            
            return None
        except:
            return None
    
    def parse_response_multiple(self, response, query: str, limit: int = 5) -> List[CitationMetadata]:
        """Parse CourtListener response for multiple results."""
        results = []
        try:
            data = response.json()
            api_results = data.get('results', [])
            
            for result in api_results[:limit]:
                case_name = result.get('caseName') or result.get('case_name')
                if case_name:
                    results.append(self._normalize(result, query))
            
            return results
        except:
            return results
    
    def search_multiple(self, query: str, limit: int = 5) -> List[CitationMetadata]:
        """Search and return multiple results."""
        import requests
        
        attempts = self.get_search_attempts(query)
        
        for attempt in attempts:
            try:
                response = requests.get(
                    self.base_url,
                    params=attempt['params'],
                    headers=self.get_headers(),
                    timeout=10
                )
                
                if response.status_code == 200:
                    results = self.parse_response_multiple(response, query, limit)
                    if results:
                        return results
            except:
                continue
        
        return []
    
    def _normalize(self, item: dict, raw_source: str) -> CitationMetadata:
        """Convert CourtListener response to CitationMetadata."""
        # Get year from date filed
        year = None
        date_filed = item.get('dateFiled') or item.get('date_filed', '')
        if date_filed:
            year_match = re.match(r'(\d{4})', date_filed)
            if year_match:
                year = year_match.group(1)
        
        # Handle citations (can be string or list)
        citation = ''
        cits = item.get('citation') or item.get('citations')
        if cits:
            citation = cits[0] if isinstance(cits, list) else cits
        
        # Build URL
        url = ''
        if item.get('absolute_url'):
            url = f"https://www.courtlistener.com{item['absolute_url']}"
        
        return CitationMetadata(
            citation_type=CitationType.LEGAL,
            raw_source=raw_source,
            source_engine=self.name,
            case_name=item.get('caseName') or item.get('case_name', ''),
            citation=citation,
            year=year,
            court=item.get('court', ''),
            jurisdiction='US',
            url=url,
            raw_data=item
        )
    
    @staticmethod
    def _clean_query(query: str) -> str:
        """Remove 'v.' and special chars."""
        clean = re.sub(r'\s+v\.?\s+', ' ', query, flags=re.IGNORECASE)
        clean = re.sub(r'[^\w\s]', '', clean)
        return clean.strip()
    
    @staticmethod
    def _make_fuzzy(query: str) -> str:
        """Convert to fuzzy search (term~)."""
        terms = query.split()
        fuzzy = []
        for t in terms:
            if len(t) > 3 and not t.isdigit():
                fuzzy.append(f"{t}~")
            else:
                fuzzy.append(t)
        return " ".join(fuzzy)
    
    @staticmethod
    def _extract_parties(query: str) -> tuple:
        """Extract plaintiff and defendant."""
        parts = re.split(r'\s+v\.?\s+', query, flags=re.IGNORECASE)
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
        return None, None


# =============================================================================
# COMPOSITE LEGAL ENGINE
# =============================================================================

class LegalSearchEngine(SearchEngine):
    """
    Composite engine that tries multiple legal sources in order:
    1. UK Citation Parser (for UK neutral citations)
    2. Famous Cases Cache (instant lookup)
    3. CourtListener (API search)
    """
    
    name = "Legal Search"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(api_key=api_key, **kwargs)
        self.uk_parser = UKCitationParser()
        self.cache = FamousCasesCache()
        self.court_listener = CourtListenerEngine(api_key=api_key, **kwargs)
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        # 1. UK neutral citation?
        if '[' in query and ']' in query:
            result = self.uk_parser.search(query)
            if result:
                return result
        
        # 2. Famous case?
        result = self.cache.search(query)
        if result:
            return result
        
        # 3. CourtListener search
        return self.court_listener.search(query)
    
    def search_multiple(self, query: str, limit: int = 5) -> List[CitationMetadata]:
        """
        Search for multiple legal case results.
        
        For legal cases, we prioritize:
        1. Famous Cases Cache (most reliable, instant)
        2. CourtListener API (for obscure cases)
        """
        results = []
        seen_names = set()
        
        def add_result(r: CitationMetadata) -> bool:
            """Add result if not duplicate. Returns True if limit reached."""
            name_key = r.case_name.lower().strip()[:50] if r.case_name else ''
            if name_key and name_key not in seen_names:
                seen_names.add(name_key)
                results.append(r)
                return len(results) >= limit
            return False
        
        # 1. UK neutral citation?
        if '[' in query and ']' in query:
            result = self.uk_parser.search(query)
            if result:
                if add_result(result):
                    return results
        
        # 2. Famous cases (can return multiple fuzzy matches)
        cache_results = self.cache.search_multiple(query, limit=limit)
        for r in cache_results:
            if add_result(r):
                return results
        
        # 3. CourtListener (if we still need more results)
        if len(results) < limit:
            remaining = limit - len(results)
            cl_results = self.court_listener.search_multiple(query, limit=remaining)
            for r in cl_results:
                if add_result(r):
                    return results
        
        return results
