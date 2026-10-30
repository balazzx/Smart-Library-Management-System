from datetime import datetime
from app import db

class Wishlist(db.Model):
    __tablename__ = 'wishlist'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('student_id', 'book_id', name='unique_wishlist'),)


class RatingReview(db.Model):
    __tablename__ = 'ratings_reviews'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1 to 5
    review_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('student_id', 'book_id', name='unique_review'),)


class Announcement(db.Model):
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='MEDIUM') # LOW, MEDIUM, HIGH, URGENT
    target_department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True) # Null = ALL
    target_role = db.Column(db.String(20), default='ALL') # ALL, STUDENT, LIBRARIAN
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User')


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='System') # Issue, Return, Due Date, Overdue, Reservation, Fine, Wishlist, Announcement, System
    is_read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SearchHistory(db.Model):
    __tablename__ = 'search_history'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    query_text = db.Column(db.String(255), nullable=False)
    result_count = db.Column(db.Integer, default=0)
    selected_book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='SET NULL'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    selected_book = db.relationship('Book')

