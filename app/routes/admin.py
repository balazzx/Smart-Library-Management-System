import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app import db
from app.models import User, Student, Librarian, Department, SystemSetting, AuditLog, SearchHistory, Book
from app.utils.decorators import admin_required
from app.ml.demand_predictor import predict_book_demand, get_smart_acquisition_insights
from app.utils.helpers import log_audit, get_setting

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    from app.models import BorrowTransaction
    total_users = User.query.count()
    total_students = Student.query.count()
    total_librarians = Librarian.query.count()
    total_books = Book.query.count()
    total_transactions = BorrowTransaction.query.count()

    recent_audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(15).all()
    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_students=total_students,
        total_librarians=total_librarians,
        total_books=total_books,
        total_transactions=total_transactions,
        recent_audits=recent_audits
    )


@admin_bp.route('/users')
@admin_required
def users():
    users_list = User.query.order_by(User.id.desc()).all()
    return render_template('admin/users.html', users=users_list)


@admin_bp.route('/users/toggle-status/<int:user_id>', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    log_audit('TOGGLE_USER_STATUS', 'User', user.id, f"User {user.username} active status set to {user.is_active}")
    flash(f"User '{user.username}' status updated.", 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        settings_map = {
            'MAX_BORROW_LIMIT': request.form.get('max_borrow_limit'),
            'BORROW_PERIOD_DAYS': request.form.get('borrow_period_days'),
            'GRACE_PERIOD_DAYS': request.form.get('grace_period_days'),
            'FINE_PER_DAY': request.form.get('fine_per_day'),
            'MAX_FINE': request.form.get('max_fine'),
            'CLAIM_PERIOD_HOURS': request.form.get('claim_period_hours'),
            'LIBRARY_NAME': request.form.get('library_name')
        }

        for key, val in settings_map.items():
            if val is not None:
                s = SystemSetting.query.filter_by(setting_key=key).first()
                if not s:
                    s = SystemSetting(setting_key=key, setting_value=str(val))
                    db.session.add(s)
                else:
                    s.setting_value = str(val)

        db.session.commit()
        log_audit('UPDATE_SETTINGS', 'SystemSetting', None, "Updated system operational parameters")
        flash('System settings updated successfully!', 'success')
        return redirect(url_for('admin.settings'))

    current_settings = {
        'MAX_BORROW_LIMIT': get_setting('MAX_BORROW_LIMIT', 5),
        'BORROW_PERIOD_DAYS': get_setting('BORROW_PERIOD_DAYS', 14),
        'GRACE_PERIOD_DAYS': get_setting('GRACE_PERIOD_DAYS', 2),
        'FINE_PER_DAY': get_setting('FINE_PER_DAY', 5.0),
        'MAX_FINE': get_setting('MAX_FINE', 500.0),
        'CLAIM_PERIOD_HOURS': get_setting('CLAIM_PERIOD_HOURS', 48),
        'LIBRARY_NAME': get_setting('LIBRARY_NAME', 'Smart Campus Central Library')
    }
    return render_template('admin/settings.html', settings=current_settings)


from app.ml.demand_predictor import predict_book_demand, get_smart_acquisition_insights, get_all_ml_predictions

@admin_bp.route('/ml-demand')
@admin_required
def ml_demand():
    predictions = get_all_ml_predictions(top_n=100)
    high_demand_count = sum(1 for p in predictions if p['demand_level'] == 'HIGH')
    return render_template('admin/ml_demand.html', predictions=predictions, high_demand_count=high_demand_count)


@admin_bp.route('/acquisition-insights')
@admin_required
def acquisition_insights():
    insights = get_smart_acquisition_insights()
    return render_template('admin/acquisition_insights.html', insights=insights)


@admin_bp.route('/search-history')
@admin_required
def search_history():
    histories = SearchHistory.query.order_by(SearchHistory.timestamp.desc()).limit(100).all()
    return render_template('admin/search_history.html', histories=histories)


@admin_bp.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'LIBRARIAN')
    name = request.form.get('name', '').strip()
    staff_id = request.form.get('staff_id', '').strip()

    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'warning')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(email=email).first():
        flash('Email already registered.', 'warning')
        return redirect(url_for('admin.users'))

    u = User(username=username, email=email, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.flush()

    if role == 'LIBRARIAN':
        s_id = staff_id or f"LIB-{u.id:04d}"
        lib = Librarian(user_id=u.id, staff_id=s_id, name=name or username)
        db.session.add(lib)

    db.session.commit()
    log_audit('CREATE_USER', 'User', u.id, f"Admin created user {username} with role {role}")
    flash(f"User account '{username}' ({role}) created successfully!", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/reset-password/<int:user_id>', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', 'Password@123')
    user.set_password(new_password)
    db.session.commit()
    log_audit('RESET_USER_PASSWORD', 'User', user.id, f"Admin reset password for user {user.username}")
    flash(f"Password for '{user.username}' reset successfully to default.", 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/profile', methods=['GET', 'POST'])
@admin_required
def profile():
    user = db.session.get(User, session['user_id'])
    librarian = user.librarian_profile

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        if email and email != user.email:
            existing = User.query.filter(User.email.ilike(email), User.id != user.id).first()
            if existing:
                flash('Email address is already in use by another user.', 'danger')
                return redirect(url_for('admin.profile'))
            user.email = email

        if librarian:
            librarian.phone = phone
        db.session.commit()
        log_audit('UPDATE_ADMIN_PROFILE', 'User', user.id, f"Admin {user.username} updated profile contact details")
        flash('Admin profile updated successfully!', 'success')
        return redirect(url_for('admin.profile'))

    recent_audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(15).all()
    return render_template('admin/profile.html', user=user, librarian=librarian, recent_audits=recent_audits)


@admin_bp.route('/email-center', methods=['GET', 'POST'])
@admin_required
def email_center():
    from app.models.system import EmailLog
    from app.utils.email_service import send_email
    from flask import current_app
    from datetime import datetime as _dt

    if request.method == 'POST':
        test_recipient = request.form.get('test_recipient', '').strip()
        test_subject = request.form.get('subject', 'KIOT Central Library SMTP Test Email').strip()
        test_body = request.form.get('body', 'This is a test notification email from KIOT Central Library Email Center.').strip()
        if test_recipient:
            success = send_email(
                recipient=test_recipient,
                subject=test_subject,
                body=test_body,
                email_type="TEST_EMAIL"
            )
            if success:
                flash(f"Test email sent successfully to {test_recipient}!", 'success')
            else:
                last_log = EmailLog.query.filter_by(recipient=test_recipient).order_by(EmailLog.id.desc()).first()
                err_msg = last_log.error_message if last_log and last_log.error_message else "Check SMTP credentials in your .env file."
                flash(f"Email sending failed: {err_msg}", 'danger')
            return redirect(url_for('admin.email_center'))

    mail_user = current_app.config.get('MAIL_USERNAME', '')
    mail_pass = current_app.config.get('MAIL_PASSWORD', '')
    mail_config = {
        'MAIL_SERVER':   current_app.config.get('MAIL_SERVER', 'smtp.gmail.com'),
        'MAIL_PORT':     current_app.config.get('MAIL_PORT', 587),
        'MAIL_USERNAME': mail_user,
        'MAIL_USE_TLS':  current_app.config.get('MAIL_USE_TLS', True),
    }
    smtp_ready = bool(mail_user and mail_pass)

    logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(100).all()
    return render_template(
        'admin/email_center.html',
        mail_config=mail_config,
        smtp_ready=smtp_ready,
        logs=logs,
        now=_dt.utcnow()
    )


@admin_bp.route('/data-quality')
@admin_required
def data_quality():
    from app.models import Student, Book, BookCopy, BorrowTransaction, Department, Fine, User
    from sqlalchemy import func

    # Diagnostic checks
    dup_roll_nos = db.session.query(Student.student_id, func.count(Student.id)).group_by(Student.student_id).having(func.count(Student.id) > 1).all()
    dup_reg_nos = db.session.query(Student.reg_no, func.count(Student.id)).filter(Student.reg_no != None).group_by(Student.reg_no).having(func.count(Student.id) > 1).all()
    dup_access_nos = db.session.query(BookCopy.copy_code, func.count(BookCopy.id)).group_by(BookCopy.copy_code).having(func.count(BookCopy.id) > 1).all()
    books_no_copies = Book.query.filter(~Book.copies.any()).all()
    orphan_copies = BookCopy.query.filter(~BookCopy.book.has()).all()
    invalid_dept_students = Student.query.filter(~Student.department.has()).all()

    quality_summary = {
        'duplicate_roll_nos': len(dup_roll_nos),
        'duplicate_reg_nos': len(dup_reg_nos),
        'duplicate_access_nos': len(dup_access_nos),
        'books_without_copies': len(books_no_copies),
        'orphan_copies': len(orphan_copies),
        'invalid_dept_students': len(invalid_dept_students),
        'total_students_checked': Student.query.count(),
        'total_books_checked': Book.query.count(),
        'total_copies_checked': BookCopy.query.count()
    }

    return render_template('admin/data_quality.html', summary=quality_summary)


@admin_bp.route('/data-management', methods=['GET', 'POST'])
@admin_required
def data_management():
    import os
    import re
    import openpyxl
    from app.models import Student, Book, BookCopy, BorrowTransaction, BookLocation, Fine

    datas_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Datas')
    final_files = [
        {'name': 'Students_Final.xlsx',             'desc': '66 KIOT Student Records (Authoritative)',       'key': 'students'},
        {'name': 'Books_Final.xlsx',                'desc': '500 Complete Book Catalog (Authoritative)',      'key': 'books'},
        {'name': 'Book_Copies_Final.xlsx',          'desc': '500 Physical Book Copies (Authoritative)',       'key': 'copies'},
        {'name': 'Library_Locations_Final.xlsx',    'desc': '360 Shelf Location Blocks & Racks',              'key': 'locations'},
        {'name': 'Borrow_Return_History_Final.xlsx','desc': '1527 Borrow & Return History Records',           'key': 'history'},
    ]
    for f in final_files:
        f['path'] = os.path.join(datas_dir, f['name'])
        f['exists'] = os.path.exists(f['path'])
        f['size_kb'] = round(os.path.getsize(f['path']) / 1024, 1) if f['exists'] else 0

    db_stats = {
        'students': Student.query.count(),
        'books': Book.query.count(),
        'copies': BookCopy.query.count(),
        'transactions': BorrowTransaction.query.count(),
        'locations': BookLocation.query.count(),
        'fines': Fine.query.count()
    }

    books_file = os.path.join(datas_dir, 'Books_Final.xlsx')
    isbn_values = []
    if os.path.exists(books_file):
        workbook = openpyxl.load_workbook(books_file, read_only=True, data_only=True)
        rows = workbook.active.iter_rows(min_row=2, values_only=True)
        headers = [cell.value for cell in workbook.active[1]]
        isbn_index = headers.index('ISBN')
        isbn_values = [str(row[isbn_index]).strip() for row in rows if row[isbn_index]]
        workbook.close()
    static_covers = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'book_covers')
    cover_files = {os.path.splitext(name)[0] for name in os.listdir(static_covers)} if os.path.exists(static_covers) else set()
    normalized_isbns = {re.sub(r'[^0-9Xx]', '', isbn) for isbn in isbn_values}
    report_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'reports', 'cover_mapping_report.json')
    download_report = {}
    if os.path.exists(report_path):
        with open(report_path, encoding='utf-8') as report_file:
            download_report = json.load(report_file)
    db_stats['cover_status'] = {
        'total_books': len(isbn_values),
        'covers_found': len(normalized_isbns & cover_files),
        'verified_covers': download_report.get('verified_covers', len(normalized_isbns & cover_files)),
        'local_covers': download_report.get('local_covers', len(normalized_isbns & cover_files)),
        'remote_covers': download_report.get('remote_covers', 0),
        'covers_missing': len(normalized_isbns - cover_files),
        'download_failed': download_report.get('failed', 0),
        'duplicate_isbn': len(isbn_values) - len(normalized_isbns),
        'unverified_covers': download_report.get('unverified', 0),
    }

    return render_template('admin/data_management.html', available_files=final_files, db_stats=db_stats)


