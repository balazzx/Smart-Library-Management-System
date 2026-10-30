from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from app import db
from app.models import (
    User, Student, Book, BookCopy, BorrowTransaction, BookRequest,
    Reservation, WaitingList, Wishlist, RatingReview, DigitalResource,
    Notification, Announcement, SearchHistory, Fine, Category, Author, Department
)
from app.utils.decorators import student_required
from app.services.issue_service import create_book_request
from app.services.waiting_service import reserve_or_join_waiting_list
from app.services.fine_service import pay_fine
from app.services.qr_service import generate_student_card_qr, generate_book_qr
from app.ml.nlp_search import search_books_nlp
from app.ml.recommendation_engine import get_personalized_recommendations
from app.utils.helpers import log_audit, get_setting

student_bp = Blueprint('student', __name__)

@student_bp.route('/dashboard')
@student_required
def dashboard():
    user = User.query.get(session['user_id'])
    student = user.student_profile

    # KPIs
    active_borrows = BorrowTransaction.query.filter_by(student_id=student.id, status='ISSUED').all()
    current_books_count = len(active_borrows)
    
    now = datetime.utcnow()
    due_soon_count = sum(1 for tx in active_borrows if 0 <= (tx.due_date - now).days <= 3)
    overdue_count = sum(1 for tx in active_borrows if now > tx.due_date)

    pending_requests_count = BookRequest.query.filter_by(student_id=student.id, status='PENDING').count()
    reservations_count = Reservation.query.filter_by(student_id=student.id, status='PENDING').count()
    wishlist_count = Wishlist.query.filter_by(student_id=student.id).count()

    unpaid_fines = Fine.query.filter_by(student_id=student.id, status='UNPAID').all()
    total_fines_due = sum(f.amount for f in unpaid_fines)

    # Recommendations
    recommendations = get_personalized_recommendations(student.id, top_n=4)

    # Announcements
    announcements = Announcement.query.filter(
        (Announcement.target_role.in_(['ALL', 'STUDENT'])) &
        ((Announcement.target_department_id == None) | (Announcement.target_department_id == student.department_id))
    ).order_by(Announcement.created_at.desc()).limit(5).all()

    # Notifications
    recent_notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(5).all()

    return render_template(
        'student/dashboard.html',
        student=student,
        current_books_count=current_books_count,
        due_soon_count=due_soon_count,
        overdue_count=overdue_count,
        pending_requests_count=pending_requests_count,
        reservations_count=reservations_count,
        wishlist_count=wishlist_count,
        total_fines_due=total_fines_due,
        active_borrows=active_borrows,
        recommendations=recommendations,
        announcements=announcements,
        notifications=recent_notifications
    )


@student_bp.route('/books')
@student_required
def search_books():
    query_str = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', type=int)
    author_id = request.args.get('author_id', type=int)
    search_mode = request.args.get('mode', 'standard')
    page = request.args.get('page', 1, type=int)

    user = User.query.get(session['user_id'])
    student = user.student_profile

    if search_mode == 'nlp' and query_str:
        nlp_results = search_books_nlp(query_str, top_n=30)
        categories = Category.query.all()
        authors = Author.query.all()
        if student and query_str:
            sh = SearchHistory(student_id=student.id, query_text=query_str, result_count=len(nlp_results))
            db.session.add(sh)
            db.session.commit()
        return render_template('student/books_search.html', nlp_results=nlp_results, categories=categories, authors=authors, mode='nlp', query=query_str)

    # Standard database search
    query = Book.query
    if query_str:
        search_filter = f"%{query_str}%"
        query = query.filter(
            (Book.title.like(search_filter)) |
            (Book.isbn.like(search_filter)) |
            (Book.description.like(search_filter)) |
            (Book.subject.like(search_filter)) |
            (Book.access_no.like(search_filter)) |
            (Book.author.has(Author.name.like(search_filter))) |
            (Book.category.has(Category.name.like(search_filter))) |
            (Book.department.has(Department.name.like(search_filter)))
        )
    if category_id:
        query = query.filter_by(category_id=category_id)
    if author_id:
        query = query.filter_by(author_id=author_id)

    total_matches = query.count()
    pagination = query.order_by(Book.title.asc()).paginate(page=page, per_page=12, error_out=False)
    books = pagination.items

    categories = Category.query.all()
    authors = Author.query.all()

    # Save search history if query string present
    if query_str and student:
        sh = SearchHistory(student_id=student.id, query_text=query_str, result_count=total_matches)
        db.session.add(sh)
        db.session.commit()

    return render_template(
        'student/books_search.html',
        books=books,
        pagination=pagination,
        categories=categories,
        authors=authors,
        mode='standard',
        query=query_str,
        selected_category=category_id,
        selected_author=author_id
    )


