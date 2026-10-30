from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models import Book, BookCopy, BorrowTransaction, Department, Category, Student, Fine, User, BookRequest

def get_librarian_kpis():
    total_books = Book.query.count()
    total_copies = BookCopy.query.count()
    available_copies = BookCopy.query.filter_by(status='AVAILABLE').count()
    issued_copies = BookCopy.query.filter_by(status='ISSUED').count()
    pending_requests = BookRequest.query.filter_by(status='PENDING').count()

    now = datetime.utcnow()
    overdue_count = BorrowTransaction.query.filter(
        BorrowTransaction.status == 'ISSUED',
        BorrowTransaction.due_date < now
    ).count()

    today_start = now.replace(hour=0, minute=0, second=0)
    today_issues = BorrowTransaction.query.filter(BorrowTransaction.issue_date >= today_start).count()
    today_returns = BorrowTransaction.query.filter(BorrowTransaction.return_date >= today_start).count()

    total_fines_query = db.session.query(func.sum(Fine.amount)).filter_by(status='PAID').scalar()
    total_fines = float(total_fines_query or 0.0)

    return {
        'total_books': total_books,
        'total_copies': total_copies,
        'available_copies': available_copies,
        'issued_copies': issued_copies,
        'pending_requests': pending_requests,
        'overdue_count': overdue_count,
        'today_issues': today_issues,
        'today_returns': today_returns,
        'total_fines': total_fines
    }


def get_monthly_transaction_chart_data():
    now = datetime.utcnow()
    labels = []
    issues_data = []
    returns_data = []

    for i in range(5, -1, -1):
        month_dt = (now - timedelta(days=i * 30)).replace(day=1)
        month_name = month_dt.strftime('%b %Y')
        next_m = (month_dt + timedelta(days=32)).replace(day=1)

        issues = BorrowTransaction.query.filter(
            BorrowTransaction.issue_date >= month_dt,
            BorrowTransaction.issue_date < next_m
        ).count()

        returns = BorrowTransaction.query.filter(
            BorrowTransaction.return_date >= month_dt,
            BorrowTransaction.return_date < next_m
        ).count()

        labels.append(month_name)
        issues_data.append(issues)
        returns_data.append(returns)

    return {
        'labels': labels,
        'issues': issues_data,
        'returns': returns_data
    }


def get_category_popularity_chart_data():
    results = db.session.query(
        Category.name,
        func.count(BorrowTransaction.id)
    ).join(Book, Book.category_id == Category.id)\
     .join(BookCopy, BookCopy.book_id == Book.id)\
     .join(BorrowTransaction, BorrowTransaction.copy_id == BookCopy.id)\
     .group_by(Category.name).all()

    labels = [r[0] for r in results]
    counts = [r[1] for r in results]

    if not labels:
        categories = Category.query.limit(5).all()
        labels = [c.name for c in categories]
        counts = [Book.query.filter_by(category_id=c.id).count() for c in categories]

    return {'labels': labels, 'data': counts}


def get_department_borrowing_chart_data():
    results = db.session.query(
        Department.code,
        func.count(BorrowTransaction.id)
    ).join(Student, Student.department_id == Department.id)\
     .join(BorrowTransaction, BorrowTransaction.student_id == Student.id)\
     .group_by(Department.code).all()

    labels = [r[0] for r in results]
    counts = [r[1] for r in results]

    if not labels:
        deps = Department.query.all()
        labels = [d.code for d in deps]
        counts = [Student.query.filter_by(department_id=d.id).count() for d in deps]

    return {'labels': labels, 'data': counts}


def get_book_utilization_stats():
    most_borrowed = db.session.query(
        Book, func.count(BorrowTransaction.id).label('borrow_cnt')
    ).join(BookCopy, BookCopy.book_id == Book.id)\
     .join(BorrowTransaction, BorrowTransaction.copy_id == BookCopy.id)\
     .group_by(Book.id)\
     .order_by(func.count(BorrowTransaction.id).desc()).limit(10).all()

    all_books = Book.query.all()
    borrowed_book_ids = {b[0].id for b in most_borrowed}
    never_borrowed = [bk for bk in all_books if bk.id not in borrowed_book_ids][:10]

    return {
        'most_borrowed': [{'book': b[0], 'count': b[1]} for b in most_borrowed],
        'never_borrowed': never_borrowed
    }