@admin_bp.route('/data-management/preview/<key>')
@admin_required
def data_management_preview(key):
    import os, openpyxl
    file_map = {
        'students': 'Students_Final.xlsx',
        'books': 'Books_Final.xlsx',
        'copies': 'Book_Copies_Final.xlsx',
        'locations': 'Library_Locations_Final.xlsx',
        'history': 'Borrow_Return_History_Final.xlsx'
    }
    if key not in file_map:
        return jsonify({'error': 'Invalid key'}), 400
    
    filename = file_map[key]
    datas_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Datas')
    filepath = os.path.join(datas_dir, filename)

    if not os.path.exists(filepath):
        return jsonify({'error': f'File {filename} not found'}), 440

    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sheet = wb.active
        headers = [str(cell.value or '').strip() for cell in sheet[1]]
        rows = []
        for r in sheet.iter_rows(min_row=2, max_row=11, values_only=True):
            rows.append([str(v if v is not None else '') for v in r])
        total_rows = max(0, sheet.max_row - 1)
        wb.close()
        return jsonify({
            'success': True,
            'filename': filename,
            'total_rows': total_rows,
            'headers': headers,
            'rows': rows
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/data-management/validate/<key>')
@admin_required
def data_management_validate(key):
    import os, openpyxl
    file_map = {
        'students': 'Students_Final.xlsx',
        'books': 'Books_Final.xlsx',
        'copies': 'Book_Copies_Final.xlsx',
        'locations': 'Library_Locations_Final.xlsx',
        'history': 'Borrow_Return_History_Final.xlsx'
    }
    if key not in file_map:
        return jsonify({'error': 'Invalid dataset key'}), 400

    filename = file_map[key]
    datas_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Datas')
    filepath = os.path.join(datas_dir, filename)

    if not os.path.exists(filepath):
        return jsonify({'error': f'File {filename} not found'}), 404

    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sheet = wb.active
        headers = [str(cell.value or '').strip() for cell in sheet[1]]
        total_records = 0
        missing_required = 0
        duplicates = 0
        seen_keys = set()

        for r in sheet.iter_rows(min_row=2, values_only=True):
            if not any(r):
                continue
            total_records += 1
            primary_val = str(r[0] or '').strip()
            if not primary_val:
                missing_required += 1
            elif primary_val in seen_keys:
                duplicates += 1
            else:
                seen_keys.add(primary_val)

        wb.close()
        is_valid = (missing_required == 0 and duplicates == 0)
        return jsonify({
            'success': True,
            'filename': filename,
            'total_records': total_records,
            'missing_required': missing_required,
            'duplicates': duplicates,
            'status': 'VALID' if is_valid else 'WARNING',
            'headers': headers
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/data-management/reconcile')
@admin_required
def data_management_reconcile():
    import os, openpyxl
    from app.models import Student, Book, BookCopy, BorrowTransaction, BookLocation, Fine

    datas_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Datas')
    reconcile_targets = [
        ('Students', 'Students_Final.xlsx', Student.query.count()),
        ('Books', 'Books_Final.xlsx', Book.query.count()),
        ('Book Copies', 'Book_Copies_Final.xlsx', BookCopy.query.count()),
        ('Library Locations', 'Library_Locations_Final.xlsx', BookLocation.query.count()),
        ('Borrow Transactions', 'Borrow_Return_History_Final.xlsx', BorrowTransaction.query.count()),
    ]

    report = []
    for label, filename, db_count in reconcile_targets:
        filepath = os.path.join(datas_dir, filename)
        excel_count = 0
        if os.path.exists(filepath):
            wb = openpyxl.load_workbook(filepath, read_only=True)
            ws = wb.active
            for r in ws.iter_rows(min_row=2, values_only=True):
                if any(r):
                    excel_count += 1
            wb.close()
        diff = db_count - excel_count
        status = 'PASS' if (excel_count > 0 and diff == 0) else 'FAIL'
        report.append({
            'entity': label,
            'excel_records': excel_count,
            'database_records': db_count,
            'difference': diff,
            'status': status
        })

    return jsonify({'success': True, 'report': report})


@admin_bp.route('/data-management/execute-import', methods=['POST'])
@admin_required
def data_management_import():
    try:
        from import_kiot_data import run_import
        run_import()
        flash('Authoritative dataset import completed successfully. Timestamped database backup created.', 'success')
        return jsonify({'success': True, 'message': 'Import completed successfully.'})
    except Exception as e:
        flash(f'Import error: {str(e)}', 'danger')
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/system-health')
@admin_required
def system_health():
    import os
    from app.models import Student, Book, BookCopy, BorrowTransaction, BookLocation, Fine
    from datetime import datetime
    from sqlalchemy import text

    # Database check
    db_ok = False
    try:
        db.session.execute(text('SELECT 1'))
        db_ok = True
    except Exception:
        pass

    # Email config check
    mail_server = os.environ.get('MAIL_SERVER', '')
    mail_ok = bool(mail_server)

    # Dataset status
    datas_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Datas')
    required_files = ['Students_Final.xlsx', 'Books_Final.xlsx', 'Book_Copies_Final.xlsx',
                      'Borrow_Return_History_Final.xlsx', 'Library_Locations_Final.xlsx']
    dataset_status = []
    for fname in required_files:
        fpath = os.path.join(datas_dir, fname)
        exists = os.path.exists(fpath)
        dataset_status.append({'name': fname, 'exists': exists, 'size_kb': round(os.path.getsize(fpath)/1024, 1) if exists else 0})

    # DB stats
    db_stats = {
        'students': Student.query.count(),
        'books': Book.query.count(),
        'copies': BookCopy.query.count(),
        'transactions': BorrowTransaction.query.count(),
        'locations': BookLocation.query.count(),
        'unpaid_fines': Fine.query.filter_by(status='UNPAID').count(),
    }

    # Logo status
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'uploads', 'kiot_logo.jpg')
    logo_ok = os.path.exists(logo_path)

    return render_template('admin/system_health.html',
        db_ok=db_ok, mail_ok=mail_ok, logo_ok=logo_ok,
        dataset_status=dataset_status, db_stats=db_stats,
        mail_server=mail_server, now=datetime.utcnow())


@admin_bp.route('/backup', methods=['POST'])
@admin_required
def create_backup():
    import os, shutil
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'smart_library.db')
    if os.path.exists(db_path):
        backup_dir = os.path.join(os.path.dirname(db_path), 'database')
        os.makedirs(backup_dir, exist_ok=True)
        backup_name = f"smart_library_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.copy2(db_path, backup_path)
        size_kb = round(os.path.getsize(backup_path) / 1024, 1)
        log_audit('DB_BACKUP', 'System', None, f"Database backed up to {backup_name} ({size_kb} KB)")
        flash(f'Database backed up successfully: {backup_name} ({size_kb} KB)', 'success')
    else:
        flash('Database file not found.', 'danger')
    return redirect(url_for('admin.system_health'))

