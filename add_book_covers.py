import os
import re
import io
import json
import urllib.parse
from urllib import request, error

from PIL import Image, ImageDraw, ImageFont

from app import create_app, db
from app.models.book import Book
from app.services.cover_service import normalise_isbn, _covers_dir, validate_image_bytes

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT, 'app', 'static')
COVERS_DIR = os.path.join(STATIC_DIR, 'book_covers')
DEFAULT_COVER = os.path.join(STATIC_DIR, 'default_cover.jpg')


def ensure_default_cover():
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(COVERS_DIR, exist_ok=True)

    if os.path.exists(DEFAULT_COVER):
        return

    width, height = 600, 900
    img = Image.new('RGB', (width, height), color=(15, 23, 42))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, fill=(30, 58, 138), outline=(59, 130, 246), width=3)
    d.text((width // 2, height // 2 - 40), 'KIOT CENTRAL', fill=(255, 255, 255), anchor='mm', font=ImageFont.load_default())
    d.text((width // 2, height // 2 + 10), 'LIBRARY', fill=(245, 158, 11), anchor='mm', font=ImageFont.load_default())
    d.text((width // 2, height - 120), 'SMART BOOK CATALOG', fill=(200, 220, 255), anchor='mm', font=ImageFont.load_default())
    img.save(DEFAULT_COVER, 'JPEG', quality=90)


def fetch_openlibrary_isbn(isbn):
    if not isbn:
        return None
    try:
        url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
        req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            ok, _ = validate_image_bytes(data)
            if ok and len(data) > 2000:
                return data
    except Exception:
        pass
    return None


def fetch_google_books(query):
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(query)}"
        req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get('items', [])
            for item in items[:3]:
                image_links = item.get('volumeInfo', {}).get('imageLinks', {})
                img_url = (image_links.get('extraLarge') or 
                           image_links.get('large') or 
                           image_links.get('medium') or 
                           image_links.get('small') or 
                           image_links.get('thumbnail'))
                if img_url:
                    img_url = img_url.replace('http://', 'https://').replace('&edge=curl', '')
                    img_req = request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with request.urlopen(img_req, timeout=10) as img_resp:
                        img_bytes = img_resp.read()
                        ok, _ = validate_image_bytes(img_bytes)
                        if ok:
                            return img_bytes
    except Exception:
        pass
    return None


def generate_styled_cover(title, author, category="Technical", isbn=""):
    width, height = 600, 900
    palettes = [
        ((15, 23, 42), (30, 58, 138), (59, 130, 246)),
        ((24, 24, 27), (88, 28, 135), (168, 85, 247)),
        ((15, 23, 42), (15, 118, 110), (20, 184, 166)),
        ((28, 25, 23), (124, 45, 18), (249, 115, 22)),
        ((17, 24, 39), (31, 41, 55), (99, 102, 241)),
    ]
    c_dark, c_mid, c_accent = palettes[hash(title) % len(palettes)]
    
    img = Image.new('RGB', (width, height), color=c_dark)
    draw = ImageDraw.Draw(img)
    
    for y in range(height):
        ratio = y / height
        r = int(c_dark[0] * (1 - ratio) + c_mid[0] * ratio)
        g = int(c_dark[1] * (1 - ratio) + c_mid[1] * ratio)
        b = int(c_dark[2] * (1 - ratio) + c_mid[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    draw.ellipse((-100, -100, 350, 350), outline=(*c_accent, 40), width=4)
    draw.rectangle((40, 40, width - 40, height - 40), outline=c_accent, width=3)
    draw.rectangle((50, 50, width - 50, height - 50), outline=(255, 255, 255, 30), width=1)
    
    tag_text = (category or "SMART LIBRARY").upper()
    draw.text((width // 2, 90), tag_text, fill=c_accent, anchor='mm')
    draw.line([(100, 130), (width - 100, 130)], fill=c_accent, width=2)
    
    words = title.split()
    lines, curr = [], ""
    for w in words:
        if len(curr + " " + w) <= 18:
            curr += (" " + w if curr else w)
        else:
            lines.append(curr)
            curr = w
    if curr:
        lines.append(curr)
        
    y_start = 320 - (len(lines) * 25)
    for i, line in enumerate(lines[:5]):
        draw.text((width // 2, y_start + i * 50), line.upper(), fill=(255, 255, 255), anchor='mm')
        
    draw.line([(180, 580), (width - 180, 580)], fill=(255, 255, 255, 100), width=1)
    if author:
        authors_short = author.split('-')[0].strip()
        if len(authors_short) > 30:
            authors_short = authors_short[:27] + '...'
        draw.text((width // 2, 620), f"BY {authors_short.upper()}", fill=(220, 230, 242), anchor='mm')
        
    draw.rectangle((80, height - 120, width - 80, height - 80), fill=(*c_dark, 200), outline=c_accent)
    draw.text((width // 2, height - 100), f"ISBN: {isbn}" if isbn else "SMART LIBRARY EDITION", fill=(255, 255, 255), anchor='mm')
    
    out_io = io.BytesIO()
    img.save(out_io, format='JPEG', quality=90)
    return out_io.getvalue()


def populate_covers(limit=None):
    ensure_default_cover()
    app = create_app()
    with app.app_context():
        books = Book.query.order_by(Book.id.asc()).all()
        if limit is not None:
            books = books[:limit]

        updated = 0
        skipped = 0

        for book in books:
            clean_isbn = normalise_isbn(book.isbn) or f"book_{book.id}"
            out_file = os.path.join(COVERS_DIR, f"{clean_isbn}.jpg")
            
            if os.path.exists(out_file) and os.path.getsize(out_file) > 3000:
                skipped += 1
                continue

            img_data = fetch_openlibrary_isbn(clean_isbn) if len(clean_isbn) >= 10 else None
            if not img_data and len(clean_isbn) >= 10:
                img_data = fetch_google_books(f"isbn:{clean_isbn}")

            if not img_data:
                img_data = fetch_google_books(f"intitle:{book.title}")

            if not img_data:
                author_name = book.author.name if book.author else ""
                cat_name = book.category.name if book.category else "Technical"
                img_data = generate_styled_cover(book.title, author_name, cat_name, clean_isbn)

            with open(out_file, 'wb') as f:
                f.write(img_data)

            book.cover_image = f"book_covers/{clean_isbn}.jpg"
            updated += 1

        db.session.commit()
        print(f'Updated covers: {updated}')
        print(f'Skipped: {skipped}')


if __name__ == '__main__':
    populate_covers()
