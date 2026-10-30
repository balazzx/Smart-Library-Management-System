from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models import User, Student, Department
from app.utils.decorators import login_required
from app.utils.helpers import log_audit
from app.email.mail_service import send_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'STUDENT':
            return redirect(url_for('student.dashboard'))
        elif role == 'LIBRARIAN':
            return redirect(url_for('librarian.dashboard'))
        elif role == 'ADMIN':
            return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        login_input = request.form.get('login_input', '').strip()
        password = request.form.get('password', '').strip()

        if not login_input or not password:
            flash('Please enter your username/email and password.', 'warning')
            return render_template('auth/login.html')

        user = User.query.filter(
            (User.username == login_input) | (User.email == login_input)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact the library administrator.', 'danger')
                return render_template('auth/login.html')

            session.clear()
            session['user_id'] = user.id
            session['username'] = user.username
            session['email'] = user.email
            session['role'] = user.role

            log_audit('LOGIN', 'User', user.id, f"User {user.username} logged in as {user.role}")
            flash(f"Welcome back, {user.username}!", 'success')

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user.role == 'STUDENT':
                return redirect(url_for('student.dashboard'))
            elif user.role == 'LIBRARIAN':
                return redirect(url_for('librarian.dashboard'))
            elif user.role == 'ADMIN':
                return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid username/email or password. Please try again.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Self-registration is disabled. Redirects to login with informational message."""
    flash('Self-registration is disabled. KIOT Central Library accounts are managed for authorized existing users only.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        log_audit('LOGOUT', 'User', user_id, "User logged out")
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not user.check_password(current_password):
            flash('Current password is incorrect.', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
        elif len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'warning')
        else:
            user.set_password(new_password)
            db.session.commit()
            log_audit('CHANGE_PASSWORD', 'User', user.id, "User changed password.")
            flash('Password successfully updated!', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/change_password.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter((User.email.ilike(email)) | (User.username.ilike(email))).first()
        if user:
            import secrets
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            msg = f"Hello {user.username},\n\nYou requested a password reset for your KIOT Central Library account. Click the link below or paste it into your browser to reset your password:\n\n{reset_url}\n\nThis link is valid for 1 hour."
            send_email(user.email, "KIOT Central Library Password Reset Request", msg, 'PASSWORD_RESET')
            log_audit('FORGOT_PASSWORD_REQUEST', 'User', user.id, f"Password reset requested for {user.email}")
            
        flash('If the account exists, password reset instructions have been sent to your registered email.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        flash('Invalid or expired password reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
        elif len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'warning')
        else:
            user.set_password(new_password)
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            log_audit('RESET_PASSWORD_SUCCESS', 'User', user.id, f"User {user.username} reset password via token.")
            flash('Password successfully reset! You can now log in with your new password.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
