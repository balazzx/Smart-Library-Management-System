import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from app import db
from app.models.system import EmailLog

def send_email(recipient, subject, body, html_body=None, email_type='GENERAL'):
    """
    Sends an email via SMTP securely using environment variables or Flask configuration.
    Exposes send_email(recipient, subject, body, html_body=None, email_type='GENERAL').
    Handles errors safely without exposing raw tracebacks or secrets to end users.
    Returns True on success, False on failure.
    """
    if not recipient:
        return False

    # First check Flask app config, fallback to environment variables
    try:
        mail_server = current_app.config.get('MAIL_SERVER') or os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        mail_port = int(current_app.config.get('MAIL_PORT') or os.environ.get('MAIL_PORT', 587))
        mail_user = current_app.config.get('MAIL_USERNAME') or os.environ.get('MAIL_USERNAME', '')
        mail_pass = current_app.config.get('MAIL_PASSWORD') or os.environ.get('MAIL_PASSWORD', '')
        use_tls_val = current_app.config.get('MAIL_USE_TLS') if current_app.config.get('MAIL_USE_TLS') is not None else os.environ.get('MAIL_USE_TLS', 'True')
        use_tls = str(use_tls_val).lower() in ('true', '1', 't', 'yes')
    except Exception:
        mail_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        mail_port = int(os.environ.get('MAIL_PORT', 587))
        mail_user = os.environ.get('MAIL_USERNAME', '')
        mail_pass = os.environ.get('MAIL_PASSWORD', '')
        use_tls = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't', 'yes')

    # Prepare HTML content
    content_html = html_body if html_body else f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .header {{ background-color: #0A192F; color: #ffffff; padding: 25px; text-align: center; }}
            .header h2 {{ margin: 0; font-size: 22px; letter-spacing: 0.5px; }}
            .content {{ padding: 30px; font-size: 15px; line-height: 1.6; color: #2d3748; }}
            .footer {{ background-color: #f8fafc; text-align: center; padding: 15px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>KIOT Central Library Management System</h2>
            </div>
            <div class="content">
                <h3>{subject}</h3>
                <p>{body}</p>
                <br/>
                <p>Knowledge Institute of Technology Central Library Desk.</p>
            </div>
            <div class="footer">
                &copy; {datetime.now().year} KIOT Central Library & Book Analytics System. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    email_log = EmailLog(
        recipient=recipient,
        subject=subject,
        email_type=email_type,
        sent_at=datetime.utcnow(),
        status='PENDING'
    )

    if not mail_user or not mail_pass:
        email_log.status = 'FAILED'
        email_log.error_message = 'SMTP credentials (MAIL_USERNAME / MAIL_PASSWORD) not configured.'
        try:
            db.session.add(email_log)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = mail_user
        msg['To'] = recipient
        msg.attach(MIMEText(body, 'plain'))
        msg.attach(MIMEText(content_html, 'html'))

        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        if use_tls:
            server.starttls()
        server.login(mail_user, mail_pass)
        server.sendmail(mail_user, recipient, msg.as_string())
        server.quit()

        email_log.status = 'SENT'
        email_log.error_message = None
        db.session.add(email_log)
        db.session.commit()
        return True

    except smtplib.SMTPAuthenticationError:
        email_log.status = 'FAILED'
        email_log.error_message = 'SMTP Authentication failed. Verify configured MAIL_USERNAME and MAIL_PASSWORD.'
    except smtplib.SMTPConnectError:
        email_log.status = 'FAILED'
        email_log.error_message = 'SMTP Connection failed. Verify MAIL_SERVER and MAIL_PORT.'
    except smtplib.SMTPServerDisconnected:
        email_log.status = 'FAILED'
        email_log.error_message = 'SMTP Server disconnected unexpectedly.'
    except Exception as e:
        email_log.status = 'FAILED'
        email_log.error_message = f'SMTP delivery failed: {type(e).__name__}'

    try:
        db.session.add(email_log)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return False
