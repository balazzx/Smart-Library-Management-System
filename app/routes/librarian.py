import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app
from werkzeug.utils import secure_filename
from app import db
from app.models import (
    Book, BookCopy, Author, Category, Publisher, BookLocation, Student,
    BookRequest, BorrowTransaction, ReturnTransaction, Reservation,
    WaitingList, Fine, DigitalResource, Announcement, EmailLog, AuditLog, Department, User
)
from app.utils.decorators import librarian_required
from app.services.issue_service import approve_and_issue_book, direct_issue_book
from app.services.return_service import process_book_return
from app.services.fine_service import pay_fine, waive_fine
from app.services.qr_service import generate_book_qr, generate_copy_qr
from app.services.pdf_service import generate_inventory_pdf_report, generate_borrow_history_pdf
from app.analytics.analytics_engine import get_librarian_kpis, get_book_utilization_stats
from app.utils.helpers import log_audit

librarian_bp = Blueprint('librarian', __name__)

@librarian_bp.route('/dashboard')
@librarian_required
def dashboard():
    kpis = get_librarian_kpis()
    recent_requests = BookRequest.query.filter_by(status='PENDING').order_by(BookRequest.request_date.desc()).limit(5).all()
    recent_issues = BorrowTransaction.query.order_by(BorrowTransaction.issue_date.desc()).limit(5).all()
    return render_template('librarian/dashboard.html', kpis=kpis, recent_requests=recent_requests, recent_issues=recent_issues)


@librarian_bp.route('/books')
@librarian_required
def books():
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', type=int)
    page = request.args.get('page', 1, type=int)

    query = Book.query
    if q:
        query = query.filter((Book.title.like(f"%{q}%")) | (Book.isbn.like(f"%{q}%")))
    if category_id:
        query = query.filter_by(category_id=category_id)

    pagination = query.order_by(Book.id.desc()).paginate(page=page, per_page=15, error_out=False)
    categories = Category.query.all()
    return render_template('librarian/books.html', books=pagination.items, pagination=pagination, categories=categories, q=q)


@librarian_bp.route('/books/add', methods=['GET', 'POST'])
@librarian_required
def add_book():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        isbn = request.form.get('isbn', '').strip()
        author_id = request.form.get('author_id', type=int)
        category_id = request.form.get('category_id', type=int)
        publisher_id = request.form.get('publisher_id', type=int)
        pub_year = request.form.get('pub_year', type=int)
        language = request.form.get('language', 'English')
        description = request.form.get('description', '').strip()
        initial_copies = request.form.get('initial_copies', 1, type=int)
        location_id = request.form.get('location_id', type=int)

        if Book.query.filter_by(isbn=isbn).first():
            flash('Error: A book with this ISBN already exists.', 'danger')
            return redirect(url_for('librarian.add_book'))

        # Handle Cover Image Upload
        cover_filename = 'default_cover.jpg'
        cover_file = request.files.get('cover_image')
        if cover_file and cover_file.filename:
            filename = secure_filename(cover_file.filename)
            save_name = f"cover_{int(datetime.utcnow().timestamp())}_{filename}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'covers', save_name)
            cover_file.save(save_path)
            cover_filename = f"uploads/covers/{save_name}"

        new_book = Book(
            title=title,
            isbn=isbn,
            author_id=author_id,
            category_id=category_id,
            publisher_id=publisher_id,
            pub_year=pub_year,
            language=language,
            description=description,
            cover_image=cover_filename,
            location_id=location_id
        )
        db.session.add(new_book)
        db.session.flush()

        # Add initial physical copies
        for i in range(1, initial_copies + 1):
            copy_code = f"BC-{new_book.id:04d}-{i:02d}"
            copy = BookCopy(copy_code=copy_code, book_id=new_book.id, status='AVAILABLE', location_id=location_id)
            db.session.add(copy)

        db.session.commit()
        log_audit('ADD_BOOK', 'Book', new_book.id, f"Added book '{title}' with {initial_copies} copies.")
        flash(f"Book '{title}' added successfully with {initial_copies} physical copies!", 'success')
        return redirect(url_for('librarian.books'))

    authors = Author.query.all()
    categories = Category.query.all()
    publishers = Publisher.query.all()
    locations = BookLocation.query.all()
    return render_template('librarian/add_book.html', authors=authors, categories=categories, publishers=publishers, locations=locations)


@librarian_bp.route('/requests')
@librarian_required
def requests_list():
    status = request.args.get('status', 'PENDING')
    reqs = BookRequest.query.filter_by(status=status).order_by(BookRequest.request_date.desc()).all()
    return render_template('librarian/requests.html', requests=reqs, current_status=status)


