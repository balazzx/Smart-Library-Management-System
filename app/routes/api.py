from flask import Blueprint, jsonify, request
from app.analytics.analytics_engine import (
    get_monthly_transaction_chart_data,
    get_category_popularity_chart_data,
    get_department_borrowing_chart_data
)
from app.utils.reminders import process_automated_reminders

api_bp = Blueprint('api', __name__)

@api_bp.route('/analytics/monthly')
def monthly_analytics_api():
    data = get_monthly_transaction_chart_data()
    return jsonify(data)

@api_bp.route('/analytics/categories')
def categories_analytics_api():
    data = get_category_popularity_chart_data()
    return jsonify(data)

@api_bp.route('/analytics/departments')
def departments_analytics_api():
    data = get_department_borrowing_chart_data()
    return jsonify(data)

@api_bp.route('/trigger-reminders', methods=['POST'])
def trigger_reminders_api():
    processed = process_automated_reminders()
    return jsonify({'status': 'success', 'processed_notifications': processed})


@api_bp.route('/qr/resolve', methods=['POST'])
def resolve_qr_api():
    from app.models import Student, BookCopy, Book, BorrowTransaction
    qr_data = request.json.get('qr_data', '') if (request.is_json and request.json) else request.form.get('qr_data', '')
    qr_data = str(qr_data).strip()

    if not qr_data:
        return jsonify({'status': 'error', 'message': 'No QR data provided.'}), 400

    # Normalize QR payload string
    clean_payload = qr_data
    for prefix in ['SMART_LIB_CARD:', 'SMART_LIB_BOOK:', 'SMART_LIB_COPY:', 'CARD:', 'BOOK:', 'COPY:']:
        if clean_payload.startswith(prefix):
            clean_payload = clean_payload[len(prefix):].strip()

    # 1. Student Identification (by Card Number, Roll Number, or Reg Number)
    st = Student.query.filter(
        (Student.library_card_number.ilike(clean_payload)) |
        (Student.student_id.ilike(clean_payload)) |
        (Student.reg_no.ilike(clean_payload)) |
        (Student.library_card_number.ilike(qr_data)) |
        (Student.student_id.ilike(qr_data))
    ).first()

    if st:
        active_b_cnt = BorrowTransaction.query.filter_by(student_id=st.id, status='ISSUED').count()
        return jsonify({
            'status': 'success',
            'type': 'student',
            'student_id': st.id,
            'name': st.name,
            'roll_no': st.student_id,
            'reg_no': st.reg_no or '',
            'library_card_number': st.library_card_number,
            'department': st.department.code if st.department else '',
            'max_limit': st.max_borrow_limit,
            'active_borrows': active_b_cnt,
            'redirect_url': f"/librarian/issue-book?student_id={st.student_id}"
        })

    # 2. Book Copy Identification (by Access No / Copy Code)
    copy = BookCopy.query.filter(
        (BookCopy.copy_code.ilike(clean_payload)) |
        (BookCopy.copy_code.ilike(qr_data))
    ).first()

    if copy:
        active_tx = BorrowTransaction.query.filter_by(copy_id=copy.id, status='ISSUED').first()
        return jsonify({
            'status': 'success',
            'type': 'copy',
            'copy_id': copy.id,
            'copy_code': copy.copy_code,
            'book_id': copy.book_id,
            'book_title': copy.book.title if copy.book else '',
            'condition': copy.condition_status,
            'book_status': copy.status,
            'active_transaction_id': active_tx.id if active_tx else None,
            'redirect_url': f"/librarian/return-book?copy_code={copy.copy_code}"
        })

    # 3. Book Title Catalog Identification (by ID or ISBN)
    book = None
    if clean_payload.isdigit():
        book = Book.query.get(int(clean_payload))
    if not book:
        book = Book.query.filter((Book.isbn.ilike(clean_payload)) | (Book.isbn.ilike(qr_data))).first()

    if book:
        return jsonify({
            'status': 'success',
            'type': 'book',
            'book_id': book.id,
            'title': book.title,
            'isbn': book.isbn,
            'available_copies': book.available_copies_count,
            'total_copies': book.total_copies_count,
            'location': book.location.display_name if book.location else 'Main Stacks',
            'redirect_url': f"/student/books/{book.id}"
        })

    return jsonify({'status': 'error', 'message': f'QR payload "{qr_data}" could not be matched.'}), 404
