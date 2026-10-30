import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import current_app
from app import db
from app.models.system import EmailLog

def send_email(recipient_email, subject, body_content, email_type='GENERAL'):
    """
    Sends an HTML formatted email via SMTP.
    If SMTP credentials are not configured or connection fails,
    logs status as FAILED/PENDING in EmailLog without crashing system.
    """
    if not recipient_email:
        return False

    mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = current_app.config.get('MAIL_PORT', 587)
    mail_user = current_app.config.get('MAIL_USERNAME', '')
    mail_pass = current_app.config.get('MAIL_PASSWORD', '')
    use_tls = current_app.config.get('MAIL_USE_TLS', True)

    # HTML Email template wrapper
    html_template = f"""
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
            .badge {{ display: inline-block; padding: 4px 10px; background: #2563eb; color: #fff; border-radius: 4px; font-weight: 600; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Smart Library Management System</h2>
            </div>
            <div class="content">
                <h3>{subject}</h3>
                <p>{body_content}</p>
                <br/>
                <p>If you have any questions, please contact the campus library desk.</p>
            </div>
            <div class="footer">
                &copy; {datetime.now().year} Smart Library & Book Analytics System. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    email_log = EmailLog(
        recipient=recipient_email,
        subject=subject,
        email_type=email_type,
        sent_at=datetime.utcnow(),
        status='PENDING'
    )

    if not mail_user or not mail_pass:
        email_log.status = 'PENDING'
        email_log.error_message = 'SMTP credentials not configured in environment variables.'
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
        msg['To'] = recipient_email
        msg.attach(MIMEText(html_template, 'html'))

        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        if use_tls:
            server.starttls()
        server.login(mail_user, mail_pass)
        server.sendmail(mail_user, recipient_email, msg.as_string())
        server.quit()

        email_log.status = 'SENT'
        db.session.add(email_log)
        db.session.commit()
        return True

    except Exception as e:
        email_log.status = 'FAILED'
        email_log.error_message = str(e)
        try:
            db.session.add(email_log)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return False