@student_bp.route('/books/<int:book_id>')
@student_required
def book_details(book_id):
    book = Book.query.get_or_404(book_id)
    user = User.query.get(session['user_id'])
    student = user.student_profile

    # Update latest search history item if within 5 mins
    if student:
        latest_sh = SearchHistory.query.filter_by(student_id=student.id).order_by(SearchHistory.timestamp.desc()).first()
        if latest_sh and not latest_sh.selected_book_id:
            latest_sh.selected_book_id = book.id
            db.session.commit()

    active_borrow = BorrowTransaction.query.filter_by(
        student_id=student.id, status='ISSUED'
    ).join(BookCopy).filter(BookCopy.book_id == book_id).first()

    active_request = BookRequest.query.filter_by(
        student_id=student.id, book_id=book_id, status='PENDING'
    ).first()

    in_wishlist = Wishlist.query.filter_by(
        student_id=student.id, book_id=book_id
    ).first() is not None

    user_review = RatingReview.query.filter_by(
        student_id=student.id, book_id=book_id
    ).first()

    qr_url = generate_book_qr(book.id)

    return render_template(
        'student/book_details.html',
        book=book,
        active_borrow=active_borrow,
        active_request=active_request,
        in_wishlist=in_wishlist,
        user_review=user_review,
        qr_url=qr_url
    )


@student_bp.route('/search-history')
@student_required
def search_history():
    user = User.query.get(session['user_id'])
    student = user.student_profile
    history_items = SearchHistory.query.filter_by(student_id=student.id).order_by(SearchHistory.timestamp.desc()).all()
    return render_template('student/search_history.html', history_items=history_items)


