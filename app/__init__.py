import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure required folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'covers'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'pdfs'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'qrcodes'), exist_ok=True)

    # Database fallback setup: Try connecting to MySQL if specified, fallback to SQLite if connection fails
    target_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if target_uri.startswith('mysql'):
        try:
            from sqlalchemy import create_engine
            test_engine = create_engine(target_uri, connect_args={'connect_timeout': 2})
            conn = test_engine.connect()
            conn.close()
            test_engine.dispose()
        except Exception as e:
            app.logger.warning(f"Failed to connect to primary MySQL DB ({target_uri}): {e}. Falling back to SQLite.")
            sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'smart_library.db')
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'

    db.init_app(app)

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.librarian import librarian_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.errors import errors_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(librarian_bp, url_prefix='/librarian')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(errors_bp)

    @app.context_processor
    def inject_global_vars():
        from flask import session
        from app.models.user import User
        from app.models.engagement import Notification
        
        unread_notifications_count = 0
        current_user_obj = None
        if 'user_id' in session:
            current_user_obj = db.session.get(User, session['user_id'])
            if current_user_obj:
                unread_notifications_count = Notification.query.filter_by(
                    user_id=current_user_obj.id, is_read=False
                ).count()
                
        return {
            'current_user': current_user_obj,
            'unread_notifications_count': unread_notifications_count,
            'app_name': 'KIOT CENTRAL LIBRARY'
        }

    return app