@librarian_bp.route('/requests/approve/<int:req_id>', methods=['POST'])
@librarian_required
def approve_request(req_id):
    reviewer_id = session['user_id']
    success, msg = approve_and_issue_book(req_id, reviewer_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'warning')
    return redirect(url_for('librarian.requests_list'))


@librarian_bp.route('/requests/reject/<int:req_id>', methods=['POST'])
@librarian_required
def reject_request(req_id):
    req = BookRequest.query.get_or_404(req_id)
    req.status = 'REJECTED'
    req.reviewer_id = session['user_id']
    req.review_date = datetime.utcnow()
    req.notes = request.form.get('notes', 'Request rejected by librarian.')
    db.session.commit()

    log_audit('REJECT_REQUEST', 'BookRequest', req.id, f"Rejected request for book ID {req.book_id}")
    flash('Request rejected.', 'info')
    return redirect(url_for('librarian.requests_list'))


@librarian_bp.route('/issue', methods=['GET', 'POST'])
@librarian_required
def issue_book():
    if request.method == 'POST':
        student_id = request.form.get('student_id', type=int)
        copy_id = request.form.get('copy_id', type=int)
        issuer_id = session['user_id']

        success, msg = direct_issue_book(student_id, copy_id, issuer_id)
        if success:
            flash(msg, 'success')
            return redirect(url_for('librarian.dashboard'))
        else:
            flash(msg, 'danger')

    students = Student.query.all()
    available_copies = BookCopy.query.filter_by(status='AVAILABLE').all()
    return render_template('librarian/issue_book.html', students=students, copies=available_copies)


@librarian_bp.route('/return', methods=['GET', 'POST'])
@librarian_required
def return_book():
    if request.method == 'POST':
        transaction_id = request.form.get('transaction_id', type=int)
        condition = request.form.get('condition', 'GOOD')
        notes = request.form.get('notes', '').strip()

        success, msg = process_book_return(transaction_id, condition=condition, notes=notes)
        if success:
            flash(msg, 'success')
            return redirect(url_for('librarian.dashboard'))
        else:
            flash(msg, 'danger')

    active_transactions = BorrowTransaction.query.filter_by(status='ISSUED').order_by(BorrowTransaction.due_date.asc()).all()
    return render_template('librarian/return_book.html', transactions=active_transactions)


@librarian_bp.route('/fines')
@librarian_required
def fines_list():
    fines = Fine.query.order_by(Fine.created_at.desc()).all()
    return render_template('librarian/fines.html', fines=fines)


@librarian_bp.route('/fines/settle/<int:fine_id>', methods=['POST'])
@librarian_required
def settle_fine_librarian(fine_id):
    payment_method = request.form.get('payment_method', 'Cash')
    success, msg = pay_fine(fine_id, payment_method=payment_method)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('librarian.fines_list'))


@librarian_bp.route('/digital-resources', methods=['GET', 'POST'])
@librarian_required
def digital_resources():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', type=int)
        dept_id = request.form.get('target_department_id', type=int)

        file = request.files.get('file')
        if file and file.filename:
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'pdf'
            save_name = f"doc_{int(datetime.utcnow().timestamp())}_{filename}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'pdfs', save_name)
            file.save(save_path)
            file_size = os.path.getsize(save_path)

            res = DigitalResource(
                title=title,
                author=author,
                description=description,
                category_id=category_id if category_id else None,
                file_path=f"uploads/pdfs/{save_name}",
                file_type=ext.upper(),
                file_size=file_size,
                target_department_id=dept_id if dept_id else None,
                uploaded_by=session['user_id']
            )
            db.session.add(res)
            db.session.commit()
            log_audit('UPLOAD_DIGITAL_RESOURCE', 'DigitalResource', res.id, f"Uploaded '{title}'")
            flash(f"Digital resource '{title}' uploaded successfully!", 'success')
            return redirect(url_for('librarian.digital_resources'))

    resources = DigitalResource.query.order_by(DigitalResource.upload_date.desc()).all()
    categories = Category.query.all()
    departments = Department.query.all()
    return render_template('librarian/digital_resources.html', resources=resources, categories=categories, departments=departments)


@librarian_bp.route('/announcements', methods=['GET', 'POST'])
@librarian_required
def announcements():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        priority = request.form.get('priority', 'MEDIUM')
        target_role = request.form.get('target_role', 'ALL')
        dept_id = request.form.get('target_department_id', type=int)
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()

        ann = Announcement(
            title=title,
            message=message,
            priority=priority,
            target_role=target_role,
            target_department_id=dept_id if dept_id else None,
            start_date=start_date,
            end_date=end_date,
            created_by=session['user_id']
        )
        db.session.add(ann)
        db.session.commit()
        log_audit('CREATE_ANNOUNCEMENT', 'Announcement', ann.id, f"Created announcement '{title}'")
        flash('Announcement published successfully.', 'success')
        return redirect(url_for('librarian.announcements'))

    items = Announcement.query.order_by(Announcement.created_at.desc()).all()
    departments = Department.query.all()
    return render_template('librarian/announcements.html', announcements=items, departments=departments)


