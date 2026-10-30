"""
CoverService — Centralized book cover resolution, validation, upload, and fallback.

Design decisions:
- No direct import of the Book model at module level to avoid circular imports.
  Use string-based lookups or accept isbn/book_id as parameters.
- All image I/O is validated with Pillow before acceptance.
- Filenames are sanitised via werkzeug.utils.secure_filename.
- Unmatched images go to book_covers/unmatched/ and are never auto-assigned.
- Fallback is always the static default_cover.jpg — never a broken link.
"""

import csv
import io
import os
import re
import shutil
import zipfile
from datetime import datetime

from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
_SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
_MIN_IMAGE_BYTES = 1000          # Reject anything smaller (placeholder/error page)
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB upper limit


def _static_dir():
    """Return the absolute path to app/static regardless of cwd."""
    here = os.path.dirname(os.path.abspath(__file__))          # app/services/
    return os.path.join(here, '..', 'static')


def _covers_dir():
    return os.path.join(_static_dir(), 'book_covers')


def _unmatched_dir():
    return os.path.join(_covers_dir(), 'unmatched')


def _default_cover_rel():
    """Relative path (from static/) used in url_for('static', filename=...)."""
    return 'default_cover.jpg'


# ---------------------------------------------------------------------------
# ISBN normalisation — safe string-only, never float
# ---------------------------------------------------------------------------
def normalise_isbn(raw) -> str:
    """
    Convert any raw ISBN value to a clean digit/X string.
    Handles:
      - Scientific notation  (9.78e12 -> '9780070087705' ish — best-effort)
      - Trailing '.0' from pandas float read
      - Leading zeros are preserved
      - Non-numeric garbage is stripped
    Never returns a float or integer.
    """
    if raw is None:
        return ''
    s = str(raw).strip()
    if not s or s.lower() in ('none', 'nan', 'null', ''):
        return ''
    # Scientific notation check
    if re.search(r'[eE][+\-]?\d', s):
        try:
            s = f"{int(float(s))}"
        except (ValueError, OverflowError):
            pass
    # Strip trailing .0 from float-ish strings
    if s.endswith('.0'):
        s = s[:-2]
    # Keep only digits and X/x
    clean = re.sub(r'[^0-9Xx]', '', s).upper()
    return clean


# ---------------------------------------------------------------------------
# Image validation (no side-effects)
# ---------------------------------------------------------------------------
def validate_image_bytes(data: bytes, filename: str = '') -> tuple[bool, str]:
    """
    Validate raw image bytes.
    Returns (is_valid, reason_string).
    """
    if len(data) < _MIN_IMAGE_BYTES:
        return False, f"File too small ({len(data)} bytes); likely an error page or placeholder."
    if len(data) > _MAX_IMAGE_BYTES:
        return False, f"File too large ({len(data)} bytes); max is {_MAX_IMAGE_BYTES // 1024 // 1024} MB."
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        img.verify()
        return True, "OK"
    except ImportError:
        # Pillow not installed — do a basic header check
        if data[:3] == b'\xff\xd8\xff':
            return True, "OK (JPEG header, no PIL)"
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return True, "OK (PNG header, no PIL)"
        if data[:4] in (b'RIFF', b'WEBP'):
            return True, "OK (WEBP header, no PIL)"
        return False, "Unrecognised image format and Pillow not available."
    except Exception as exc:
        return False, f"Image validation failed: {exc}"


# ---------------------------------------------------------------------------
# Cover-path resolution (no DB access — pure filesystem)
# ---------------------------------------------------------------------------
def resolve_cover_path(isbn: str) -> str:
    """
    Return the relative static/ path for a book's cover image.

    Priority:
      1. app/static/book_covers/<ISBN>.jpg   (exact ISBN match — any supported ext)
      2. 'default_cover.jpg'                 (safe KIOT placeholder)

    Never returns a path that does not exist on disk.
    Never returns a path for an unmatched image.
    """
    clean_isbn = normalise_isbn(isbn)
    if clean_isbn:
        covers = _covers_dir()
        for ext in ('.jpg', '.jpeg', '.png', '.webp'):
            candidate = os.path.join(covers, f"{clean_isbn}{ext}")
            if os.path.isfile(candidate):
                return f"book_covers/{clean_isbn}{ext}"
    return _default_cover_rel()


def has_local_cover(isbn: str) -> bool:
    return resolve_cover_path(isbn) != _default_cover_rel()


