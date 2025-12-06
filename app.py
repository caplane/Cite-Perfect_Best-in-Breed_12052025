"""
citeflex/app.py

Flask application for CiteFlex Unified.

Version History:
    2025-12-06 13:30: Added debug logging to diagnose session loss issue
    2025-12-06 13:00: CRITICAL FIX - Fixed /api/update and /api/download to properly
                      access session data. Override feature now works correctly.
    2025-12-06 12:45: Added file-based session persistence to survive deployments
                      Sessions saved to /data/sessions (Railway Volume mount point)
    2025-12-05 12:53: Thread-safe session management with threading.Lock()
    2025-12-05 13:35: Updated to use unified_router, added /api/update endpoint
                      Enhanced /api/cite to return type and source info
                      Enhanced /api/process to return notes list for workbench UI

FIXES APPLIED:
1. Thread-safe session management with threading.Lock()
2. Session expiration (4 hours) to prevent memory leaks
3. Periodic cleanup of expired sessions
4. File-based persistence for sessions (survives deployments with Railway Volume)
5. CRITICAL: /api/update now properly updates document (was silently failing)
6. CRITICAL: /api/download now returns updated document (was returning original)
7. DEBUG: Added logging to track session creation and lookup
"""

import os
import uuid
import time
import threading
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename

from unified_router import get_citation, get_multiple_citations
from document_processor import process_document

# =============================================================================
# APP CONFIGURATION
# =============================================================================

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')

ALLOWED_EXTENSIONS = {'docx'}

# =============================================================================
# FIX: PERSISTENT SESSION MANAGEMENT
# =============================================================================

# Session storage directory - use Railway Volume mount point for persistence
SESSIONS_DIR = Path(os.environ.get('SESSIONS_DIR', '/data/sessions'))

