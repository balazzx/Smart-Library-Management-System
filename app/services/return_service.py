from datetime import datetime
from app import db
from app.models import BorrowTransaction, ReturnTransaction, BookCopy, Fine, WaitingList, Notification
from app.email.mail_service import send_email
from app.utils.helpers import log_audit, get_setting

def process_book_return(transaction_id, condition='GOOD', notes=None):
    """Processes return of a borrowed book copy, calculates fines, and promotes waiting list candidates."""
    tx = BorrowTransaction.query.get(transaction_id)
    if not tx or tx.status != 'ISSUED':
        return False, "Invalid or completed transaction."

    now = datetime.utcnow()
    tx.return_date = now
    tx.status = 'RETURNED'

    # Calculate fine
    grace_period = get_setting('GRACE_PERIOD_DAYS', 2)
    fine_per_day = get_setting('FINE_PER_DAY', 5.0)

    fine_assessed = 0.0
    if now > tx.due_date:
        overdue_days = max(0, (now - tx.due_date).days)
        billable_days = max(0, overdue_days - grace_period)
        fine_assessed = round(billable_days * fine_per_day, 2)
        tx.fine_amount = fine_assessed

    if fine_assessed > 0:
        fine_record = Fine(
            student_id=tx.student_id,
            transaction_id=tx.id,
            amount=fine_assessed,
            reason=f"Overdue return for book '{tx.copy.book.title}'",
            status='UNPAID'
        )
        db.session.add(fine_record)

    # Create Return Record
    return_rec = ReturnTransaction(
        borrow_transaction_id=tx.id,
        return_date=now,
        condition_on_return=condition,
        fine_assessed=fine_assessed,
        notes=notes
    )
    db.session.add(return_rec)

    # Update Copy Status
    copy = tx.copy
    if condition == 'DAMAGED':
        copy.status = 'DAMAGED'
        copy.condition_status = 'DAMAGED'
    elif condition == 'LOST':
        copy.status = 'LOST'
    else:
        copy.status = 'AVAILABLE'

    db.session.commit()

    # Notify student
    student = tx.student
    book_title = copy.book.title
    notif_msg = f"Book '{book_title}' has been returned. Fine assessed: ₹{fine_assessed:.2f}."
    if student and student.user:
        notif = Notification(user_id=student.user.id, title="Book Returned", message=notif_msg, category='Return', link='/student/my-books')
        db.session.add(notif)
        send_email(student.user.email, "Book Return Confirmation", notif_msg, 'RETURN_CONFIRM')

    # Waiting List auto promotion if copy returned to AVAILABLE status
    if copy.status == 'AVAILABLE':
        next_waiting = WaitingList.query.filter_by(book_id=copy.book_id, status='WAITING').order_by(WaitingList.queue_position.asc()).first()
        if next_waiting:
            next_waiting.status = 'NOTIFIED'
            next_waiting.notified_at = now
            st_user = next_waiting.student.user if next_waiting.student else None
            if st_user:
                claim_hours = get_setting('CLAIM_PERIOD_HOURS', 48)
                res_msg = f"Good news! '{book_title}' is now available for claim. You have {claim_hours} hours to request it."
                n = Notification(user_id=st_user.id, title=f"Reserved Book Available: {book_title}", message=res_msg, category='Reservation', link='/student/reservations')
                db.session.add(n)
                send_email(st_user.email, f"Book Available: {book_title}", res_msg, 'RESERVATION_NOTIFY')

    db.session.commit()
    log_audit("RETURN_BOOK", "BorrowTransaction", tx.id, f"Returned copy {copy.copy_code}. Fine: ₹{fine_assessed:.2f}")

    msg = f"Book '{book_title}' successfully returned."
    if fine_assessed > 0:
        msg += f" Fine of ₹{fine_assessed:.2f} applied."
    return True, msg