# ---------------------------------------------------------------------------
# Single-cover save (used by upload/replace routes)
# ---------------------------------------------------------------------------
def save_cover_for_isbn(isbn: str, file_storage) -> tuple[bool, str, str]:
    """
    Validate and save an uploaded cover image for a given ISBN.

    Returns (success, message, relative_path_or_empty).
    The relative path is from static/, e.g. 'book_covers/9780070087705.jpg'.
    """
    clean_isbn = normalise_isbn(isbn)
    if not clean_isbn:
        return False, "Invalid or empty ISBN.", ''

    if file_storage is None or not file_storage.filename:
        return False, "No file provided.", ''

    orig_name = secure_filename(file_storage.filename)
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Accepted: jpg, jpeg, png, webp.", ''

    data = file_storage.read()
    ok, reason = validate_image_bytes(data, orig_name)
    if not ok:
        return False, f"Image rejected: {reason}", ''

    # Ensure directory exists
    covers = _covers_dir()
    os.makedirs(covers, exist_ok=True)

    # Remove any old cover for this ISBN (all extensions)
    for old_ext in _SUPPORTED_EXTENSIONS:
        old_path = os.path.join(covers, f"{clean_isbn}{old_ext}")
        if os.path.isfile(old_path):
            os.remove(old_path)

    dest = os.path.join(covers, f"{clean_isbn}{ext}")
    with open(dest, 'wb') as f:
        f.write(data)

    rel_path = f"book_covers/{clean_isbn}{ext}"
    return True, f"Cover saved successfully for ISBN {clean_isbn}.", rel_path


# ---------------------------------------------------------------------------
# Single-cover delete
# ---------------------------------------------------------------------------
def delete_cover_for_isbn(isbn: str) -> tuple[bool, str]:
    """Remove cover image(s) for the given ISBN. Returns (success, message)."""
    clean_isbn = normalise_isbn(isbn)
    if not clean_isbn:
        return False, "Invalid ISBN."

    removed = []
    covers = _covers_dir()
    for ext in _SUPPORTED_EXTENSIONS:
        path = os.path.join(covers, f"{clean_isbn}{ext}")
        if os.path.isfile(path):
            os.remove(path)
            removed.append(os.path.basename(path))

    if removed:
        return True, f"Removed: {', '.join(removed)}"
    return False, f"No local cover found for ISBN {clean_isbn}."


