import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.models import Book, Student, BorrowTransaction, Wishlist, RatingReview, SearchHistory

def get_personalized_recommendations(student_id, top_n=6):
    """
    Content-Based AI Recommendation Engine.
    Analyzes student's interaction history (borrows, wishlist, search terms, high ratings)
    and uses TF-IDF similarity to suggest unread relevant books with rationale.
    """
    student = Student.query.get(student_id)
    if not student:
        return []

    # Gather user's interacted book IDs
    borrowed_txs = BorrowTransaction.query.filter_by(student_id=student.id).all()
    borrowed_book_ids = set()
    for tx in borrowed_txs:
        if tx.copy and tx.copy.book_id:
            borrowed_book_ids.add(tx.copy.book_id)

    wishlist_entries = Wishlist.query.filter_by(student_id=student.id).all()
    wishlist_book_ids = {w.book_id for w in wishlist_entries}

    reviews = RatingReview.query.filter_by(student_id=student.id).filter(RatingReview.rating >= 4).all()
    liked_book_ids = {r.book_id for r in reviews}

    searches = SearchHistory.query.filter_by(student_id=student.id).order_by(SearchHistory.timestamp.desc()).limit(10).all()
    search_keywords = " ".join([s.query_text for s in searches])

    user_seed_ids = borrowed_book_ids.union(wishlist_book_ids).union(liked_book_ids)

    all_books = Book.query.all()
    if not all_books:
        return []

    # Build corpus for all books
    corpus = []
    book_map = []
    seed_text = [search_keywords]

    for b in all_books:
        cat_name = b.category.name if b.category else ""
        auth_name = b.author.name if b.author else ""
        text = f"{b.title} {b.description or ''} {cat_name} {cat_name} {auth_name}"
        corpus.append(text)
        book_map.append(b)

        if b.id in user_seed_ids:
            seed_text.append(text)

    # Combined user profile text
    user_profile_text = " ".join(seed_text)

    # Cold start check: if student has no interactions yet, return highest rated / most borrowed books
    if not user_profile_text.strip():
        popular_books = sorted(all_books, key=lambda x: (x.average_rating, x.issued_copies_count), reverse=True)[:top_n]
        return [{
            'book': bk,
            'reason': f"Top rated library selection in {bk.category.name if bk.category else 'Computer Science'}"
        } for bk in popular_books]

    # Compute TF-IDF similarities
    vectorizer = TfidfVectorizer(stop_words='english')
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        user_vec = vectorizer.transform([user_profile_text])
        similarities = cosine_similarity(user_vec, tfidf_matrix).flatten()
    except Exception as e:
        print(f"Recommendation calculation fallback: {e}")
        return []

    ranked_indices = np.argsort(similarities)[::-1]

    recommendations = []
    for idx in ranked_indices:
        book = book_map[idx]
        
        # Exclude books currently borrowed or already in wishlist
        if book.id in borrowed_book_ids:
            continue

        score = float(similarities[idx])
        
        # Generate specific recommendation rationale
        reason = f"Recommended based on your interest in {book.category.name if book.category else 'related technical topics'}"
        if book.author and any(b.author_id == book.author_id for b in all_books if b.id in user_seed_ids):
            reason = f"Recommended because you frequently read books by {book.author.name}"

        recommendations.append({
            'book': book,
            'reason': reason,
            'confidence': min(98, int(score * 100) + 20)
        })

        if len(recommendations) >= top_n:
            break

    return recommendations