@librarian_bp.route('/reports')
@librarian_required
def reports():
    return render_template('librarian/reports.html')


@librarian_bp.route('/reports/export/<report_type>/<fmt>')
@librarian_required
def export_report(report_type, fmt):
    from app.services.pdf_service import generate_generic_pdf_report, generate_generic_excel_report
    from app.models import Book, BookCopy, BorrowTransaction, Department, Student, Fine, BookLocation, Category, SearchHistory, AuditLog, Wishlist, BookRequest
    from app.ml.demand_predictor import get_all_ml_predictions
    from sqlalchemy import func

    headers = []
    rows = []
    title = ""

    if report_type == 'inventory':
        title = "Catalog Books & Inventory Master Audit"
        headers = ["ISBN", "Book Title", "Author", "Category", "Total Copies", "Available Copies", "Location"]
        for b in Book.query.all():
            rows.append([b.isbn, b.title, b.author.name if b.author else '', b.category.name if b.category else '', b.total_copies_count, b.available_copies_count, b.location.display_name if b.location else 'Unassigned'])

    elif report_type == 'circulation':
        title = "Active Borrowings & Circulation Status"
        headers = ["Copy Code", "Book Title", "Borrower Name", "Roll No", "Issue Date", "Due Date", "Status"]
        for tx in BorrowTransaction.query.filter_by(status='ISSUED').all():
            rows.append([
                tx.copy.copy_code if tx.copy else '',
                tx.copy.book.title if tx.copy and tx.copy.book else '',
                tx.student.name if tx.student else '',
                tx.student.student_id if tx.student else '',
                tx.issue_date.strftime('%Y-%m-%d'),
                tx.due_date.strftime('%Y-%m-%d'),
                tx.status
            ])

    elif report_type == 'overdue':
        title = "Overdue Loans & Fine Audit"
        headers = ["Student Name", "Roll No", "Book Title", "Access No", "Due Date", "Fine Amount", "Fine Status"]
        for tx in BorrowTransaction.query.filter(BorrowTransaction.status == 'ISSUED', BorrowTransaction.due_date < datetime.utcnow()).all():
            f = Fine.query.filter_by(transaction_id=tx.id).first()
            rows.append([
                tx.student.name if tx.student else '',
                tx.student.student_id if tx.student else '',
                tx.copy.book.title if tx.copy and tx.copy.book else '',
                tx.copy.copy_code if tx.copy else '',
                tx.due_date.strftime('%Y-%m-%d'),
                f"₹{tx.fine_amount:.2f}",
                f.status if f else 'PENDING'
            ])

    elif report_type == 'department':
        title = "Department-Wise Student Borrowing Distribution"
        headers = ["Dept Code", "Department Name", "Registered Students", "Active Borrows", "Total Fines (₹)"]
        for dept in Department.query.all():
            st_count = Student.query.filter_by(department_id=dept.id).count()
            active_tx = BorrowTransaction.query.join(Student).filter(Student.department_id == dept.id, BorrowTransaction.status == 'ISSUED').count()
            fines_sum = db.session.query(func.sum(Fine.amount)).join(Student, Fine.student_id == Student.id).filter(Student.department_id == dept.id).scalar() or 0.0
            rows.append([dept.code, dept.name, st_count, active_tx, f"₹{fines_sum:.2f}"])

    elif report_type == 'copy_condition':
        title = "Physical Book Copies Condition Audit"
        headers = ["Access No", "Book Title", "ISBN", "Condition Status", "Availability Status", "Location"]
        for copy in BookCopy.query.all():
            rows.append([
                copy.copy_code,
                copy.book.title if copy.book else '',
                copy.book.isbn if copy.book else '',
                copy.condition_status,
                copy.status,
                copy.location.display_name if copy.location else (copy.book.location.display_name if copy.book and copy.book.location else 'Main Stacks')
            ])

    elif report_type == 'locations':
        title = "Shelf Location & Navigation Mapping Hierarchy"
        headers = ["ID", "Block", "Floor", "Section", "Rack", "Shelf", "Position", "Full Location Display"]
        for loc in BookLocation.query.all():
            rows.append([loc.id, loc.block, loc.floor, loc.section, loc.rack, loc.shelf, loc.position, loc.display_name])

    elif report_type == 'categories':
        title = "Category & Subject Catalog Distribution"
        headers = ["Category ID", "Category Name", "Total Titles", "Total Physical Copies"]
        for cat in Category.query.all():
            titles_count = Book.query.filter_by(category_id=cat.id).count()
            copies_count = BookCopy.query.join(Book).filter(Book.category_id == cat.id).count()
            rows.append([cat.id, cat.name, titles_count, copies_count])

    elif report_type == 'students':
        title = "Student Digital ID & Eligibility Master Audit"
        headers = ["Roll No", "Reg No", "Student Name", "Department", "Library Card No", "Max Borrow Limit", "Active Borrows"]
        for st in Student.query.all():
            active_b = BorrowTransaction.query.filter_by(student_id=st.id, status='ISSUED').count()
            rows.append([st.student_id, st.reg_no or '', st.name, st.department.code if st.department else '', st.library_card_number, st.max_borrow_limit, active_b])

    elif report_type == 'popular':
        title = "Most Popular & High Circulation Titles"
        headers = ["ISBN", "Book Title", "Author", "Category", "Total Borrows", "Available Stock"]
        popular_query = db.session.query(Book, func.count(BorrowTransaction.id).label('tx_cnt'))\
            .join(BookCopy, Book.id == BookCopy.book_id)\
            .join(BorrowTransaction, BookCopy.id == BorrowTransaction.copy_id)\
            .group_by(Book.id).order_by(func.count(BorrowTransaction.id).desc()).limit(50).all()
        for b, cnt in popular_query:
            rows.append([b.isbn, b.title, b.author.name if b.author else '', b.category.name if b.category else '', cnt, b.available_copies_count])

    elif report_type == 'ml_demand':
        title = "Machine Learning Book Demand Predictions"
        headers = ["ISBN", "Book Title", "Category", "Predicted Monthly Demand", "Demand Level", "Historical Vol", "Model"]
        preds = get_all_ml_predictions(top_n=100)
        for p in preds:
            rows.append([p.get('isbn',''), p['book_title'], p.get('category_name',''), f"{p['predicted_demand']} Req/mo", p['demand_level'], p['historical_total'], p['model_type']])

    elif report_type == 'wishlist':
        title = "Wishlist & Unfulfilled Book Requests Report"
        headers = ["Book Title", "ISBN", "Category", "Wishlist Count", "Pending Requests", "Available Copies"]
        for b in Book.query.all():
            w_cnt = Wishlist.query.filter_by(book_id=b.id).count()
            req_cnt = BookRequest.query.filter_by(book_id=b.id, status='PENDING').count()
            if w_cnt > 0 or req_cnt > 0:
                rows.append([b.title, b.isbn, b.category.name if b.category else '', w_cnt, req_cnt, b.available_copies_count])

    elif report_type == 'audit_logs':
        title = "System Audit Logs & Operational Activity"
        headers = ["Timestamp", "User ID", "Action", "Entity", "Description"]
        for log in AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(200).all():
            rows.append([log.timestamp.strftime('%Y-%m-%d %H:%M:%S'), log.user_id, log.action, log.entity or '', log.description])

    elif report_type == 'master':
        title = "KIOT Central Library Master Database Export"
        headers = ["Type", "Identifier", "Main Detail", "Secondary Detail", "Status/Count"]
        for st in Student.query.all():
            rows.append(["STUDENT", st.student_id, st.name, st.department.name if st.department else '', f"Limit: {st.max_borrow_limit}"])
        for b in Book.query.all():
            rows.append(["BOOK", b.isbn, b.title, b.author.name if b.author else '', f"Copies: {b.available_copies_count}/{b.total_copies_count}"])

    else:
        flash("Invalid report type specified.", "warning")
        return redirect(url_for('librarian.reports'))

    fname = f"KIOT_Report_{report_type}_{datetime.now().strftime('%Y%m%d')}"
    if fmt == 'pdf':
        file_path = generate_generic_pdf_report(title, headers, rows, output_filename=f"{fname}.pdf")
        return send_file(file_path, as_attachment=True, download_name=f"{fname}.pdf")
    else:
        file_path = generate_generic_excel_report(title, headers, rows, output_filename=f"{fname}.xlsx")
        return send_file(file_path, as_attachment=True, download_name=f"{fname}.xlsx")


