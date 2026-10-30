from functools import wraps
from flask import session, redirect, url_for, flash, request, abort
from app.models.user import User
from app import db

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            user_role = session.get('role')
            if user_role not in roles:
                flash('Unauthorized access: You do not have permission to view this resource.', 'danger')
                if user_role == 'STUDENT':
                    return redirect(url_for('student.dashboard'))
                elif user_role == 'LIBRARIAN':
                    return redirect(url_for('librarian.dashboard'))
                elif user_role == 'ADMIN':
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def student_required(f):
    return role_required('STUDENT')(f)

def librarian_required(f):
    return role_required('LIBRARIAN', 'ADMIN')(f)

def admin_required(f):
    return role_required('ADMIN')(f)
