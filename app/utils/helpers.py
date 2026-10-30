from flask import has_request_context, session, request
from app import db
from app.models.system import AuditLog, SystemSetting

def log_audit(action, entity=None, entity_id=None, description=None):
    """Utility to record system activity in AuditLog."""
    try:
        user_id = None
        role = 'SYSTEM'
        ip_addr = '127.0.0.1'

        if has_request_context():
            user_id = session.get('user_id')
            role = session.get('role', 'ANONYMOUS')
            ip_addr = request.remote_addr or '127.0.0.1'

        audit_entry = AuditLog(
            user_id=user_id,
            role=role,
            action=action,
            entity=entity,
            entity_id=entity_id,
            description=description,
            ip_address=ip_addr
        )
        db.session.add(audit_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Audit log writing info: {e}")


def get_setting(key, default_value=None):
    """Retrieve system configuration value from database setting or return default."""
    try:
        setting = SystemSetting.query.filter_by(setting_key=key).first()
        if setting and setting.setting_value:
            # Parse numeric values if applicable
            val = setting.setting_value
            if val.replace('.', '', 1).isdigit():
                return float(val) if '.' in val else int(val)
            return val
    except Exception:
        pass
    return default_value
