import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.models.book import Book

def search_books_nlp(query_string, top_n=20):
    """
    Performs Smart NLP Search using TF-IDF and Cosine Similarity over book metadata.
    Returns ranked books with relevance percentage and explanatory match reasons.
    """
    if not query_string or not query_string.strip():
        return []

    books = Book.query.all()
    if not books:
        return []

    corpus = []
    book_list = []

    for b in books:
        title = b.title or ""
        desc = b.description or ""
        cat = b.category.name if b.category else ""
        auth = b.author.name if b.author else ""
        pub = b.publisher.name if b.publisher else ""

        text_content = f"{title} {title} {desc} {cat} {cat} {auth} {pub}"
        corpus.append(text_content)
        book_list.append(b)

    vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        query_vec = vectorizer.transform([query_string])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    except Exception as e:
        print(f"NLP search vectorization error: {e}")
        return []

    # Sort indices by similarity
    ranked_indices = np.argsort(similarities)[::-1]

    results = []
    query_words = set(query_string.lower().split())

    for idx in ranked_indices:
        score = float(similarities[idx])
        if score <= 0.01:
            continue

        book = book_list[idx]
        relevance_pct = min(100, int(score * 100) + 15)

        # Generate explanatory match reason
        match_reasons = []
        if any(w in book.title.lower() for w in query_words):
            match_reasons.append("Title keywords")
        if book.category and any(w in book.category.name.lower() for w in query_words):
            match_reasons.append(f"Category '{book.category.name}'")
        if book.author and any(w in book.author.name.lower() for w in query_words):
            match_reasons.append(f"Author '{book.author.name}'")
        if any(w in (book.description or "").lower() for w in query_words):
            match_reasons.append("Description context")

        reason_str = f"Matched via {', '.join(match_reasons)}" if match_reasons else "Semantic similarity match"

        results.append({
            'book': book,
            'relevance_pct': relevance_pct,
            'score': round(score, 3),
            'match_reason': reason_str
        })

        if len(results) >= top_n:
            break

    return results
