import os
import qrcode
from flask import current_app

def generate_qr_code(data_string, filename):
    """Generates a high-quality QR code PNG image and saves it to static uploads."""
    qr_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)
    file_path = os.path.join(qr_dir, filename)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data_string)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0A192F", back_color="#FFFFFF")
    img.save(file_path)

    return f"uploads/qrcodes/{filename}"

def generate_book_qr(book_id):
    content = f"SMART_LIB_BOOK:{book_id}"
    return generate_qr_code(content, f"book_{book_id}.png")

def generate_copy_qr(copy_code):
    content = f"SMART_LIB_COPY:{copy_code}"
    return generate_qr_code(content, f"copy_{copy_code}.png")

def generate_student_card_qr(student_card_number):
    content = f"SMART_LIB_CARD:{student_card_number}"
    return generate_qr_code(content, f"card_{student_card_number}.png")
