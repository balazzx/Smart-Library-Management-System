from app import create_app, db
from app.utils.reminders import process_automated_reminders
from seed import seed_database

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        try:
            seed_database()
        except Exception as e:
            app.logger.warning(f"Auto-seeding check info: {e}")
            
        try:
            process_automated_reminders()
        except Exception as e:
            app.logger.warning(f"Background reminder engine initial check error: {e}")
            
    app.run(host='127.0.0.1', port=5000, debug=True)