@librarian_bp.route('/email-logs')
@librarian_required
def email_logs():
    logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(100).all()
    return render_template('librarian/email_logs.html', logs=logs)


@librarian_bp.route('/audit-logs')
@librarian_required
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template('librarian/audit_logs.html', logs=logs)


@librarian_bp.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
@librarian_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        book.title = request.form.get('title', '').strip()
        book.isbn = request.form.get('isbn', '').strip()
        book.author_id = request.form.get('author_id', type=int)
        book.category_id = request.form.get('category_id', type=int)
        book.publisher_id = request.form.get('publisher_id', type=int)
        book.pub_year = request.form.get('pub_year', type=int)
        book.language = request.form.get('language', 'English')
        book.description = request.form.get('description', '').strip()
        book.location_id = request.form.get('location_id', type=int)

        cover_file = request.files.get('cover_image')
        if cover_file and cover_file.filename:
            filename = secure_filename(cover_file.filename)
            save_name = f"cover_{int(datetime.utcnow().timestamp())}_{filename}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'covers', save_name)
            cover_file.save(save_path)
            book.cover_image = f"uploads/covers/{save_name}"

        db.session.commit()
        log_audit('EDIT_BOOK', 'Book', book.id, f"Updated details for book '{book.title}'")
        flash(f"Book '{book.title}' updated successfully!", 'success')
        return redirect(url_for('librarian.books'))

    authors = Author.query.all()
    categories = Category.query.all()
    publishers = Publisher.query.all()
    locations = BookLocation.query.all()
    return render_template('librarian/edit_book.html', book=book, authors=authors, categories=categories, publishers=publishers, locations=locations)


