import csv
import os
from functools import lru_cache
from datetime import datetime
from app import db

# CoverService is imported lazily inside methods to avoid any circular-import
# risk during Flask app initialisation.

class Author(db.Model):
    __tablename__ = 'authors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    bio = db.Column(db.Text)

    books = db.relationship('Book', backref='author', lazy='dynamic')


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

    books = db.relationship('Book', backref='category', lazy='dynamic')
    digital_resources = db.relationship('DigitalResource', backref='category', lazy='dynamic')


class Publisher(db.Model):
    __tablename__ = 'publishers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)

    books = db.relationship('Book', backref='publisher', lazy='dynamic')


class BookLocation(db.Model):
    __tablename__ = 'book_locations'

    id = db.Column(db.Integer, primary_key=True)
    block = db.Column(db.String(50), nullable=False)
    floor = db.Column(db.String(20), nullable=False)
    section = db.Column(db.String(50), nullable=False)
    rack = db.Column(db.String(20), nullable=False)
    shelf = db.Column(db.String(20), nullable=False)
    position = db.Column(db.String(20), nullable=False)

    books = db.relationship('Book', backref='location', lazy='dynamic')
    copies = db.relationship('BookCopy', backref='location', lazy='dynamic')

    @property
    def display_name(self):
        return f"{self.block} - Floor {self.floor}, Sec {self.section}, Rack {self.rack}, Shelf {self.shelf}, Pos {self.position}"


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('authors.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    publisher_id = db.Column(db.Integer, db.ForeignKey('publishers.id'), nullable=False)
    pub_year = db.Column(db.Integer, nullable=False)
    edition = db.Column(db.String(50), nullable=True)
    subject = db.Column(db.String(100), nullable=True)
    access_no = db.Column(db.String(50), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    language = db.Column(db.String(50), default='English')
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(255), default='default_cover.jpg')
    location_id = db.Column(db.Integer, db.ForeignKey('book_locations.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department = db.relationship('Department', backref='books')

    # Relationships
    copies = db.relationship('BookCopy', backref='book', lazy='dynamic', cascade='all, delete-orphan')
    requests = db.relationship('BookRequest', backref='book', lazy='dynamic')
    reservations = db.relationship('Reservation', backref='book', lazy='dynamic')
    waiting_lists = db.relationship('WaitingList', backref='book', lazy='dynamic')
    wishlists = db.relationship('Wishlist', backref='book', lazy='dynamic')
    reviews = db.relationship('RatingReview', backref='book', lazy='dynamic')

    @property
    def total_copies_count(self):
        return self.copies.count()

    @property
    def available_copies_count(self):
        return self.copies.filter_by(status='AVAILABLE').count()

    @property
    def issued_copies_count(self):
        return self.copies.filter_by(status='ISSUED').count()

    @property
    def reserved_copies_count(self):
        return self.copies.filter_by(status='RESERVED').count()

    @property
    def damaged_copies_count(self):
        return self.copies.filter_by(status='DAMAGED').count()

    @property
    def lost_copies_count(self):
        return self.copies.filter_by(status='LOST').count()

    @property
    def average_rating(self):
        revs = self.reviews.all()
        if not revs:
            return 0.0
        return round(sum(r.rating for r in revs) / len(revs), 1)

    @property
    def rating_count(self):
        return self.reviews.count()

    @property
    def cover_path(self):
        """
        Return the relative static/ path for this book's cover image.

        Delegates to CoverService which:
          1. Checks book_covers/<ISBN>.<ext> (exact ISBN filename match)
          2. Falls back to 'default_cover.jpg' (KIOT placeholder)

        Never returns None — the fallback ensures no broken-image icons.
        Legacy uploads in uploads/covers/ are also checked as a tertiary path.
        """
        from app.services.cover_service import resolve_cover_path, normalise_isbn

        # 1. Primary: ISBN-matched local file via CoverService
        clean_isbn = normalise_isbn(self.isbn or '')
        primary = resolve_cover_path(clean_isbn)
        if primary != 'default_cover.jpg':
            return primary

        # 2. Secondary: legacy uploads/covers/ path stored in cover_image column
        if self.cover_image and self.cover_image not in ('default_cover.jpg', '', None):
            static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')
            legacy_path = os.path.join(static_dir, *self.cover_image.replace('/', os.sep).split(os.sep))
            if os.path.isfile(legacy_path):
                return self.cover_image

        # 3. Fallback: KIOT placeholder
        return 'default_cover.jpg'

    @property
    def cover_url(self):
        """
        Return a verified remote URL from the manifest CSV, or None.
        Only returns URLs for rows with Status == 'VERIFIED' or 'VERIFIED_EXACT_ISBN'.
        Never returns a URL from a row with a scientific-notation ISBN in the manifest.
        """
        from app.services.cover_service import normalise_isbn, load_manifest
        clean_isbn = normalise_isbn(self.isbn or '')
        if not clean_isbn:
            return None
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '..', 'Datas', 'book_covers_manifest.csv'
        )
        manifest = load_manifest(os.path.abspath(manifest_path))
        row = manifest.get(clean_isbn)
        if not row:
            return None
        # Reject if the manifest had a conflicted (sci-notation) ISBN
        if row.get('_isbn_conflict'):
            return None
        status = row.get('Status', '')
        if status in ('VERIFIED', 'VERIFIED_EXACT_ISBN') and row.get('Cover URL'):
            return row['Cover URL']
        return None


# Keep the legacy helper for backwards-compatibility with any existing callers.
@lru_cache(maxsize=1)
def _cover_manifest(manifest_path):
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, newline='', encoding='utf-8-sig') as manifest_file:
        return {row.get('ISBN', ''): row for row in csv.DictReader(manifest_file)}


def verified_cover_url(manifest_path, isbn):
    row = _cover_manifest(os.path.abspath(manifest_path)).get(isbn)
    if row and row.get('Status') in ('VERIFIED', 'VERIFIED_EXACT_ISBN') and row.get('Cover URL'):
        return row['Cover URL']
    return None


class BookCopy(db.Model):
    __tablename__ = 'book_copies'

    id = db.Column(db.Integer, primary_key=True)
    copy_code = db.Column(db.String(50), unique=True, nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    acquisition_date = db.Column(db.Date, default=datetime.utcnow().date)
    condition_status = db.Column(db.String(20), default='EXCELLENT') # EXCELLENT, GOOD, FAIR, DAMAGED
    status = db.Column(db.String(20), default='AVAILABLE') # AVAILABLE, ISSUED, RESERVED, LOST, DAMAGED, ARCHIVED
    location_id = db.Column(db.Integer, db.ForeignKey('book_locations.id'), nullable=True)

    borrow_transactions = db.relationship('BorrowTransaction', backref='copy', lazy='dynamic')
