import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
parentdir = os.path.dirname(basedir)
load_dotenv(os.path.join(parentdir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'smart-library-capstone-secret-key-2026'
    
    # Database Configuration
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    DB_NAME = os.environ.get('DB_NAME', 'smart_library_db')
    
    # Check if custom MySQL DB environment is requested
    USE_MYSQL = os.environ.get('USE_MYSQL', 'true').lower() == 'true'
    
    if USE_MYSQL and DB_NAME:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(parentdir, 'smart_library.db')
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mail Config
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')

    # Upload & Report Directories
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    REPORT_FOLDER = os.path.join(parentdir, 'reports')
    
    # Default Business Rules
    DEFAULT_MAX_BORROW_LIMIT = 5
    DEFAULT_BORROW_PERIOD_DAYS = 14
    DEFAULT_GRACE_PERIOD_DAYS = 2
    DEFAULT_FINE_PER_DAY = 5.0
    DEFAULT_MAX_FINE = 500.0
    DEFAULT_CLAIM_PERIOD_HOURS = 48
