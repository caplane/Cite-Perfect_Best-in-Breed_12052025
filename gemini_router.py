"""
citeflex/gemini_router.py

Gemini AI-powered citation type detection for ambiguous inputs.

SECURITY FIX: API key passed in header (x-goog-api-key), not URL.
"""

import re
import json
import requests
from typing import Optional, Tuple

from models import CitationType, CitationMetadata
from config import GEMINI_API_KEY, GEMINI_MODEL, DEFAULT_TIMEOUT


class GeminiRouter:
    """Uses Gemini to classify ambiguous citation queries."""
    
    # SECURITY FIX: Base URL without key parameter
    API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    
    SYSTEM_PROMPT = """Analyze the input and classify as:
journal, book, legal, interview, newspaper, government, medical, url, or unknown.

Respond in JSON only:
{"type": "...", "confidence": 0.0-1.0, "title": "", "authors": [], "year": ""}"""

    def __init__(self, api_key: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT):
        self.api_key = api_key or GEMINI_API_KEY
        self.timeout = timeout
        self.model = GEMINI_MODEL
    
    def classify(self, text: str) -> Tuple[CitationType, Optional[CitationMetadata]]:
        if not self.api_key:
            return CitationType.UNKNOWN, None
        
        try:
            # SECURITY FIX: API key in header, not URL
            url = f"{self.API_URL}/{self.model}:generateContent"
            
            headers = {
                'Content-Type': 'application/json',
                'x-goog-api-key': self.api_key,  # Key in header
            }
            
            payload = {
                'contents': [{'parts': [{'text': f"{self.SYSTEM_PROMPT}\n\nInput:\n{text}"}]}],
                'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 500}
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            
            if response.status_code == 429:
                return CitationType.UNKNOWN, None
            
            response.raise_for_status()
            data = response.json()
            
            candidates = data.get('candidates', [])
            if not candidates:
                return CitationType.UNKNOWN, None
            
            response_text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            return self._parse_response(response_text, text)
            
        except Exception as e:
            print(f"[GeminiRouter] Error: {e}")
            return CitationType.UNKNOWN, None
    
    def _parse_response(self, response_text: str, original: str) -> Tuple[CitationType, Optional[CitationMetadata]]:
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return CitationType.UNKNOWN, None
            
            data = json.loads(json_match.group())
            
            type_map = {
                'journal': CitationType.JOURNAL, 'book': CitationType.BOOK,
                'legal': CitationType.LEGAL, 'interview': CitationType.INTERVIEW,
                'newspaper': CitationType.NEWSPAPER, 'government': CitationType.GOVERNMENT,
                'medical': CitationType.MEDICAL, 'url': CitationType.URL,
            }
            
            citation_type = type_map.get(data.get('type', '').lower(), CitationType.UNKNOWN)
            
            if citation_type == CitationType.UNKNOWN:
                return citation_type, None
            
            metadata = CitationMetadata(
                citation_type=citation_type,
                raw_source=original,
                source_engine="Gemini Router",
                title=data.get('title', ''),
                authors=data.get('authors', []),
                year=data.get('year'),
                confidence=data.get('confidence', 0.5),
            )
            
            return citation_type, metadata
            
        except:
            return CitationType.UNKNOWN, None


def classify_with_gemini(text: str) -> Tuple[CitationType, Optional[CitationMetadata]]:
    return GeminiRouter().classify(text)