# ---------------------------------------------------------------------------
# Manifest reader (reads book_covers_manifest.csv as supporting info only)
# ---------------------------------------------------------------------------
def load_manifest(manifest_path: str) -> dict:
    """
    Load book_covers_manifest.csv into {clean_isbn: row_dict}.
    
    The manifest is SUPPORTING information only — it never overrides
    Books_Final.xlsx ISBNs. Scientific-notation ISBNs in the manifest
    are normalised but flagged as CONFLICT in the returned dict.
    """
    result = {}
    if not os.path.isfile(manifest_path):
        return result
    try:
        with open(manifest_path, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                raw_isbn = row.get('ISBN') or row.get('\ufeffISBN') or ''
                clean = normalise_isbn(raw_isbn)
                if not clean:
                    continue
                # Flag if raw value looked like scientific notation
                if re.search(r'[eE][+\-]?\d', str(raw_isbn)):
                    row['_isbn_conflict'] = f"Scientific notation in manifest: {raw_isbn!r}"
                else:
                    row['_isbn_conflict'] = ''
                result[clean] = row
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# ZIP bulk-upload processor
# ---------------------------------------------------------------------------
def process_cover_zip(zip_data: bytes, catalog_isbns: set) -> dict:
    """
    Extract a cover ZIP and match images to catalog ISBNs.

    Rules:
    - ISBN-named files are matched by exact string comparison (normalised).
    - Non-ISBN filenames are moved to unmatched/ for manual review.
    - Files already in unmatched/ are never forced onto books.
    - Existing covers are NOT overwritten unless the new image is validated.

    Parameters:
        zip_data      — raw bytes of the uploaded ZIP file
        catalog_isbns — set of clean ISBN strings from the authoritative catalog

    Returns a dict with keys:
        matched, unmatched, invalid, duplicate, errors,
        books_still_missing, report_rows
    """
    covers_dir = _covers_dir()
    unmatched_dir = _unmatched_dir()
    os.makedirs(covers_dir, exist_ok=True)
    os.makedirs(unmatched_dir, exist_ok=True)

    matched = []
    unmatched = []
    invalid = []
    duplicate = []
    errors = []

    already_covered = {normalise_isbn(os.path.splitext(f)[0])
                       for f in os.listdir(covers_dir)
                       if os.path.splitext(f)[1].lower() in _SUPPORTED_EXTENSIONS
                       and f != 'unmatched'}

    try:
        with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zf:
            for member in zf.namelist():
                # Skip directories and macOS metadata
                if member.endswith('/') or os.path.basename(member).startswith('._'):
                    continue
                basename = os.path.basename(member)
                ext = os.path.splitext(basename)[1].lower()
                if ext not in _SUPPORTED_EXTENSIONS:
                    continue

                # Read image bytes
                try:
                    data = zf.read(member)
                except Exception as e:
                    errors.append({'file': basename, 'reason': str(e)})
                    continue

                ok, reason = validate_image_bytes(data, basename)
                if not ok:
                    invalid.append({'file': basename, 'reason': reason})
                    continue

                # Try to extract ISBN from filename
                stem = os.path.splitext(basename)[0]
                candidate_isbn = normalise_isbn(stem)

                if candidate_isbn and candidate_isbn in catalog_isbns:
                    # Exact ISBN match
                    if candidate_isbn in already_covered:
                        duplicate.append({
                            'file': basename,
                            'isbn': candidate_isbn,
                            'reason': 'Cover already exists; not overwritten.'
                        })
                        continue
                    dest = os.path.join(covers_dir, f"{candidate_isbn}{ext}")
                    with open(dest, 'wb') as f:
                        f.write(data)
                    already_covered.add(candidate_isbn)
                    matched.append({'file': basename, 'isbn': candidate_isbn})
                else:
                    # Unmatched — preserve for manual review
                    safe_name = secure_filename(basename)
                    dest = os.path.join(unmatched_dir, safe_name)
                    # Avoid overwriting existing unmatched file
                    if os.path.exists(dest):
                        base, e = os.path.splitext(safe_name)
                        safe_name = f"{base}_{datetime.now().strftime('%H%M%S')}{e}"
                        dest = os.path.join(unmatched_dir, safe_name)
                    with open(dest, 'wb') as f:
                        f.write(data)
                    reason = (f"Filename ISBN '{candidate_isbn}' not in catalog"
                              if candidate_isbn else "Filename is not a recognisable ISBN")
                    unmatched.append({'file': basename, 'saved_as': safe_name, 'reason': reason})

    except zipfile.BadZipFile as e:
        errors.append({'file': 'ZIP', 'reason': f"Invalid ZIP file: {e}"})

    books_still_missing = sorted(catalog_isbns - already_covered)

    return {
        'matched': matched,
        'unmatched': unmatched,
        'invalid': invalid,
        'duplicate': duplicate,
        'errors': errors,
        'books_still_missing': books_still_missing,
    }


# ---------------------------------------------------------------------------
# Catalog-wide reconciliation report (no DB dependency)
# ---------------------------------------------------------------------------
def generate_cover_reconciliation(catalog_isbns: set) -> dict:
    """
    Scan book_covers/ and return counts for a reconciliation report.
    Does not touch the database.
    """
    covers_dir = _covers_dir()
    unmatched_dir = _unmatched_dir()
    os.makedirs(covers_dir, exist_ok=True)

    cover_files = [
        f for f in os.listdir(covers_dir)
        if os.path.isfile(os.path.join(covers_dir, f))
        and os.path.splitext(f)[1].lower() in _SUPPORTED_EXTENSIONS
    ]

    matched_isbns = set()
    unmatched_files = []
    for f in cover_files:
        stem = os.path.splitext(f)[0]
        isbn = normalise_isbn(stem)
        if isbn in catalog_isbns:
            matched_isbns.add(isbn)
        else:
            unmatched_files.append(f)

    unmatched_preserved = []
    if os.path.isdir(unmatched_dir):
        unmatched_preserved = [
            f for f in os.listdir(unmatched_dir)
            if os.path.isfile(os.path.join(unmatched_dir, f))
        ]

    missing = sorted(catalog_isbns - matched_isbns)

    return {
        'total_catalog_isbns': len(catalog_isbns),
        'total_cover_files': len(cover_files),
        'verified_isbn_matches': len(matched_isbns),
        'unmatched_in_covers_dir': unmatched_files,
        'unmatched_preserved_count': len(unmatched_preserved),
        'missing_covers': missing,
        'missing_count': len(missing),
    }