@librarian_bp.route('/books/copies/<int:book_id>', methods=['GET', 'POST'])
@librarian_required
def book_copies(book_id):
    book = Book.query.get_or_404(book_id)
    if request.method == 'POST':
        condition = request.form.get('condition_status', 'EXCELLENT')
        num_copies = request.form.get('num_copies', 1, type=int)
        current_count = book.copies.count()

        for i in range(1, num_copies + 1):
            copy_code = f"BC-{book.id:04d}-{current_count + i:02d}"
            c = BookCopy(copy_code=copy_code, book_id=book.id, condition_status=condition, status='AVAILABLE', location_id=book.location_id)
            db.session.add(c)

        db.session.commit()
        log_audit('ADD_BOOK_COPIES', 'Book', book.id, f"Added {num_copies} copies for '{book.title}'")
        flash(f"Added {num_copies} new physical copies for '{book.title}'.", 'success')
        return redirect(url_for('librarian.book_copies', book_id=book.id))

    copies = BookCopy.query.filter_by(book_id=book.id).order_by(BookCopy.id.asc()).all()
    return render_template('librarian/book_copies.html', book=book, copies=copies)


@librarian_bp.route('/copies/status/<int:copy_id>', methods=['POST'])
@librarian_required
def update_copy_status(copy_id):
    copy = BookCopy.query.get_or_404(copy_id)
    status = request.form.get('status')
    condition = request.form.get('condition_status')

    if status:
        copy.status = status
    if condition:
        copy.condition_status = condition

    db.session.commit()
    log_audit('UPDATE_COPY_STATUS', 'BookCopy', copy.id, f"Updated copy {copy.copy_code} status to {copy.status}")
    flash(f"Copy {copy.copy_code} status updated.", 'info')
    return redirect(url_for('librarian.book_copies', book_id=copy.book_id))


@librarian_bp.route('/fines/waive/<int:fine_id>', methods=['POST'])
@librarian_required
def waive_fine_librarian(fine_id):
    success, msg = waive_fine(fine_id, session['user_id'], reason=request.form.get('reason', 'Librarian Waiver'))
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('librarian.fines_list'))


@librarian_bp.route('/authors', methods=['GET', 'POST'])
@librarian_required
def authors():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        bio = request.form.get('bio', '').strip()
        if name:
            auth = Author(name=name, bio=bio)
            db.session.add(auth)
            db.session.commit()
            flash(f"Author '{name}' added successfully!", 'success')
            return redirect(url_for('librarian.authors'))

    authors_list = Author.query.order_by(Author.name.asc()).all()
    return render_template('librarian/authors.html', authors=authors_list)


@librarian_bp.route('/categories', methods=['GET', 'POST'])
@librarian_required
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        if name:
            if Category.query.filter_by(name=name).first():
                flash('Category with this name already exists.', 'warning')
            else:
                cat = Category(name=name, description=description)
                db.session.add(cat)
                db.session.commit()
                flash(f"Category '{name}' added successfully!", 'success')
            return redirect(url_for('librarian.categories'))

    categories_list = Category.query.order_by(Category.name.asc()).all()
    return render_template('librarian/categories.html', categories=categories_list)


