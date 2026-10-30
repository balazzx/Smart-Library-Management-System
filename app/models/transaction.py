from datetime import datetime
from app import db

class BookRequest(db.Model):
    __tablename__ = 'book_requests'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='PENDING') # PENDING, APPROVED, REJECTED, CANCELLED, FULFILLED
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)

    reviewer = db.relationship('User', foreign_keys=[reviewer_id])


class BorrowTransaction(db.Model):
    __tablename__ = 'borrow_transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_ref = db.Column(db.String(50), unique=True, nullable=True) # TRN-000001
    copy_id = db.Column(db.Integer, db.ForeignKey('book_copies.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='ISSUED') # ISSUED, RETURNED, OVERDUE, LOST
    fine_amount = db.Column(db.Float, default=0.0)
    is_fine_paid = db.Column(db.Boolean, default=False)
    renewal_count = db.Column(db.Integer, default=0)
    issued_by = db.Column(db.String(100), nullable=True)
    returned_to = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    return_records = db.relationship('ReturnTransaction', backref='borrow_transaction', lazy='dynamic')
    fines = db.relationship('Fine', backref='transaction', lazy='dynamic')

    @property
    def is_overdue(self):
        if self.status == 'ISSUED' and datetime.utcnow() > self.due_date:
            return True
        return False

    @property
    def overdue_days(self):
        if self.is_overdue:
            delta = datetime.utcnow() - self.due_date
            return max(0, delta.days)
        elif self.return_date and self.return_date > self.due_date:
            delta = self.return_date - self.due_date
            return max(0, delta.days)
        return 0


class ReturnTransaction(db.Model):
    __tablename__ = 'return_transactions'

    id = db.Column(db.Integer, primary_key=True)
    borrow_transaction_id = db.Column(db.Integer, db.ForeignKey('borrow_transactions.id'), nullable=False)
    return_date = db.Column(db.DateTime, default=datetime.utcnow)
    condition_on_return = db.Column(db.String(50), default='GOOD')
    fine_assessed = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)


class Reservation(db.Model):
    __tablename__ = 'reservations'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    reservation_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='PENDING') # PENDING, FULFILLED, EXPIRED, CANCELLED
    queue_position = db.Column(db.Integer, default=1)
    expiry_date = db.Column(db.DateTime, nullable=True)


class WaitingList(db.Model):
    __tablename__ = 'waiting_list'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    queue_position = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='WAITING') # WAITING, NOTIFIED, EXPIRED, FULFILLED
    notified_at = db.Column(db.DateTime, nullable=True)
