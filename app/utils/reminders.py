from datetime import datetime, timedelta
from app import db
from app.models import BorrowTransaction, Notification, WaitingList, BookCopy, Book, Student, User
from app.email.mail_service import send_email
from app.utils.helpers import get_setting

def process_automated_reminders():
    """Scans database for due dates, overdues, and expired waiting list reservations."""
    now = datetime.utcnow()
    processed_count = 0

    # 1. Check transactions due in 3 days, 1 day, or overdue
    active_borrows = BorrowTransaction.query.filter_by(status='ISSUED').all()
    grace_period = get_setting('GRACE_PERIOD_DAYS', 2)
    fine_per_day = get_setting('FINE_PER_DAY', 5.0)

    for tx in active_borrows:
        time_diff = tx.due_date - now
        days_left = time_diff.days

        student = tx.student
        if not student or not student.user:
            continue

        user = student.user
        book = tx.copy.book if tx.copy else None
        book_title = book.title if book else 'Library Book'

        # Due tomorrow or in 3 days notification
        if 0 <= days_left <= 3:
            existing_notif = Notification.query.filter_by(
                user_id=user.id,
                category='Due Date',
                link=f'/student/my-books'
            ).filter(Notification.created_at >= now - timedelta(days=1)).first()

            if not existing_notif:
                title = f"Reminder: '{book_title}' Due Soon"
                msg = f"Your borrowed book '{book_title}' is due on {tx.due_date.strftime('%B %d, %Y')}. Please return or renew it to avoid fines."
                notif = Notification(user_id=user.id, title=title, message=msg, category='Due Date', link='/student/my-books')
                db.session.add(notif)
                send_email(user.email, title, msg, 'DUE_REMINDER')
                processed_count += 1

        # Overdue handling
        elif now > tx.due_date:
            overdue_days = max(0, (now - tx.due_date).days)
            billable_days = max(0, overdue_days - grace_period)
            calc_fine = billable_days * fine_per_day
            tx.fine_amount = calc_fine

            existing_notif = Notification.query.filter_by(
                user_id=user.id,
                category='Overdue',
                link=f'/student/my-books'
            ).filter(Notification.created_at >= now - timedelta(days=1)).first()

            if not existing_notif:
                title = f"OVERDUE: '{book_title}' is Overdue!"
                msg = f"Your book '{book_title}' was due on {tx.due_date.strftime('%B %d, %Y')} ({overdue_days} days overdue). Current fine accumulated: ₹{calc_fine:.2f}. Please return immediately."
                notif = Notification(user_id=user.id, title=title, message=msg, category='Overdue', link='/student/my-books')
                db.session.add(notif)
                send_email(user.email, title, msg, 'OVERDUE')
                processed_count += 1

    # 2. Check expired waiting list notifications
    claim_hours = get_setting('CLAIM_PERIOD_HOURS', 48)
    expired_waiting = WaitingList.query.filter_by(status='NOTIFIED').all()
    for wl in expired_waiting:
        if wl.notified_at and (now - wl.notified_at) > timedelta(hours=claim_hours):
            wl.status = 'EXPIRED'
            # Promote next student in waiting list
            next_in_line = WaitingList.query.filter_by(book_id=wl.book_id, status='WAITING').order_by(WaitingList.queue_position.asc()).first()
            if next_in_line:
                next_in_line.status = 'NOTIFIED'
                next_in_line.notified_at = now
                st_user = next_in_line.student.user if next_in_line.student else None
                if st_user:
                    bk_title = next_in_line.book.title if next_in_line.book else 'Book'
                    notif_msg = f"Good news! '{bk_title}' is now available for you to collect. Claim period: {claim_hours} hours."
                    notif = Notification(user_id=st_user.id, title=f"Reserved Book Available: {bk_title}", message=notif_msg, category='Reservation', link='/student/reservations')
                    db.session.add(notif)
                    send_email(st_user.email, f"Reserved Book Available: {bk_title}", notif_msg, 'RESERVATION')

    db.session.commit()
    return processed_count
