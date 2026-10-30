import os
from datetime import datetime
from flask import current_app
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_inventory_pdf_report(books, output_filename="inventory_report.pdf"):
    report_path = os.path.join(current_app.config['REPORT_FOLDER'], output_filename)
    doc = SimpleDocTemplate(report_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#0A192F'), spaceAfter=12)
    meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#64748B'), spaceAfter=15)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#1E293B'))

    story.append(Paragraph("KIOT CENTRAL LIBRARY - Inventory Report", title_style))
    story.append(Paragraph(f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Books: {len(books)}", meta_style))

    table_data = [["ISBN", "Title", "Author", "Category", "Copies", "Available", "Location"]]
    for b in books:
        loc = b.location.display_name if b.location else "Unassigned"
        table_data.append([
            Paragraph(b.isbn, cell_style),
            Paragraph(b.title, cell_style),
            Paragraph(b.author.name if b.author else "", cell_style),
            Paragraph(b.category.name if b.category else "", cell_style),
            str(b.total_copies_count),
            str(b.available_copies_count),
            Paragraph(loc, cell_style)
        ])

    t = Table(table_data, colWidths=[70, 140, 90, 80, 45, 55, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0A192F')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    story.append(t)
    doc.build(story)
    return report_path


def generate_generic_pdf_report(title, headers, rows, output_filename="report.pdf", col_widths=None):
    report_path = os.path.join(current_app.config['REPORT_FOLDER'], output_filename)
    doc = SimpleDocTemplate(report_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, textColor=colors.HexColor('#0A192F'), spaceAfter=8)
    meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#64748B'), spaceAfter=15)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.HexColor('#1E293B'))

    # KIOT Header
    story.append(Paragraph("KNOWLEDGE INSTITUTE OF TECHNOLOGY — CENTRAL LIBRARY", title_style))
    story.append(Paragraph(f"Report: <b>{title}</b> | Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Records: {len(rows)}", meta_style))

    table_data = [[Paragraph(f"<b>{h}</b>", cell_style) for h in headers]]
    for row in rows:
        table_data.append([Paragraph(str(v if v is not None else ''), cell_style) for v in row])

    if not col_widths:
        usable_width = 540
        cw = usable_width / len(headers)
        col_widths = [cw] * len(headers)

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0A192F')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    story.append(t)
    doc.build(story)
    return report_path


def generate_generic_excel_report(title, headers, rows, output_filename="report.xlsx"):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report Data"

    ws.append([f"KIOT CENTRAL LIBRARY — {title.upper()}"])
    ws.append([f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    ws.append([])
    ws.append(headers)

def generate_borrow_history_pdf(transactions, student_name, output_filename="borrow_history.pdf"):
    report_path = os.path.join(current_app.config['REPORT_FOLDER'], output_filename)
    doc = SimpleDocTemplate(report_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#0A192F'), spaceAfter=12)
    meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#64748B'), spaceAfter=15)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=9)

    story.append(Paragraph(f"KIOT CENTRAL LIBRARY - Borrowing Statement ({student_name})", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", meta_style))

    table_data = [["Copy Code", "Book Title", "Issue Date", "Due Date", "Return Date", "Status", "Fine"]]
    for tx in transactions:
        bk_title = tx.copy.book.title if tx.copy and tx.copy.book else "N/A"
        ret_dt = tx.return_date.strftime('%Y-%m-%d') if tx.return_date else "-"
        table_data.append([
            tx.copy.copy_code if tx.copy else "",
            Paragraph(bk_title, cell_style),
            tx.issue_date.strftime('%Y-%m-%d'),
            tx.due_date.strftime('%Y-%m-%d'),
            ret_dt,
            tx.status,
            f"₹{tx.fine_amount:.2f}"
        ])

    t = Table(table_data, colWidths=[70, 160, 70, 70, 70, 50, 50])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563EB')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    story.append(t)
    doc.build(story)
    return report_path
