"""
citeflex/engines/superlegal.py

Unified Legal Citation Engine - Merged from court.py + legal.py

Version History:
    2025-12-05 20:00: Created by merging court.py (V28.1) and legal.py
                      - Base: legal.py SearchEngine architecture
                      - Added: 25+ cases from court.py (state courts, federal circuit, tech)
                      - Added: Case aliases (palsgraf lirr, kitzmiller, etc.)
                      - Added: is_legal_citation() with Westlaw/F.2d patterns
                      - Added: Backward-compatible extract_metadata() wrapper

Features:
- 90+ landmark cases (US + UK) with instant cache lookup
- Fuzzy matching for case name variants
- CourtListener API integration (phrase search + fuzzy fallbacks)
- UK neutral citation parsing
- Proper SearchEngine base class architecture
"""

import re
import difflib
import requests
import time
from typing import Optional, List, Dict
from urllib.parse import urlparse, unquote

from engines.base import SearchEngine
from models import CitationMetadata, CitationType
from config import COURTLISTENER_API_KEY


# =============================================================================
# FAMOUS CASES CACHE (US + UK) - MERGED
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
    'wickard v filburn': {'case_name': 'Wickard v. Filburn', 'citation': '317 U.S. 111', 'year': '1942', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    
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
    'cruzan v missouri': {'case_name': 'Cruzan v. Director, Missouri Department of Health', 'citation': '497 U.S. 261', 'year': '1990', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    
    # MODERN ERA
    'bush v gore': {'case_name': 'Bush v. Gore', 'citation': '531 U.S. 98', 'year': '2000', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'lawrence v texas': {'case_name': 'Lawrence v. Texas', 'citation': '539 U.S. 558', 'year': '2003', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'dc v heller': {'case_name': 'District of Columbia v. Heller', 'citation': '554 U.S. 570', 'year': '2008', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'district of columbia v heller': {'case_name': 'District of Columbia v. Heller', 'citation': '554 U.S. 570', 'year': '2008', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'citizens united v fec': {'case_name': 'Citizens United v. FEC', 'citation': '558 U.S. 310', 'year': '2010', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'obergefell v hodges': {'case_name': 'Obergefell v. Hodges', 'citation': '576 U.S. 644', 'year': '2015', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'montgomery v louisiana': {'case_name': 'Montgomery v. Louisiana', 'citation': '577 U.S. 190', 'year': '2016', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    'dobbs v jackson': {'case_name': "Dobbs v. Jackson Women's Health Organization", 'citation': '597 U.S. 215', 'year': '2022', 'court': 'Supreme Court of the United States', 'jurisdiction': 'US'},
    
    # =========================================================================
    # US STATE COURTS (from court.py)
    # =========================================================================
    # New York
    'palsgraf v lirr': {'case_name': 'Palsgraf v. Long Island R.R. Co.', 'citation': '248 N.Y. 339', 'year': '1928', 'court': 'N.Y.', 'jurisdiction': 'US'},
    'palsgraf v long island': {'case_name': 'Palsgraf v. Long Island R.R. Co.', 'citation': '248 N.Y. 339', 'year': '1928', 'court': 'N.Y.', 'jurisdiction': 'US'},
    'palsgraf lirr': {'case_name': 'Palsgraf v. Long Island R.R. Co.', 'citation': '248 N.Y. 339', 'year': '1928', 'court': 'N.Y.', 'jurisdiction': 'US'},
    'macpherson v buick': {'case_name': 'MacPherson v. Buick Motor Co.', 'citation': '217 N.Y. 382', 'year': '1916', 'court': 'N.Y.', 'jurisdiction': 'US'},
    'people v goetz': {'case_name': 'People v. Goetz', 'citation': '68 N.Y.2d 96', 'year': '1986', 'court': 'N.Y.', 'jurisdiction': 'US'},
    'jacob and youngs v kent': {'case_name': 'Jacob & Youngs, Inc. v. Kent', 'citation': '230 N.Y. 239', 'year': '1921', 'court': 'N.Y.', 'jurisdiction': 'US'},
    
    # California
    'tarasoff v regents': {'case_name': 'Tarasoff v. Regents of the University of California', 'citation': '17 Cal. 3d 425', 'year': '1976', 'court': 'Cal.', 'jurisdiction': 'US'},
    'grimshaw v ford motor co': {'case_name': 'Grimshaw v. Ford Motor Co.', 'citation': '119 Cal. App. 3d 757', 'year': '1981', 'court': 'Cal. Ct. App.', 'jurisdiction': 'US'},
    'people v turner': {'case_name': 'People v. Turner', 'citation': 'No. 15014799', 'year': '2016', 'court': 'Cal. Super. Ct.', 'jurisdiction': 'US'},
    
    # Other States
    'hawkins v mcgee': {'case_name': 'Hawkins v. McGee', 'citation': '84 N.H. 114', 'year': '1929', 'court': 'N.H.', 'jurisdiction': 'US'},
    'lucy v zehmer': {'case_name': 'Lucy v. Zehmer', 'citation': '196 Va. 493', 'year': '1954', 'court': 'Va.', 'jurisdiction': 'US'},
    'sherwood v walker': {'case_name': 'Sherwood v. Walker', 'citation': '66 Mich. 568', 'year': '1887', 'court': 'Mich.', 'jurisdiction': 'US'},
    'in re quinlan': {'case_name': 'In re Quinlan', 'citation': '355 A.2d 647', 'year': '1976', 'court': 'N.J.', 'jurisdiction': 'US'},
    'in re baby m': {'case_name': 'In re Baby M', 'citation': '537 A.2d 1227', 'year': '1988', 'court': 'N.J.', 'jurisdiction': 'US'},
    'commonwealth v hunt': {'case_name': 'Commonwealth v. Hunt', 'citation': '45 Mass. 111', 'year': '1842', 'court': 'Mass.', 'jurisdiction': 'US'},
    'greenspan v osheroff': {'case_name': 'Greenspan v. Osheroff', 'citation': '232 Va. 388', 'year': '1986', 'court': 'Supreme Court of Virginia', 'jurisdiction': 'US'},
    
    # =========================================================================
    # US FEDERAL CIRCUIT COURTS (from court.py)
    # =========================================================================
    # District Courts
    'a&m records v napster': {'case_name': 'A&M Records, Inc. v. Napster, Inc.', 'citation': '114 F. Supp. 2d 896', 'year': '2000', 'court': 'N.D. Cal.', 'jurisdiction': 'US'},
    'kitzmiller v dover': {'case_name': 'Kitzmiller v. Dover Area School Dist.', 'citation': '400 F. Supp. 2d 707', 'year': '2005', 'court': 'M.D. Pa.', 'jurisdiction': 'US'},
    'kitzmiller': {'case_name': 'Kitzmiller v. Dover Area School Dist.', 'citation': '400 F. Supp. 2d 707', 'year': '2005', 'court': 'M.D. Pa.', 'jurisdiction': 'US'},
    'floyd v city of new york': {'case_name': 'Floyd v. City of New York', 'citation': '959 F. Supp. 2d 540', 'year': '2013', 'court': 'S.D.N.Y.', 'jurisdiction': 'US'},
    'jones v clinton': {'case_name': 'Jones v. Clinton', 'citation': '990 F. Supp. 657', 'year': '1998', 'court': 'E.D. Ark.', 'jurisdiction': 'US'},
    'united states v oliver north': {'case_name': 'United States v. North', 'citation': '708 F. Supp. 380', 'year': '1988', 'court': 'D.D.C.', 'jurisdiction': 'US'},
    
    # Circuit Courts
    'united states v microsoft': {'case_name': 'United States v. Microsoft Corp.', 'citation': '253 F.3d 34', 'year': '2001', 'court': 'D.C. Cir.', 'jurisdiction': 'US'},
    'united states v microsoft corp': {'case_name': 'United States v. Microsoft Corp.', 'citation': '253 F.3d 34', 'year': '2001', 'court': 'D.C. Cir.', 'jurisdiction': 'US'},
    'buckley v valeo': {'case_name': 'Buckley v. Valeo', 'citation': '519 F.2d 821', 'year': '1975', 'court': 'D.C. Cir.', 'jurisdiction': 'US'},
    'massachusetts v epa': {'case_name': 'Massachusetts v. EPA', 'citation': '415 F.3d 50', 'year': '2005', 'court': 'D.C. Cir.', 'jurisdiction': 'US'},
    'united states v carroll towing': {'case_name': 'United States v. Carroll Towing Co.', 'citation': '159 F.2d 169', 'year': '1947', 'court': '2d Cir.', 'jurisdiction': 'US'},
    'authors guild v google': {'case_name': 'Authors Guild v. Google, Inc.', 'citation': '804 F.3d 202', 'year': '2015', 'court': '2d Cir.', 'jurisdiction': 'US'},
    'viacom v youtube': {'case_name': "Viacom Int'l, Inc. v. YouTube, Inc.", 'citation': '676 F.3d 19', 'year': '2012', 'court': '2d Cir.', 'jurisdiction': 'US'},
    'newdow v us congress': {'case_name': 'Newdow v. U.S. Congress', 'citation': '292 F.3d 597', 'year': '2002', 'court': '9th Cir.', 'jurisdiction': 'US'},
    'lenz v universal music': {'case_name': 'Lenz v. Universal Music Corp.', 'citation': '815 F.3d 1145', 'year': '2016', 'court': '9th Cir.', 'jurisdiction': 'US'},
    'lenz v universal music corp': {'case_name': 'Lenz v. Universal Music Corp.', 'citation': '815 F.3d 1145', 'year': '2016', 'court': '9th Cir.', 'jurisdiction': 'US'},
    'state street bank v signature financial': {'case_name': 'State St. Bank & Trust Co. v. Signature Fin. Group', 'citation': '149 F.3d 1368', 'year': '1998', 'court': 'Fed. Cir.', 'jurisdiction': 'US'},
    
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
    'miller v secretary of state': {'case_name': 'R (Miller) v Secretary of State for Exiting the European Union', 'citation': '[2017] UKSC 5', 'year': '2017', 'court': 'Supreme Court', 'jurisdiction': 'UK'},
}


# =============================================================================
# HELPER FUNCTIONS (from court.py)
# =============================================================================

def _normalize_key(text: str) -> str:
    """Aggressively normalize case names for cache lookup."""
    text = text.lower()
    text = text.replace('.', '').replace(',', '').replace(':', '').replace(';', '')
    text = re.sub(r'\b(vs|versus)\b', 'v', text)
    return " ".join(text.split())


def _find_best_cache_match(text: str) -> Optional[str]:
    """Find the best matching key in FAMOUS_CASES using fuzzy matching."""
    clean_key = _normalize_key(text)
    if clean_key in FAMOUS_CASES:
        return clean_key
    matches = difflib.get_close_matches(clean_key, FAMOUS_CASES.keys(), n=1, cutoff=0.7)
    if matches:
        return matches[0]
    return None


def _extract_query_from_url(url: str) -> str:
    """Extract a searchable query from a legal URL."""
    try:
        decoded_url = unquote(url)
        parsed = urlparse(decoded_url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if not path_parts:
            return ""
        slug = path_parts[-1]
        slug = re.sub(r'\.(htm|html|pdf|aspx|php|jsp)$', '', slug, flags=re.IGNORECASE)
        slug = slug.replace('_', ' ').replace('-', ' ').replace('+', ' ')
        slug = re.sub(r'(?<!^)(?=[A-Z])', ' ', slug)
        return slug.strip()
    except:
        return ""


# =============================================================================
# LEGAL CITATION DETECTION (from court.py)
# =============================================================================

KNOWN_LEGAL_DOMAINS = [
    'courtlistener.com', 'oyez.org', 'case.law', 'justia.com',
    'supremecourt.gov', 'law.cornell.edu', 'findlaw.com'
]


def is_legal_citation(text: str) -> bool:
    """
    Check if text appears to be a legal citation.
    
    Detects:
    - UK neutral citations: [2024] UKSC 123
    - Famous cases from cache
    - Legal URLs
    - Case name patterns: X v Y
    - Reporter patterns: Westlaw, Federal Reporter, U.S. Reports, etc.
    """
    if not text:
        return False
    clean = text.strip()
    
    # UK neutral citation: [2024] UKSC 123
    if '[' in clean and ']' in clean and re.search(r'\[\d{4}\]', clean):
        return True
    
    # Check famous cases cache
    if _find_best_cache_match(clean):
        return True
    
    # Legal URLs
    if 'http' in clean and any(d in clean for d in KNOWN_LEGAL_DOMAINS):
        return True
    
    # Case name pattern: X v Y
    if re.search(r'\s(v|vs|versus)\.?\s', clean, re.IGNORECASE):
        return True
    
    # Reporter patterns (US case citations)
    # Westlaw: 2024 WL 123456
    if re.search(r'\d{4}\s+WL\s+\d+', clean):
        return True
    # Federal Reporter: 123 F.2d 456, 123 F.3d 456
    if re.search(r'\d+\s+F\.\d+[a-z]*\s+\d+', clean):
        return True
    # U.S. Reports: 388 U.S. 1
    if re.search(r'\d+\s+U\.S\.\s+\d+', clean):
        return True
    # Atlantic/Pacific reporters: 355 A.2d 647
    if re.search(r'\d+\s+[A-Z]\.\d+[a-z]*\s+\d+', clean):
        return True
    
    return False


# =============================================================================
# UK CITATION PARSER
# =============================================================================

class UKCitationParser(SearchEngine):
    """Parse UK neutral citations like [2024] UKSC 12."""
    
    name = "UK Citation Parser"
    
    # Court code mappings
    UK_COURTS = {
        'UKSC': 'Supreme Court',
        'UKHL': 'House of Lords',
        'EWCA Civ': 'Court of Appeal (Civil)',
        'EWCA Crim': 'Court of Appeal (Criminal)',
        'EWHC': 'High Court',
        'UKPC': 'Privy Council',
        'UKUT': 'Upper Tribunal',
        'UKFTT': 'First-tier Tribunal',
    }
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        """Parse UK neutral citation."""
        match = re.search(r'\[(\d{4})\]\s+(\w+(?:\s+\w+)?)\s+(\d+)', query)
        if not match:
            return None
        
        year, court_code, number = match.groups()
        court_name = self.UK_COURTS.get(court_code, court_code)
        
        # Try to extract case name from query
        case_name = query
        citation_part = match.group(0)
        name_part = query.replace(citation_part, '').strip()
        if name_part:
            case_name = name_part
        
        return CitationMetadata(
            citation_type=CitationType.LEGAL,
            case_name=case_name,
            citation=f'[{year}] {court_code} {number}',
            court=court_name,
            year=year,
            jurisdiction='UK',
            raw_source=query
        )


# =============================================================================
# FAMOUS CASES CACHE ENGINE
# =============================================================================

class FamousCasesCache(SearchEngine):
    """Instant lookup for landmark cases."""
    
    name = "Famous Cases Cache"
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        """Look up a famous case by name."""
        cache_key = _find_best_cache_match(query)
        if not cache_key:
            return None
        
        data = FAMOUS_CASES[cache_key]
        return CitationMetadata(
            citation_type=CitationType.LEGAL,
            case_name=data['case_name'],
            citation=data['citation'],
            court=data['court'],
            year=data['year'],
            jurisdiction=data.get('jurisdiction', 'US'),
            raw_source=query
        )
    
    def search_multiple(self, query: str, limit: int = 5) -> List[CitationMetadata]:
        """Find multiple fuzzy matches in cache."""
        clean_key = _normalize_key(query)
        results = []
        seen = set()
        
        # Exact match first
        if clean_key in FAMOUS_CASES:
            data = FAMOUS_CASES[clean_key]
            results.append(CitationMetadata(
                citation_type=CitationType.LEGAL,
                case_name=data['case_name'],
                citation=data['citation'],
                court=data['court'],
                year=data['year'],
                jurisdiction=data.get('jurisdiction', 'US'),
                raw_source=query
            ))
            seen.add(data['case_name'])
        
        # Fuzzy matches
        matches = difflib.get_close_matches(clean_key, FAMOUS_CASES.keys(), n=limit, cutoff=0.5)
        for match_key in matches:
            data = FAMOUS_CASES[match_key]
            if data['case_name'] not in seen:
                seen.add(data['case_name'])
                results.append(CitationMetadata(
                    citation_type=CitationType.LEGAL,
                    case_name=data['case_name'],
                    citation=data['citation'],
                    court=data['court'],
                    year=data['year'],
                    jurisdiction=data.get('jurisdiction', 'US'),
                    raw_source=query
                ))
                if len(results) >= limit:
                    break
        
        return results


# =============================================================================
# COURTLISTENER API ENGINE
# =============================================================================

class CourtListenerEngine(SearchEngine):
    """
    Multi-attempt search via CourtListener API.
    
    Search strategies:
    1. Phrase search (exact)
    2. Smart query (cleaned)
    3. Fuzzy search (term~)
    4. Plaintiff fallback
    """
    
    name = "CourtListener"
    base_url = "https://www.courtlistener.com/api/rest/v4/search/"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(api_key=api_key or COURTLISTENER_API_KEY, **kwargs)
        self.headers = {
            'Authorization': f'Token {self.api_key}',
            'Content-Type': 'application/json'
        } if self.api_key else {}
    
    def search(self, query: str) -> Optional[CitationMetadata]:
        """Search CourtListener with multiple strategies."""
        result = self._search_api(query)
        if result:
            return self._to_metadata(result, query)
        return None
    
    def search_multiple(self, query: str, limit: int = 5) -> List[CitationMetadata]:
        """Get multiple results from CourtListener."""
        results = []
        seen = set()
        
        # Try phrase search
        api_results = self._api_request(query, f'"{query}"')
        for item in api_results[:limit]:
            meta = self._to_metadata(item, query)
            if meta and meta.case_name not in seen:
                seen.add(meta.case_name)
                results.append(meta)
        
        return results[:limit]
    
    def _search_api(self, query: str) -> Optional[dict]:
        """Try multiple search strategies."""
        # 1. Phrase search
        result = self._try_search(f'"{query}"')
        if result:
            return result
        
        # 2. Smart query (cleaned)
        smart_query = self._clean_query(query)
        if smart_query != query:
            result = self._try_search(smart_query)
            if result:
                return result
        
        # 3. Fuzzy search
        fuzzy_query = self._make_fuzzy(smart_query)
        if fuzzy_query != smart_query:
            time.sleep(0.1)
            result = self._try_search(fuzzy_query)
            if result:
                return result
        
        # 4. Plaintiff fallback
        plaintiff, _ = self._extract_parties(query)
        if plaintiff and len(plaintiff) > 4:
            common = ['state', 'people', 'united', 'states', 'board', 'city', 'county']
            if plaintiff.lower() not in common:
                time.sleep(0.1)
                results = self._api_request(query, plaintiff)
                for r in results[:5]:
                    if plaintiff.lower() in (r.get('caseName', '') or '').lower():
                        return r
        
        return None
    
    def _try_search(self, q: str) -> Optional[dict]:
        """Execute a single search attempt."""
        results = self._api_request(q, q)
        for r in results[:5]:
            if r.get('caseName') or r.get('case_name'):
                return r
        return None
    
    def _api_request(self, original_query: str, search_query: str) -> List[dict]:
        """Make API request to CourtListener."""
        try:
            params = {
                'q': search_query,
                'type': 'o',
                'order_by': 'score desc',
                'format': 'json'
            }
            response = requests.get(
                self.base_url,
                params=params,
                headers=self.headers,
                timeout=8
            )
            if response.status_code == 200:
                return response.json().get('results', [])
        except Exception as e:
            print(f"[CourtListener] Error: {e}")
        return []
    
    def _to_metadata(self, item: dict, query: str) -> Optional[CitationMetadata]:
        """Convert API result to CitationMetadata."""
        case_name = item.get('caseName') or item.get('case_name')
        if not case_name:
            return None
        
        # Extract citation
        cits = item.get('citation') or item.get('citations')
        citation = ''
        if cits:
            citation = cits[0] if isinstance(cits, list) else cits
        
        # Extract year from dateFiled
        year = ''
        df = item.get('dateFiled')
        if df:
            year = str(df)[:4]
        
        # Build URL
        url = ''
        if item.get('absolute_url'):
            url = f"https://www.courtlistener.com{item['absolute_url']}"
        
        return CitationMetadata(
            citation_type=CitationType.LEGAL,
            case_name=case_name,
            citation=citation,
            court=item.get('court', ''),
            year=year,
            jurisdiction='US',
            url=url,
            raw_source=query,
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
        """Search all legal sources in priority order."""
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
        """Search for multiple legal case results."""
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


# =============================================================================
# BACKWARD COMPATIBILITY (for unified_router.py)
# =============================================================================

# Singleton instance for backward compatibility
_legal_engine = None

def _get_engine() -> LegalSearchEngine:
    """Get or create singleton legal engine."""
    global _legal_engine
    if _legal_engine is None:
        _legal_engine = LegalSearchEngine()
    return _legal_engine


def extract_metadata(text: str) -> Optional[dict]:
    """
    Backward-compatible function matching court.py interface.
    
    Returns dict with keys: type, case_name, citation, court, year, 
                           jurisdiction, url, raw_source
    """
    clean = text.strip()
    
    # Handle URLs
    if 'http' in clean:
        search_query = _extract_query_from_url(clean) or clean
        url = clean
    else:
        search_query = clean
        url = ''
    
    # Search using the engine
    engine = _get_engine()
    result = engine.search(search_query)
    
    if result:
        return {
            'type': 'legal',
            'case_name': result.case_name,
            'citation': result.citation,
            'court': result.court,
            'year': result.year,
            'jurisdiction': result.jurisdiction,
            'url': url or result.url,
            'raw_source': text
        }
    
    # Fallback: return basic metadata
    return {
        'type': 'legal',
        'case_name': search_query,
        'citation': '',
        'court': '',
        'year': '',
        'jurisdiction': 'US',
        'url': url,
        'raw_source': text
    }
