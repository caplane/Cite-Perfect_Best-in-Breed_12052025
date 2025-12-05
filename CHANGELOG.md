# CiteFlex Unified - Changelog

## Version 1.1.0 (2025-12-05 13:26)

### Surgical Fixes Applied
All changes made via str_replace (surgical edits, not regeneration).

#### court.py V28.2
- Added Westlaw pattern (2024 WL 123456) to is_legal_citation()
- Added Federal Reporter pattern (123 F.3d 456) to is_legal_citation()
- Added U.S. Reports pattern (388 U.S. 1) to is_legal_citation()
- Added Atlantic/Pacific reporter pattern (355 A.2d 647)
- All 65 cached cases verified (336K ops/sec)

#### detectors.py
- Added Westlaw citation pattern to reporter_patterns list
- Verified Federal Reporter pattern (was already present)
- Medical .gov domains correctly excluded from government detection

#### formatters/legal.py
- Fixed OSCOLA _format_case to include year for US cases
- Pattern: Case Name, Citation (Year) for US; Case Name [Year] for UK

### Test Results
- **Pass Rate**: 100.0% (231/231 tests)
- **All 10 Test Suites**: ✅ PASS
- **Duration**: 0.05 seconds

### Files with Version Headers Updated
- unified_router.py: V1.1 (2025-12-05 13:15)
- court.py: V28.2 (2025-12-05 13:22)
- detectors.py: (2025-12-05 13:15)
- books.py: (2025-12-05 13:15)
- document_processor.py: (2025-12-05 13:15)
- formatters/legal.py: (2025-12-05 13:05)

---

## Version 1.0.0 (2025-12-05 12:53)

### Initial Unified Release
Combines CiteFlex Pro (academic engines) with Cite Fix Pro (legal cache, book engines) into a single best-in-breed citation management system.

### Core Features
- **65 Landmark Cases**: Instant lookup with no API calls required
- **5 Citation Styles**: Chicago Manual of Style, APA, MLA, Bluebook, OSCOLA
- **7 Citation Types**: Legal, Journal, Book, Medical, Interview, Newspaper, Government
- **40+ Publishers**: Automatic place-of-publication mapping
- **Parallel Execution**: ThreadPoolExecutor with 12s timeout for academic searches

### Files Modified (2025-12-05)

#### books.py
- Expanded PUBLISHER_PLACE_MAP from 19 to 42 publishers
- Added: Basic Books, Free Press, Johns Hopkins, Duke, Cornell, UPenn, UNC, UVA, Michigan, Wisconsin, Illinois, Indiana, Texas, Washington, Palgrave Macmillan, Vintage, Doubleday, Scribner, Little Brown, Beacon Press, Houghton Mifflin

#### document_processor.py
- Enhanced IBID_PATTERN to recognize "Id." (Bluebook short form)
- Added "pp." prefix support for page extraction
- Switched import from `router` to `unified_router`

#### detectors.py
- Fixed medical .gov URL routing (PubMed, NIH, NIMH now route to MEDICAL)
- Excluded medical domains from is_government detection
- Added explicit medical .gov domain list

#### extractors.py
- Added multiple date patterns for newspaper URLs
- Pattern 1: /YYYY/MM/DD/ (NYT, WaPo style)
- Pattern 2: /YYYY-MM-DD/ (LA Times style)
- Pattern 3: /story/YYYY-MM-DD/ (alternate style)

#### config.py
- Fixed get_gov_agency to check more specific domains first
- Prevents 'nih.gov' from matching before 'nimh.nih.gov'

#### court.py
- Added case aliases: "brown v board of education", "palsgraf v long island"
- Updated version to V28

#### unified_router.py
- Added version tracking header
- Version 1.0.0

### Test Results
- **Pass Rate**: 96.6% (227/235 tests)
- **Perfect Scores**: Extractors, Ibid Handling, Unified Router, Edge Cases, Style Consistency
- **Performance**: 336,000+ cache lookups/sec, 1.2M+ formats/sec

### Known Limitations
- Bare reporter citations (e.g., "388 U.S. 1") without case name not detected as legal
- "Oral history with [Person]" pattern not recognized as interview
- Interview formatting limited in Bluebook/OSCOLA (no standard format)
- Concurrent routing may fail for uncached cases when APIs are blocked

---

## Pre-Release History

### CiteFlex Pro (Original)
- Academic engines: Crossref, OpenAlex, Semantic Scholar, PubMed
- 5 formatters with consistent period termination
- URL handling with DOI extraction

### Cite Fix Pro (Original)
- Legal cache with 63 landmark cases
- CourtListener API integration
- Book engines: Open Library, Google Books
- Publisher-to-place mapping