class SessionManager:
    """
    Thread-safe session manager with file-based persistence.
    
    Features:
    1. Thread-safe with threading.Lock()
    2. Sessions expire after 4 hours
    3. Persists to disk - survives server restarts/deployments
    4. Requires Railway Volume mounted at /data for full persistence
    
    Setup for Railway:
    1. Go to your service in Railway
    2. Add a Volume: Settings → Volumes → Add Volume
    3. Mount path: /data
    4. Sessions will now survive deployments
    """
    
    SESSION_EXPIRY_HOURS = 4
    CLEANUP_INTERVAL_MINUTES = 15
    
    def __init__(self, storage_dir: Path = SESSIONS_DIR):
        self._sessions = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._storage_dir = storage_dir
        self._persistence_available = False
        
        # Try to set up persistent storage
        self._init_storage()
        
        # Load existing sessions from disk
        self._load_sessions()
    
    def _init_storage(self):
        """Initialize storage directory if possible."""
        try:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = self._storage_dir / '.test'
            test_file.write_text('test')
            test_file.unlink()
            self._persistence_available = True
            print(f"[SessionManager] Persistent storage enabled at {self._storage_dir}")
        except Exception as e:
            self._persistence_available = False
            print(f"[SessionManager] Persistent storage unavailable ({e}). Using in-memory only.")
            print("[SessionManager] To enable persistence, add a Railway Volume mounted at /data")
    
    def _get_session_file(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self._storage_dir / f"{session_id}.pkl"
    
    def _save_session(self, session_id: str):
        """Save a single session to disk."""
        if not self._persistence_available:
            return
        try:
            session = self._sessions.get(session_id)
            if session:
                with open(self._get_session_file(session_id), 'wb') as f:
                    pickle.dump(session, f)
        except Exception as e:
            print(f"[SessionManager] Failed to save session {session_id[:8]}: {e}")
    
    def _delete_session_file(self, session_id: str):
        """Delete session file from disk."""
        if not self._persistence_available:
            return
        try:
            session_file = self._get_session_file(session_id)
            if session_file.exists():
                session_file.unlink()
        except Exception as e:
            print(f"[SessionManager] Failed to delete session file {session_id[:8]}: {e}")
    
    def _load_sessions(self):
        """Load all sessions from disk on startup."""
        if not self._persistence_available:
            return
        
        loaded = 0
        expired = 0
        current_time = datetime.now()
        
        try:
            for session_file in self._storage_dir.glob("*.pkl"):
                try:
                    with open(session_file, 'rb') as f:
                        session = pickle.load(f)
                    
                    # Check if expired
                    if current_time > session.get('expires_at', current_time):
                        session_file.unlink()
                        expired += 1
                        continue
                    
                    session_id = session_file.stem
                    self._sessions[session_id] = session
                    loaded += 1
                except Exception as e:
                    print(f"[SessionManager] Failed to load {session_file.name}: {e}")
                    # Remove corrupted file
                    try:
                        session_file.unlink()
                    except:
                        pass
            
            if loaded > 0 or expired > 0:
                print(f"[SessionManager] Loaded {loaded} sessions, cleaned {expired} expired")
        except Exception as e:
            print(f"[SessionManager] Failed to load sessions: {e}")
    
    def create(self) -> str:
        """Create a new session with expiration."""
        session_id = str(uuid.uuid4())
        
        with self._lock:
            self._sessions[session_id] = {
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(hours=self.SESSION_EXPIRY_HOURS),
                'data': {}
            }
            self._save_session(session_id)
            self._maybe_cleanup()
        
        return session_id
    
    def get(self, session_id: str) -> dict:
        """Get session data (thread-safe)."""
        with self._lock:
            session = self._sessions.get(session_id)
            
            if not session:
                return None
            
            # Check expiration
            if datetime.now() > session['expires_at']:
                del self._sessions[session_id]
                self._delete_session_file(session_id)
                return None
            
            return session['data']
    
    def set(self, session_id: str, key: str, value) -> bool:
        """Set session data (thread-safe)."""
        with self._lock:
            session = self._sessions.get(session_id)
            
            if not session:
                return False
            
            if datetime.now() > session['expires_at']:
                del self._sessions[session_id]
                self._delete_session_file(session_id)
                return False
            
            session['data'][key] = value
            self._save_session(session_id)
            return True
    
    def delete(self, session_id: str) -> bool:
        """Delete a session (thread-safe)."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._delete_session_file(session_id)
                return True
            return False
    
    def _maybe_cleanup(self) -> None:
        """
        Clean up expired sessions periodically.
        Called within lock, so no additional locking needed.
        """
        now = time.time()
        if now - self._last_cleanup < self.CLEANUP_INTERVAL_MINUTES * 60:
            return
        
        self._last_cleanup = now
        current_time = datetime.now()
        
        expired = [
            sid for sid, session in self._sessions.items()
            if current_time > session['expires_at']
        ]
        
        for sid in expired:
            del self._sessions[sid]
            self._delete_session_file(sid)
        
        if expired:
            print(f"[SessionManager] Cleaned up {len(expired)} expired sessions")


# Global session manager instance
sessions = SessionManager()


# =============================================================================
# HELPERS
# =============================================================================

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/api/cite', methods=['POST'])
def cite():
    """
    Single citation lookup API.
    
    Request JSON:
    {
        "query": "citation text or URL",
        "style": "Chicago Manual of Style"  // optional
    }
    
    Response JSON:
    {
        "success": true,
        "citation": "formatted citation",
        "metadata": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('query'):
            return jsonify({
                'success': False,
                'error': 'Missing query parameter'
            }), 400
        
        query = data['query'].strip()
        style = data.get('style', 'Chicago Manual of Style')
        
        metadata, formatted = get_citation(query, style)
        
        if not formatted:
            return jsonify({
                'success': False,
                'error': 'Could not find citation information',
                'query': query
            }), 404
        
        # Determine type and source for UI badges
        citation_type = 'unknown'
        source = 'unified'
        confidence = 'medium'
        
        if metadata:
            citation_type = metadata.citation_type.name.lower() if metadata.citation_type else 'unknown'
            # Determine source based on type and metadata
            if citation_type == 'legal':
                source = 'cache' if metadata.citation else 'courtlistener'
                confidence = 'high' if metadata.citation else 'medium'
            elif citation_type in ['journal', 'medical']:
                source = 'crossref/openalex'
                confidence = 'high' if metadata.doi else 'medium'
            elif citation_type == 'book':
                source = 'openlibrary/googlebooks'
                confidence = 'high' if metadata.isbn else 'medium'
            else:
                source = 'unified'
        
        return jsonify({
            'success': True,
            'citation': formatted,
            'type': citation_type,
            'source': source,
            'confidence': confidence,
            'metadata': metadata.to_dict() if metadata else None
        })
        
    except Exception as e:
        print(f"[API] Error in /api/cite: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/cite/multiple', methods=['POST'])
def cite_multiple():
    """
    Multiple citation options API.
    
    Request JSON:
    {
        "query": "search text",
        "style": "Chicago Manual of Style",
        "limit": 5
    }
    
    Response JSON:
    {
        "success": true,
        "results": [
            {"citation": "...", "metadata": {...}},
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('query'):
            return jsonify({
                'success': False,
                'error': 'Missing query parameter'
            }), 400
        
        query = data['query'].strip()
        style = data.get('style', 'Chicago Manual of Style')
        limit = min(data.get('limit', 5), 10)  # Cap at 10
        
        results = get_multiple_citations(query, style, limit)
        
        return jsonify({
            'success': True,
            'results': [
                {
                    'citation': formatted,
                    'source': source,
                    'type': meta.citation_type.name.lower() if meta and meta.citation_type else 'unknown',
                    'confidence': 'high' if (meta and (meta.doi or meta.citation)) else 'medium',
                    'metadata': meta.to_dict() if meta else None
                }
                for meta, formatted, source in results
            ]
        })
        
    except Exception as e:
        print(f"[API] Error in /api/cite/multiple: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/process', methods=['POST'])
def process_doc():
    """
    Document processing API.
    
    Expects multipart form with:
    - file: .docx document
    - style: citation style (optional)
    - add_links: whether to make URLs clickable (optional)
    
    Returns processed document as download.
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Only .docx files are supported'
            }), 400
        
        style = request.form.get('style', 'Chicago Manual of Style')
        add_links = request.form.get('add_links', 'true').lower() == 'true'
        
        # Read file bytes
        file_bytes = file.read()
        
        # Process document
        processed_bytes, results = process_document(
            file_bytes,
            style=style,
            add_links=add_links
        )
        
        # Create session to store results
        session_id = sessions.create()
        print(f"[API] Created session {session_id[:8]}... for document {file.filename}")
        
        sessions.set(session_id, 'processed_doc', processed_bytes)
        sessions.set(session_id, 'original_bytes', file_bytes)  # Store original for re-processing
        sessions.set(session_id, 'style', style)
        sessions.set(session_id, 'results', [
            {
                'id': idx + 1,
                'original': r.original,
                'formatted': r.formatted,
                'success': r.success,
                'error': r.error,
                'form': r.citation_form,
                'type': r.citation_type.name.lower() if hasattr(r, 'citation_type') and r.citation_type else 'unknown'
            }
            for idx, r in enumerate(results)
        ])
        sessions.set(session_id, 'filename', secure_filename(file.filename))
        
        print(f"[API] Session {session_id[:8]} initialized with {len(results)} notes, doc size={len(processed_bytes)}")
        print(f"[API] Total active sessions: {len(sessions._sessions)}")
        
        # Build notes list for UI
        notes = []
        for idx, r in enumerate(results):
            note_type = 'unknown'
            if hasattr(r, 'citation_type') and r.citation_type:
                note_type = r.citation_type.name.lower()
            
            notes.append({
                'id': idx + 1,
                'text': r.original,
                'formatted': r.formatted if r.success else r.original,
                'type': note_type,
                'success': r.success,
                'form': r.citation_form
            })
        
        # Return summary with notes for workbench UI
        success_count = sum(1 for r in results if r.success)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'notes': notes,  # For workbench UI
            'stats': {
                'total': len(results),
                'success': success_count,
                'failed': len(results) - success_count,
                'ibid': sum(1 for r in results if r.citation_form == 'ibid'),
                'short': sum(1 for r in results if r.citation_form == 'short'),
                'full': sum(1 for r in results if r.citation_form == 'full'),
            }
        })
        
    except Exception as e:
        print(f"[API] Error in /api/process: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/download/<session_id>')
def download(session_id: str):
    """Download processed document."""
    try:
        # Get session data using proper method
        session_data = sessions.get(session_id)
        
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'Session not found or expired'
            }), 404
        
        processed_doc = session_data.get('processed_doc')
        filename = session_data.get('filename', 'processed.docx')
        
        if not processed_doc:
            return jsonify({
                'success': False,
                'error': 'Processed document not found'
            }), 404
        
        from io import BytesIO
        buffer = BytesIO(processed_doc)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=f"citeflex_{filename}" if filename else "citeflex_processed.docx"
        )
        
    except Exception as e:
        print(f"[API] Error in /api/download: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/results/<session_id>')
def get_results(session_id: str):
    """Get processing results for a session."""
    try:
        session_data = sessions.get(session_id)
        
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'Session not found or expired'
            }), 404
        
        results = session_data.get('results')
        
        if results is None:
            return jsonify({
                'success': False,
                'error': 'Results not found'
            }), 404
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/update', methods=['POST'])
def update_note():
    """
    Update a specific note in the processed document.
    
    Request JSON:
    {
        "session_id": "uuid",
        "note_id": 1,
        "html": "formatted citation text"
    }
    
    This re-processes the document with the updated note.
    Updated: 2025-12-06 13:00 - Fixed to properly update document and report failures
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request data'
            }), 400
        
        session_id = data.get('session_id')
        note_id = data.get('note_id')
        new_html = data.get('html', '')
        
        if not session_id or not note_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id or note_id'
            }), 400
        
        # Debug: Log available sessions
        print(f"[API] /api/update called for session={session_id[:8]}..., note={note_id}")
        print(f"[API] Active sessions: {list(sessions._sessions.keys())[:5]}")  # First 5
        
        # Get session data using proper thread-safe method
        session_data = sessions.get(session_id)
        if not session_data:
            print(f"[API] Session {session_id[:8]} NOT FOUND in {len(sessions._sessions)} sessions")
            return jsonify({
                'success': False,
                'error': 'Session not found or expired'
            }), 404
        
        results = session_data.get('results', [])
        processed_doc = session_data.get('processed_doc')
        
        if not results or not processed_doc:
            print(f"[API] Session {session_id[:8]} has incomplete data: results={bool(results)}, doc={bool(processed_doc)}")
            return jsonify({
                'success': False,
                'error': 'Session data incomplete'
            }), 404
        
        # Update the specific result
        note_idx = note_id - 1  # Convert 1-based to 0-based
        if note_idx < 0 or note_idx >= len(results):
            return jsonify({
                'success': False,
                'error': f'Note {note_id} not found'
            }), 404
        
        # Update the document - this is the critical part
        from document_processor import update_document_note
        try:
            updated_doc = update_document_note(processed_doc, note_id, new_html)
            
            # Verify the update actually changed something
            if updated_doc == processed_doc:
                print(f"[API] Warning: update_document_note returned unchanged document for note {note_id}")
            
            # Save updated document to session
            sessions.set(session_id, 'processed_doc', updated_doc)
            
        except Exception as update_err:
            print(f"[API] Document update failed for note {note_id}: {update_err}")
            return jsonify({
                'success': False,
                'error': f'Failed to update document: {str(update_err)}'
            }), 500
        
        # Update results array
        results[note_idx]['formatted'] = new_html
        results[note_idx]['success'] = True
        sessions.set(session_id, 'results', results)
        
        print(f"[API] Successfully updated note {note_id}")
        
        return jsonify({
            'success': True,
            'note_id': note_id,
            'formatted': new_html
        })
        
    except Exception as e:
        print(f"[API] Error in /api/update: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'version': '2.0.1',
        'sessions_count': len(sessions._sessions),
        'persistence': sessions._persistence_available
    })


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