@librarian_bp.route('/publishers', methods=['GET', 'POST'])
@librarian_required
def publishers():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            pub = Publisher(name=name)
            db.session.add(pub)
            db.session.commit()
            flash(f"Publisher '{name}' added successfully!", 'success')
            return redirect(url_for('librarian.publishers'))

    publishers_list = Publisher.query.order_by(Publisher.name.asc()).all()
    return render_template('librarian/publishers.html', publishers=publishers_list)


@librarian_bp.route('/locations', methods=['GET', 'POST'])
@librarian_required
def locations():
    if request.method == 'POST':
        block = request.form.get('block', '').strip()
        floor = request.form.get('floor', '').strip()
        section = request.form.get('section', '').strip()
        rack = request.form.get('rack', '').strip()
        shelf = request.form.get('shelf', '').strip()
        position = request.form.get('position', '').strip()

        if block and floor and section:
            loc = BookLocation(block=block, floor=floor, section=section, rack=rack, shelf=shelf, position=position)
            db.session.add(loc)
            db.session.commit()
            flash('Shelf location added successfully!', 'success')
            return redirect(url_for('librarian.locations'))

    locations_list = BookLocation.query.order_by(BookLocation.block.asc()).all()
    return render_template('librarian/locations.html', locations=locations_list)


@librarian_bp.route('/reports/inventory/csv')
@librarian_required
def export_inventory_csv():
    import csv
    from io import StringIO
    from flask import Response

    books = Book.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'ISBN', 'Title', 'Author', 'Category', 'Publisher', 'Publication Year', 'Total Copies', 'Available Copies', 'Location'])

    for b in books:
        loc = b.location.display_name if b.location else 'Unassigned'
        cw.writerow([
            b.id, b.isbn, b.title,
            b.author.name if b.author else '',
            b.category.name if b.category else '',
            b.publisher.name if b.publisher else '',
            b.pub_year, b.total_copies_count, b.available_copies_count, loc
        ])

    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Smart_Library_Inventory.csv"})


@librarian_bp.route('/reports/borrow-history/<int:student_id>/pdf')
@librarian_required
def download_student_borrow_pdf(student_id):
    student = Student.query.get_or_404(student_id)
    txs = BorrowTransaction.query.filter_by(student_id=student.id).order_by(BorrowTransaction.issue_date.desc()).all()
    pdf_path = generate_borrow_history_pdf(txs, student.name)
    return send_file(pdf_path, as_attachment=True, download_name=f"Borrowing_Statement_{student.student_id}.pdf")


@librarian_bp.route('/profile', methods=['GET', 'POST'])
@librarian_required
def profile():
    user = db.session.get(User, session['user_id'])
    librarian = user.librarian_profile

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()

        if email and email != user.email:
            existing = User.query.filter(User.email.ilike(email), User.id != user.id).first()
            if existing:
                flash('This email address is already in use.', 'danger')
                return redirect(url_for('librarian.profile'))
            user.email = email

        if librarian:
            librarian.phone = phone
        db.session.commit()
        log_audit('UPDATE_PROFILE', 'Librarian', user.id, f"Librarian {user.username} updated profile contact info")
        flash('Librarian profile updated successfully!', 'success')
        return redirect(url_for('librarian.profile'))

    issued_count = BorrowTransaction.query.count()
    returned_count = BorrowTransaction.query.filter_by(status='RETURNED').count()
    overdue_count = BorrowTransaction.query.filter(BorrowTransaction.status == 'ISSUED', BorrowTransaction.due_date < datetime.utcnow()).count()
    fines_count = Fine.query.filter_by(status='PAID').count()
    recent_logs = AuditLog.query.filter_by(user_id=user.id).order_by(AuditLog.timestamp.desc()).limit(10).all()

    return render_template(
        'librarian/profile.html',
        user=user,
        librarian=librarian,
        issued_count=issued_count,
        returned_count=returned_count,
        overdue_count=overdue_count,
        fines_count=fines_count,
        recent_logs=recent_logs
    )



# ─────────────────────────────────────────────────────────────────────────────
# COVER MANAGEMENT — authorized librarian/admin only
# All routes protected by @librarian_required (backend, not just UI).
# ─────────────────────────────────────────────────────────────────────────────

