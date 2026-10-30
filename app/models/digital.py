from datetime import datetime
from app import db

class DigitalResource(db.Model):
    __tablename__ = 'digital_resources'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(150))
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False) # PDF, EPUB, DOCX, etc.
    file_size = db.Column(db.Integer, nullable=False) # Size in bytes
    target_department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True) # Null means ALL
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    uploader = db.relationship('User')

    @property
    def formatted_size(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{round(self.file_size / 1024, 1)} KB"
        else:
            return f"{round(self.file_size / (1024 * 1024), 1)} MB"
