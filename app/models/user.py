from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='STUDENT') # STUDENT, LIBRARIAN, ADMIN
    is_active = db.Column(db.Boolean, default=True)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student_profile = db.relationship('Student', backref='user', uselist=False, cascade='all, delete-orphan')
    librarian_profile = db.relationship('Librarian', backref='user', uselist=False, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_student(self):
        return self.role == 'STUDENT'

    def is_librarian(self):
        return self.role == 'LIBRARIAN'

    def is_admin(self):
        return self.role == 'ADMIN'


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False) # CSE, IT, AI & DS, CSBS, ECE, EEE, ECX, Mechanical, Civil
    name = db.Column(db.String(100), nullable=False)

    students = db.relationship('Student', backref='department', lazy='dynamic')
    librarians = db.relationship('Librarian', backref='department', lazy='dynamic')
    digital_resources = db.relationship('DigitalResource', backref='target_department', lazy='dynamic')
    announcements = db.relationship('Announcement', backref='target_department', lazy='dynamic')


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=False) # College Roll No
    name = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    phone = db.Column(db.String(20))
    library_card_number = db.Column(db.String(50), unique=True, nullable=False)
    reg_no = db.Column(db.String(50), nullable=True)
    section = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    mentor_name = db.Column(db.String(150), nullable=True)
    class_advisor = db.Column(db.String(150), nullable=True)
    max_borrow_limit = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    requests = db.relationship('BookRequest', backref='student', lazy='dynamic')
    borrow_transactions = db.relationship('BorrowTransaction', backref='student', lazy='dynamic')
    reservations = db.relationship('Reservation', backref='student', lazy='dynamic')
    wishlists = db.relationship('Wishlist', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    reviews = db.relationship('RatingReview', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    fines = db.relationship('Fine', backref='student', lazy='dynamic')
    search_histories = db.relationship('SearchHistory', backref='student', lazy='dynamic', cascade='all, delete-orphan')


class Librarian(db.Model):
    __tablename__ = 'librarians'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    staff_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    phone = db.Column(db.String(20))
