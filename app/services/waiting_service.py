from datetime import datetime, timedelta
from app import db
from app.models import Book, Student, Reservation, WaitingList, Notification
from app.utils.helpers import log_audit, get_setting

def reserve_or_join_waiting_list(student_id, book_id):
    """Adds student to reservation queue or FIFO waiting list if book is out of stock."""
    student = Student.query.get(student_id)
    book = Book.query.get(book_id)

    if not student or not book:
        return False, "Student or book not found."

    # Check existing active reservation or waiting list entry
    existing_res = Reservation.query.filter_by(student_id=student.id, book_id=book.id, status='PENDING').first()
    if existing_res:
        return False, "You already have an active reservation for this book."

    existing_wl = WaitingList.query.filter_by(student_id=student.id, book_id=book.id).filter(WaitingList.status.in_(['WAITING', 'NOTIFIED'])).first()
    if existing_wl:
        return False, "You are already on the waiting list for this book."

    # Current queue position
    current_max_pos = db.session.query(db.func.max(WaitingList.queue_position)).filter_by(book_id=book.id).scalar() or 0
    next_pos = current_max_pos + 1

    waiting_entry = WaitingList(
        book_id=book.id,
        student_id=student.id,
        joined_at=datetime.utcnow(),
        queue_position=next_pos,
        status='WAITING'
    )
    db.session.add(waiting_entry)

    res_entry = Reservation(
        student_id=student.id,
        book_id=book.id,
        reservation_date=datetime.utcnow(),
        status='PENDING',
        queue_position=next_pos
    )
    db.session.add(res_entry)
    db.session.commit()

    log_audit("RESERVE_BOOK", "Reservation", res_entry.id, f"Student {student.name} reserved '{book.title}' (Queue pos: {next_pos})")
    return True, f"Reservation confirmed for '{book.title}'. Your position in line is #{next_pos}."
