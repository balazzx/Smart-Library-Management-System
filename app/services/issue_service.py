from datetime import datetime, timedelta
from app import db
from app.models import Book, BookCopy, BookRequest, BorrowTransaction, Student, User, Notification
from app.email.mail_service import send_email
from app.utils.helpers import log_audit, get_setting

def create_book_request(student_id, book_id):
    """Student submits a request for a book."""
    student = Student.query.get(student_id)
    book = Book.query.get(book_id)

    if not student or not book:
        return False, "Student or book record not found."

    # 1. Active borrow limit check
    active_borrows = BorrowTransaction.query.filter_by(student_id=student.id, status='ISSUED').count()
    max_limit = student.max_borrow_limit or get_setting('MAX_BORROW_LIMIT', 5)
    if active_borrows >= max_limit:
        return False, f"Maximum borrow limit reached ({max_limit} books)."

    # 2. Check duplicate pending request
    existing_req = BookRequest.query.filter_by(student_id=student.id, book_id=book.id, status='PENDING').first()
    if existing_req:
        return False, "You already have a pending request for this book."

    # 3. Check duplicate active borrow
    active_copy = db.session.query(BorrowTransaction).join(BookCopy).filter(
        BorrowTransaction.student_id == student.id,
        BorrowTransaction.status == 'ISSUED',
        BookCopy.book_id == book.id
    ).first()
    if active_copy:
        return False, "You currently have a copy of this book issued."

    # 4. Check book availability
    available_copies = BookCopy.query.filter_by(book_id=book.id, status='AVAILABLE').count()
    if available_copies == 0:
        return False, "No copies are currently available. You can reserve this book instead."

    request_record = BookRequest(
        student_id=student.id,
        book_id=book.id,
        request_date=datetime.utcnow(),
        status='PENDING'
    )
    db.session.add(request_record)
    db.session.commit()

    log_audit("BOOK_REQUEST", "BookRequest", request_record.id, f"Student {student.name} requested book '{book.title}'")
    return True, "Book request submitted successfully. Awaiting librarian approval."


def approve_and_issue_book(request_id, reviewer_user_id):
    """Librarian approves a request and issues an available physical copy."""
    req = BookRequest.query.get(request_id)
    if not req or req.status != 'PENDING':
        return False, "Invalid or processed request."

    student = req.student
    book = req.book
    available_copy = BookCopy.query.filter_by(book_id=book.id, status='AVAILABLE').first()
    if not available_copy:
        return False, "No copies currently available to fulfill issue."

    borrow_days = get_setting('BORROW_PERIOD_DAYS', 14)
    issue_dt = datetime.utcnow()
    due_dt = issue_dt + timedelta(days=borrow_days)

    # Update Request
    req.status = 'APPROVED'
    req.reviewer_id = reviewer_user_id
    req.review_date = issue_dt

    # Update Copy Status
    available_copy.status = 'ISSUED'

    # Create Transaction
    tx = BorrowTransaction(
        copy_id=available_copy.id,
        student_id=student.id,
        issue_date=issue_dt,
        due_date=due_dt,
        status='ISSUED'
    )
    db.session.add(tx)
    db.session.commit()

    # Notifications & Emails
    notif_msg = f"Your request for '{book.title}' has been approved! Copy ID: {available_copy.copy_code}. Due date: {due_dt.strftime('%B %d, %Y')}."
    if student.user:
        notif = Notification(user_id=student.user.id, title="Book Request Approved", message=notif_msg, category='Issue', link='/student/my-books')
        db.session.add(notif)
        send_email(student.user.email, "Book Issued Notification", notif_msg, 'ISSUE_APPROVED')

    db.session.commit()
    log_audit("ISSUE_BOOK", "BorrowTransaction", tx.id, f"Issued copy {available_copy.copy_code} to student {student.name}")
    return True, f"Book '{book.title}' successfully issued. Copy Code: {available_copy.copy_code}."


def direct_issue_book(student_id, copy_id, issuer_user_id):
    """Directly issue a copy to a student without prior online request."""
    student = Student.query.get(student_id)
    copy = BookCopy.query.get(copy_id)

    if not student or not copy:
        return False, "Student or copy record not found."

    if copy.status != 'AVAILABLE':
        return False, f"Physical copy {copy.copy_code} is not AVAILABLE (Current status: {copy.status})."

    active_borrows = BorrowTransaction.query.filter_by(student_id=student.id, status='ISSUED').count()
    max_limit = student.max_borrow_limit or get_setting('MAX_BORROW_LIMIT', 5)
    if active_borrows >= max_limit:
        return False, f"Student has reached maximum borrow limit ({max_limit} books)."

    borrow_days = get_setting('BORROW_PERIOD_DAYS', 14)
    issue_dt = datetime.utcnow()
    due_dt = issue_dt + timedelta(days=borrow_days)

    copy.status = 'ISSUED'
    tx = BorrowTransaction(
        copy_id=copy.id,
        student_id=student.id,
        issue_date=issue_dt,
        due_date=due_dt,
        status='ISSUED'
    )
    db.session.add(tx)
    db.session.commit()

    notif_msg = f"Book '{copy.book.title}' (Copy: {copy.copy_code}) has been issued to you. Due date: {due_dt.strftime('%B %d, %Y')}."
    if student.user:
        notif = Notification(user_id=student.user.id, title="Book Issued", message=notif_msg, category='Issue', link='/student/my-books')
        db.session.add(notif)
        send_email(student.user.email, "Book Issued Notification", notif_msg, 'ISSUE_DIRECT')

    db.session.commit()
    log_audit("DIRECT_ISSUE", "BorrowTransaction", tx.id, f"Directly issued copy {copy.copy_code} to student {student.name}")
    return True, f"Issued copy {copy.copy_code} to student {student.name}."
