from datetime import datetime
from app import db

class Fine(db.Model):
    __tablename__ = 'fines'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('borrow_transactions.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='UNPAID') # UNPAID, PAID, WAIVED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    payment_method = db.Column(db.String(50), nullable=True) # Cash, Online, Card
    transaction_ref = db.Column(db.String(100), nullable=True)


class EmailLog(db.Model):
    __tablename__ = 'email_logs'

    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    email_type = db.Column(db.String(50), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='PENDING') # SENT, FAILED, PENDING
    error_message = db.Column(db.Text, nullable=True)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    role = db.Column(db.String(20), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PredictionLog(db.Model):
    __tablename__ = 'predictions'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    target_month = db.Column(db.String(20), nullable=False)
    predicted_demand = db.Column(db.Float, nullable=False)
    demand_level = db.Column(db.String(20), nullable=False) # HIGH, MEDIUM, LOW
    confidence_score = db.Column(db.Float, default=0.0)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)

    book = db.relationship('Book')