@librarian_bp.route('/covers')
@librarian_required
def cover_management():
    """Main cover-management dashboard: view all books and their cover status."""
    from app.services.cover_service import normalise_isbn, resolve_cover_path, _unmatched_dir

    q = request.args.get('q', '').strip()
    filter_status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)

    book_query = Book.query
    if q:
        book_query = book_query.filter(
            (Book.title.ilike(f'%{q}%')) |
            (Book.isbn.ilike(f'%{q}%')) |
            Book.author.has(Author.name.ilike(f'%{q}%'))
        )

    all_books = book_query.order_by(Book.title.asc()).all()

    book_entries = []
    for b in all_books:
        clean_isbn = normalise_isbn(b.isbn or '')
        cover_rel = resolve_cover_path(clean_isbn)
        has_cover = cover_rel != 'default_cover.jpg'
        book_entries.append({
            'book': b,
            'isbn': clean_isbn,
            'cover_rel': cover_rel,
            'has_cover': has_cover,
            'status': 'COVERED' if has_cover else 'MISSING',
        })

    if filter_status == 'missing':
        book_entries = [e for e in book_entries if not e['has_cover']]
    elif filter_status == 'covered':
        book_entries = [e for e in book_entries if e['has_cover']]

    total = len(book_entries)
    per_page = 20
    start = (page - 1) * per_page
    page_entries = book_entries[start:start + per_page]
    total_pages = max(1, (total + per_page - 1) // per_page)

    udir = _unmatched_dir()
    unmatched_files = []
    if os.path.isdir(udir):
        unmatched_files = sorted([
            f for f in os.listdir(udir)
            if os.path.isfile(os.path.join(udir, f))
        ])

    covered_count = sum(1 for e in book_entries if e['has_cover'])
    missing_count = total - covered_count

    return render_template(
        'librarian/covers.html',
        book_entries=page_entries,
        page=page,
        total_pages=total_pages,
        total=total,
        covered_count=covered_count,
        missing_count=missing_count,
        unmatched_files=unmatched_files,
        q=q,
        filter_status=filter_status,
    )


@librarian_bp.route('/covers/upload/<int:book_id>', methods=['POST'])
@librarian_required
def upload_cover(book_id):
    """Upload or replace a cover image for a specific book."""
    from app.services.cover_service import save_cover_for_isbn

    book = Book.query.get_or_404(book_id)
    cover_file = request.files.get('cover_image')

    success, msg, rel_path = save_cover_for_isbn(book.isbn, cover_file)
    if success:
        book.cover_image = rel_path
        db.session.commit()
        log_audit('UPLOAD_COVER', 'Book', book.id,
                  f"Cover uploaded for '{book.title}' (ISBN {book.isbn})")
        flash(f"Cover uploaded successfully for '{book.title}'.", 'success')
    else:
        flash(f"Cover upload failed: {msg}", 'danger')

    return redirect(url_for('librarian.cover_management', q=request.form.get('q', '')))


@librarian_bp.route('/covers/delete/<int:book_id>', methods=['POST'])
@librarian_required
def delete_cover(book_id):
    """Remove the cover image for a specific book."""
    from app.services.cover_service import delete_cover_for_isbn

    book = Book.query.get_or_404(book_id)
    success, msg = delete_cover_for_isbn(book.isbn)

    if success:
        book.cover_image = 'default_cover.jpg'
        db.session.commit()
        log_audit('DELETE_COVER', 'Book', book.id,
                  f"Cover removed for '{book.title}' (ISBN {book.isbn})")
        flash(f"Cover removed for '{book.title}'. {msg}", 'info')
    else:
        flash(f"No cover to remove: {msg}", 'warning')

    return redirect(url_for('librarian.cover_management', q=request.form.get('q', '')))


@librarian_bp.route('/covers/zip-upload', methods=['GET', 'POST'])
@librarian_required
def zip_cover_upload():
    """Bulk cover upload via ZIP file."""
    from app.services.cover_service import process_cover_zip, normalise_isbn

    if request.method == 'POST':
        zip_file = request.files.get('cover_zip')
        if not zip_file or not zip_file.filename:
            flash('No ZIP file provided.', 'warning')
            return redirect(url_for('librarian.zip_cover_upload'))

        if not zip_file.filename.lower().endswith('.zip'):
            flash('Uploaded file must be a .zip archive.', 'danger')
            return redirect(url_for('librarian.zip_cover_upload'))

        zip_data = zip_file.read()
        catalog_isbns = {normalise_isbn(b.isbn) for b in Book.query.all() if b.isbn}
        report = process_cover_zip(zip_data, catalog_isbns)

        for m in report.get('matched', []):
            isbn = m.get('isbn')
            if isbn:
                b = Book.query.filter_by(isbn=isbn).first()
                if b:
                    ext = os.path.splitext(m.get('file', 'x.jpg'))[1].lower() or '.jpg'
                    b.cover_image = f"book_covers/{isbn}{ext}"
        db.session.commit()

        log_audit('ZIP_COVER_UPLOAD', 'CoverManagement', 0,
                  f"ZIP upload: {len(report['matched'])} matched, "
                  f"{len(report['unmatched'])} unmatched, "
                  f"{len(report['invalid'])} invalid")

        flash(
            f"ZIP processed: {len(report['matched'])} covers matched, "
            f"{len(report['unmatched'])} unmatched (saved for manual review), "
            f"{len(report['invalid'])} invalid files.",
            'success' if report['matched'] else 'warning'
        )
        return render_template('librarian/zip_cover_report.html', report=report)

    return render_template('librarian/zip_cover_upload.html')


@librarian_bp.route('/covers/manual-map', methods=['POST'])
@librarian_required
def manual_cover_map():
    """Manually assign an unmatched image file to a specific book ISBN."""
    from app.services.cover_service import (
        normalise_isbn, validate_image_bytes,
        _unmatched_dir, _covers_dir, _SUPPORTED_EXTENSIONS
    )
    import shutil as _shutil

    target_isbn = normalise_isbn(request.form.get('isbn', ''))
    unmatched_filename = request.form.get('filename', '').strip()

    if not target_isbn:
        flash('Invalid or empty ISBN provided.', 'danger')
        return redirect(url_for('librarian.cover_management'))

    if not unmatched_filename:
        flash('No filename specified.', 'danger')
        return redirect(url_for('librarian.cover_management'))

    safe_name = os.path.basename(secure_filename(unmatched_filename))
    src = os.path.join(_unmatched_dir(), safe_name)
    if not os.path.isfile(src):
        flash(f"File '{safe_name}' not found in unmatched folder.", 'warning')
        return redirect(url_for('librarian.cover_management'))

    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        flash(f"Unsupported file extension '{ext}'.", 'danger')
        return redirect(url_for('librarian.cover_management'))

    with open(src, 'rb') as f:
        data = f.read()
    ok, reason = validate_image_bytes(data, safe_name)
    if not ok:
        flash(f"Image validation failed: {reason}", 'danger')
        return redirect(url_for('librarian.cover_management'))

    book = Book.query.filter_by(isbn=target_isbn).first()
    if not book:
        flash(f"No book found with ISBN {target_isbn}.", 'danger')
        return redirect(url_for('librarian.cover_management'))

    covers = _covers_dir()
    for old_ext in _SUPPORTED_EXTENSIONS:
        old = os.path.join(covers, f"{target_isbn}{old_ext}")
        if os.path.isfile(old):
            os.remove(old)

    dest = os.path.join(covers, f"{target_isbn}{ext}")
    _shutil.move(src, dest)

    book.cover_image = f"book_covers/{target_isbn}{ext}"
    db.session.commit()

    log_audit('MANUAL_COVER_MAP', 'Book', book.id,
              f"Manually mapped '{safe_name}' -> ISBN {target_isbn} for '{book.title}'")
    flash(f"'{safe_name}' mapped to '{book.title}' (ISBN {target_isbn}).", 'success')
    return redirect(url_for('librarian.cover_management'))


@librarian_bp.route('/covers/reconciliation')
@librarian_required
def cover_reconciliation():
    """Generate a live cover reconciliation report."""
    from app.services.cover_service import normalise_isbn, generate_cover_reconciliation

    catalog_isbns = {normalise_isbn(b.isbn) for b in Book.query.all() if b.isbn}
    report = generate_cover_reconciliation(catalog_isbns)
    return render_template('librarian/cover_reconciliation.html', report=report)


@librarian_bp.route('/locations/reconciliation')
@librarian_required
def location_reconciliation():
    from app.models.book import BookLocation, BookCopy
    loc_master = BookLocation.query.all()
    master_keys = {(l.block, str(l.floor), l.section, str(l.rack), str(l.shelf), str(l.position)) for l in loc_master}
    copies = BookCopy.query.all()
    items = []
    matched_count = 0
    unmatched_count = 0
    for cp in copies:
        loc = cp.location
        if loc:
            b, f, sec, r, sh, p = loc.block, str(loc.floor), loc.section, str(loc.rack), str(loc.shelf), str(loc.position)
            tup = (b, f, sec, r, sh, p)
            if tup in master_keys:
                status = 'EXACT_MASTER_MATCH'
                matched_count += 1
            else:
                status = 'UNRESOLVED_SHELVED_POSITION'
                unmatched_count += 1
        else:
            b = f = sec = r = sh = p = 'N/A'
            status = 'UNASSIGNED'
            unmatched_count += 1
        items.append({'copy_code': cp.copy_code, 'book_title': cp.book.title if cp.book else 'N/A', 'isbn': cp.book.isbn if cp.book else 'N/A', 'block': b, 'floor': f, 'section': sec, 'rack': r, 'shelf': sh, 'position': p, 'status': status})
    return render_template('librarian/location_reconciliation.html', items=items, matched_count=matched_count, unmatched_count=unmatched_count, total_copies=len(copies), total_locations=len(loc_master))
