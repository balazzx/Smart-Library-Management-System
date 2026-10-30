# 📚 Smart Library Management System

<p align="center">
  <b>A full-featured, AI-powered Library Management System built with Python & Flask</b><br/>
  Role-based dashboards for Students, Librarians, and Administrators
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-3.0+-black?logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite%20%7C%20MySQL-supported-green?logo=sqlite" />
  <img src="https://img.shields.io/badge/License-MIT-yellow" />
</p>

---

## ✨ Features

### 👨‍🎓 Student Portal
- Browse, search, and filter the entire book catalog
- Issue / return books with live availability tracking
- **Wishlist** — save books for later
- Digital resource access (PDFs)
- View borrowing history, fines, and due-date status
- Real-time notifications and reminders

### 📖 Librarian Portal
- Manage books (add / edit / delete with cover images)
- Process issue & return transactions
- Waiting list management
- QR code generation for books
- Generate PDF reports (transactions, fines, stock)
- Automated overdue reminders via email

### 🛡️ Admin Panel
- Full user management (Students & Librarians)
- System-wide analytics dashboard
- Fine configuration and management
- Department & category management
- Audit logs and system health

### 🤖 Smart Features
- **ML-based book recommendations** (scikit-learn)
- **Book cover auto-fetch** (from Open Library / Google Books APIs)
- MySQL <-> SQLite **automatic fallback** — runs anywhere without extra config
- Email notification engine for due dates and fines

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask 3.x |
| ORM | Flask-SQLAlchemy |
| Database | SQLite (default) / MySQL |
| ML | scikit-learn, pandas, numpy |
| PDF Reports | ReportLab |
| QR Codes | qrcode + Pillow |
| Email | smtplib (SMTP) |
| Frontend | HTML5, CSS3, Bootstrap 5, Vanilla JS |

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/smart-library-management-system.git
cd smart-library-management-system
```

### 2. Create & Activate Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the example file
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux

# Open .env and fill in your values
```

> **Minimum required:** Only `SECRET_KEY` is strictly needed.
> The app uses SQLite by default — no database server required!

### 5. Run the Application

```bash
python run.py
```

Open your browser at **http://127.0.0.1:5000**

---

## 🔑 Default Login Credentials

After first run, the database is seeded automatically.

| Role | Username / Roll No | Password |
|------|-------------------|----------|
| Admin | `admin` | `admin123` |
| Librarian | `librarian` | `lib123` |
| Student | *(use any seeded roll number)* | `student123` |

> Warning: **Change these passwords immediately** in a production deployment.

---

## 📁 Project Structure

```
smart-library-management-system/
├── app/
│   ├── __init__.py          # App factory (Flask)
│   ├── config.py            # Configuration (env-driven)
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── book.py
│   │   ├── transaction.py
│   │   ├── engagement.py    # Wishlist, Notifications, Reviews
│   │   ├── digital.py       # Digital resources
│   │   └── system.py        # System settings, Fine rules
│   ├── routes/              # Flask blueprints
│   │   ├── auth.py          # Login / logout / register
│   │   ├── student.py       # Student portal
│   │   ├── librarian.py     # Librarian portal
│   │   ├── admin.py         # Admin panel
│   │   ├── api.py           # REST API endpoints
│   │   └── errors.py        # 404 / 500 handlers
│   ├── services/            # Business logic layer
│   │   ├── issue_service.py
│   │   ├── return_service.py
│   │   ├── fine_service.py
│   │   ├── cover_service.py # Auto book-cover fetcher
│   │   ├── pdf_service.py
│   │   ├── qr_service.py
│   │   └── waiting_service.py
│   ├── ml/                  # Recommendation engine
│   ├── analytics/           # Analytics helpers
│   ├── email/               # Email notification system
│   ├── utils/               # Utilities (reminders, helpers)
│   ├── static/
│   │   ├── css/custom.css
│   │   ├── js/main.js
│   │   ├── book_covers/     # Cached book cover images
│   │   └── uploads/         # User uploads (gitignored)
│   └── templates/           # Jinja2 HTML templates
│       ├── base.html
│       ├── auth/
│       ├── student/
│       ├── librarian/
│       ├── admin/
│       └── errors/
├── reports/                 # Generated PDF reports (gitignored)
├── seed.py                  # Database seeder
├── run.py                   # Application entry point
├── requirements.txt
├── .env.example             # Environment template
└── .gitignore
```

---

## ⚙️ Configuration

All configuration is driven by the `.env` file (copy from `.env.example`).

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret | *required* |
| `FLASK_ENV` | `development` or `production` | `development` |
| `DB_HOST` | MySQL host | — |
| `DB_PORT` | MySQL port | `3306` |
| `DB_USER` | MySQL username | — |
| `DB_PASSWORD` | MySQL password | — |
| `DB_NAME` | MySQL database name | — |
| `MAIL_SERVER` | SMTP server | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USERNAME` | Sender email | — |
| `MAIL_PASSWORD` | App password | — |

> If MySQL credentials are absent or connection fails, the app **automatically uses SQLite**.

---

## 🗄️ Database

### SQLite (Zero Config)
No setup needed. On first `python run.py`, a `smart_library.db` file is created and seeded.

### MySQL
1. Create a database: `CREATE DATABASE smart_library_db CHARACTER SET utf8mb4;`
2. Fill `DB_*` vars in `.env`
3. Run `python run.py` — tables are created automatically

---

## 📧 Email Notifications

The system sends automated emails for:
- Book due-date reminders (3 days before)
- Overdue notices
- Fine payment confirmations

To enable, configure `MAIL_*` variables in `.env`.
For Gmail, create an **App Password** (Account → Security → 2-Step Verification → App Passwords).

---

## 🧪 Running Tests

```bash
pytest tests/
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Bala S**
Built as a Capstone Project — KIOT Central Library Management System

---

<p align="center">Made with love using Python & Flask</p>