@student_bp.route('/search-history/delete/<int:history_id>', methods=['POST'])
@student_required
def delete_search_history_item(history_id):
    user = User.query.get(session['user_id'])
    student = user.student_profile
    item = SearchHistory.query.filter_by(id=history_id, student_id=student.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('Search entry deleted.', 'info')
    return redirect(url_for('student.search_history'))


@student_bp.route('/search-history/clear', methods=['POST'])
@student_required
def clear_search_history():
    user = User.query.get(session['user_id'])
    student = user.student_profile
    SearchHistory.query.filter_by(student_id=student.id).delete()
    db.session.commit()
    flash('All search history cleared.', 'info')
    return redirect(url_for('student.search_history'))


@student_bp.route('/request/<int:book_id>', methods=['POST'])
@student_required
def request_book(book_id):
    user = User.query.get(session['user_id'])
    student = user.student_profile
    success, msg = create_book_request(student.id, book_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'warning')
    return redirect(url_for('student.book_details', book_id=book_id))


@student_bp.route('/reserve/<int:book_id>', methods=['POST'])
@student_required
def reserve_book(book_id):
    user = User.query.get(session['user_id'])
    student = user.student_profile
    success, msg = reserve_or_join_waiting_list(student.id, book_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'warning')
    return redirect(url_for('student.book_details', book_id=book_id))


@student_bp.route('/my-books')
@student_required
def my_books():
    user = User.query.get(session['user_id'])
    student = user.student_profile

    active_borrows = BorrowTransaction.query.filter_by(student_id=student.id, status='ISSUED').order_by(BorrowTransaction.due_date.asc()).all()
    past_borrows = BorrowTransaction.query.filter_by(student_id=student.id, status='RETURNED').order_by(BorrowTransaction.return_date.desc()).all()
    unpaid_fines = Fine.query.filter_by(student_id=student.id, status='UNPAID').all()

    return render_template(
        'student/my_books.html',
        active_borrows=active_borrows,
        past_borrows=past_borrows,
        unpaid_fines=unpaid_fines
    )


@student_bp.route('/wishlist')
@student_required
def wishlist():
    user = User.query.get(session['user_id'])
    student = user.student_profile
    items = Wishlist.query.filter_by(student_id=student.id).all()
    return render_template('student/wishlist.html', items=items)


@student_bp.route('/wishlist/toggle/<int:book_id>', methods=['POST'])
@student_required
def toggle_wishlist(book_id):
    user = User.query.get(session['user_id'])
    student = user.student_profile

    existing = Wishlist.query.filter_by(student_id=student.id, book_id=book_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Book removed from wishlist.', 'info')
    else:
        w = Wishlist(student_id=student.id, book_id=book_id)
        db.session.add(w)
        db.session.commit()
        flash('Book added to wishlist!', 'success')
    return redirect(request.referrer or url_for('student.wishlist'))


@student_bp.route('/reviews/add/<int:book_id>', methods=['POST'])
@student_required
def add_review(book_id):
    user = User.query.get(session['user_id'])
    student = user.student_profile

    rating = request.form.get('rating', type=int)
    review_text = request.form.get('review_text', '').strip()

    if not rating or not (1 <= rating <= 5):
        flash('Please select a valid rating (1 to 5 stars).', 'warning')
        return redirect(url_for('student.book_details', book_id=book_id))

    existing = RatingReview.query.filter_by(student_id=student.id, book_id=book_id).first()
    if existing:
        existing.rating = rating
        existing.review_text = review_text
        flash('Your review has been updated.', 'success')
    else:
        rev = RatingReview(student_id=student.id, book_id=book_id, rating=rating, review_text=review_text)
        db.session.add(rev)
        flash('Thank you for your rating & review!', 'success')

    db.session.commit()
    log_audit('REVIEW_BOOK', 'RatingReview', book_id, f"Student {student.name} rated book ID {book_id} with {rating} stars.")
    return redirect(url_for('student.book_details', book_id=book_id))


@student_bp.route('/recommendations')
@student_required
def recommendations():
    user = User.query.get(session['user_id'])
    student = user.student_profile
    recs = get_personalized_recommendations(student.id, top_n=10)
    return render_template('student/recommendations.html', recommendations=recs)


@student_bp.route('/analytics')
@student_required
def analytics():
    user = User.query.get(session['user_id'])
    student = user.student_profile

    all_txs = BorrowTransaction.query.filter_by(student_id=student.id).all()
    total_read = len(all_txs)
    current_reading = sum(1 for t in all_txs if t.status == 'ISSUED')

    on_time = sum(1 for t in all_txs if t.return_date and t.return_date <= t.due_date)
    on_time_pct = round((on_time / len(all_txs)) * 100, 1) if all_txs else 100.0

    return render_template(
        'student/analytics.html',
        total_read=total_read,
        current_reading=current_reading,
        on_time_pct=on_time_pct
    )


@student_bp.route('/digital-library')
@student_required
def digital_library():
    user = User.query.get(session['user_id'])
    student = user.student_profile
    resources = DigitalResource.query.filter(
        (DigitalResource.target_department_id == None) |
        (DigitalResource.target_department_id == student.department_id)
    ).order_by(DigitalResource.upload_date.desc()).all()
    return render_template('student/digital_library.html', resources=resources)


@student_bp.route('/digital-card')
@student_required
def digital_card():
    user = User.query.get(session['user_id'])
    student = user.student_profile
    qr_url = generate_student_card_qr(student.library_card_number)
    return render_template('student/digital_card.html', student=student, qr_url=qr_url)


@student_bp.route('/library-map')
@student_required
def library_map():
    selected_book_id = request.args.get('book_id', type=int)
    selected_book = Book.query.get(selected_book_id) if selected_book_id else None
    books = Book.query.order_by(Book.title.asc()).all()
    return render_template('student/library_map.html', books=books, selected_book=selected_book)


@student_bp.route('/notifications')
@student_required
def notifications():
    user = User.query.get(session['user_id'])
    notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    return render_template('student/notifications.html', notifications=notifs)


@student_bp.route('/notifications/mark-read/<int:notif_id>')
@student_required
def mark_notification_read(notif_id):
    user = User.query.get(session['user_id'])
    notif = Notification.query.filter_by(id=notif_id, user_id=user.id).first()
    if notif:
        notif.is_read = True
        db.session.commit()
    return redirect(request.referrer or url_for('student.notifications'))


@student_bp.route('/pay-fine/<int:fine_id>', methods=['POST'])
@student_required
def pay_fine_student(fine_id):
    payment_method = request.form.get('payment_method', 'Online Card')
    success, msg = pay_fine(fine_id, payment_method=payment_method)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('student.my_books'))


@student_bp.route('/reservations')
@student_required
def reservations():
    user = db.session.get(User, session['user_id'])
    student = user.student_profile
    active_reservations = Reservation.query.filter_by(student_id=student.id).order_by(Reservation.reservation_date.desc()).all()
    waiting_entries = WaitingList.query.filter_by(student_id=student.id).order_by(WaitingList.joined_at.desc()).all()
    return render_template('student/reservations.html', reservations=active_reservations, waiting_entries=waiting_entries)


@student_bp.route('/reservations/cancel/<int:res_id>', methods=['POST'])
@student_required
def cancel_reservation(res_id):
    user = db.session.get(User, session['user_id'])
    student = user.student_profile
    res = Reservation.query.filter_by(id=res_id, student_id=student.id).first()
    if res and res.status == 'PENDING':
        res.status = 'CANCELLED'
        wl = WaitingList.query.filter_by(student_id=student.id, book_id=res.book_id, status='WAITING').first()
        if wl:
            wl.status = 'EXPIRED'
        db.session.commit()
        log_audit('CANCEL_RESERVATION', 'Reservation', res.id, f"Student {student.name} cancelled reservation")
        flash('Reservation cancelled.', 'info')
    else:
        flash('Reservation not found or already processed.', 'warning')
    return redirect(url_for('student.reservations'))


@student_bp.route('/requests')
@student_required
def requests_page():
    user = db.session.get(User, session['user_id'])
    student = user.student_profile
    requests_list = BookRequest.query.filter_by(student_id=student.id).order_by(BookRequest.request_date.desc()).all()
    return render_template('student/requests.html', requests=requests_list)


@student_bp.route('/profile', methods=['GET', 'POST'])
@student_required
def profile():
    user = db.session.get(User, session['user_id'])
    student = user.student_profile

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()

        if email and email != user.email:
            existing = User.query.filter(User.email.ilike(email), User.id != user.id).first()
            if existing:
                flash('This email address is already in use by another account.', 'danger')
                return redirect(url_for('student.profile'))
            user.email = email

        student.phone = phone
        db.session.commit()
        log_audit('UPDATE_PROFILE', 'Student', student.id, f"Student {student.name} updated profile contact info")
        flash('Profile contact information updated successfully!', 'success')
        return redirect(url_for('student.profile'))

    return render_template('student/profile.html', student=student, user=user)

