from datetime import datetime
from app import db
from app.models import Fine, Notification
from app.utils.helpers import log_audit

def pay_fine(fine_id, payment_method='Online', transaction_ref=None):
    """Processes payment for an unpaid fine."""
    fine = Fine.query.get(fine_id)
    if not fine or fine.status != 'UNPAID':
        return False, "Invalid or already settled fine."

    fine.status = 'PAID'
    fine.paid_at = datetime.utcnow()
    fine.payment_method = payment_method
    fine.transaction_ref = transaction_ref or f"PAY-{fine.id}-{int(datetime.utcnow().timestamp())}"

    # Also update associated borrow transaction fine status if linked
    if fine.transaction:
        fine.transaction.is_fine_paid = True

    db.session.commit()

    student = fine.student
    if student and student.user:
        msg = f"Payment of ₹{fine.amount:.2f} for fine '{fine.reason}' received successfully. Ref: {fine.transaction_ref}."
        notif = Notification(user_id=student.user.id, title="Fine Payment Confirmed", message=msg, category='Fine', link='/student/dashboard')
        db.session.add(notif)
        db.session.commit()

    log_audit("PAY_FINE", "Fine", fine.id, f"Fine ₹{fine.amount:.2f} paid by student {student.name}")
    return True, f"Fine of ₹{fine.amount:.2f} successfully settled."


def waive_fine(fine_id, admin_user_id, reason="Admin Waiver"):
    """Waives fine (Admin privilege)."""
    fine = Fine.query.get(fine_id)
    if not fine or fine.status != 'UNPAID':
        return False, "Invalid fine."

    fine.status = 'WAIVED'
    fine.paid_at = datetime.utcnow()
    fine.transaction_ref = f"WAIVED-{admin_user_id}"

    if fine.transaction:
        fine.transaction.is_fine_paid = True

    db.session.commit()
    log_audit("WAIVE_FINE", "Fine", fine.id, f"Fine ₹{fine.amount:.2f} waived by Admin (Reason: {reason})")
    return True, f"Fine ₹{fine.amount:.2f} waived."
