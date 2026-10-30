import os
import random
from datetime import datetime, timedelta
from app import create_app, db
from app.models import (
    User, Department, Student, Librarian, Author, Category, Publisher,
    BookLocation, Book, BookCopy, BookRequest, BorrowTransaction, ReturnTransaction,
    Reservation, WaitingList, Wishlist, RatingReview, Fine, DigitalResource,
    Announcement, Notification, SearchHistory, SystemSetting
)

app = create_app()

def seed_database():
    with app.app_context():
        print("Clearing and creating database schema...")
        db.create_all()

        # Check if database has data (including real KIOT data)
        if User.query.first():
            print("Database is already seeded with real KIOT Central Library data.")
            return

        print("Seeding Departments...")
        depts_data = [
            ('CSE', 'Computer Science and Engineering'),
            ('IT', 'Information Technology'),
            ('AI & DS', 'Artificial Intelligence and Data Science'),
            ('CSBS', 'Computer Science and Business Systems'),
            ('ECE', 'Electronics and Communication Engineering'),
            ('EEE', 'Electrical and Electronics Engineering'),
            ('ECX', 'Electronics and Computer Engineering'),
            ('Mechanical', 'Mechanical Engineering'),
            ('Civil', 'Civil Engineering')
        ]

        dept_objs = {}
        for code, name in depts_data:
            d = Department(code=code, name=name)
            db.session.add(d)
            dept_objs[code] = d
        db.session.flush()

        print("Seeding System Settings...")
        settings_data = [
            ('MAX_BORROW_LIMIT', '5', 'Maximum books a student can borrow simultaneously'),
            ('BORROW_PERIOD_DAYS', '14', 'Standard borrowing duration in days'),
            ('GRACE_PERIOD_DAYS', '2', 'Grace period before overdue fines begin accumulating'),
            ('FINE_PER_DAY', '5.0', 'Daily overdue fine amount in currency'),
            ('MAX_FINE', '500.0', 'Maximum cap for overdue fine'),
            ('CLAIM_PERIOD_HOURS', '48', 'Time window to collect a reserved book once notified'),
            ('LIBRARY_NAME', 'Smart Campus Central Library', 'Official college library display name')
        ]
        for key, val, desc in settings_data:
            s = SystemSetting(setting_key=key, setting_value=val, description=desc)
            db.session.add(s)

        print("Seeding Users & Profiles...")
        # Admin User
        admin_user = User(username='admin', email='admin@library.edu', role='ADMIN')
        admin_user.set_password('Admin@123')
        db.session.add(admin_user)

        # Librarians
        lib1_user = User(username='librarian1', email='librarian1@library.edu', role='LIBRARIAN')
        lib1_user.set_password('Librarian@123')
        db.session.add(lib1_user)
        db.session.flush()

        lib1_profile = Librarian(user_id=lib1_user.id, staff_id='LIB-1001', name='Sarah Jenkins', department_id=dept_objs['CSE'].id, phone='9876543210')
        db.session.add(lib1_profile)

        # Students
        students = []
        student_names = [
            ('Alex Rivera', 'CSE', '21CSE001', 'alex.rivera@college.edu'),
            ('Priya Sharma', 'AI & DS', '21AIDS012', 'priya.sharma@college.edu'),
            ('David Chen', 'IT', '21IT045', 'david.chen@college.edu'),
            ('Ananya Patel', 'ECE', '21ECE023', 'ananya.patel@college.edu'),
            ('Marcus Vance', 'CSBS', '21CSBS009', 'marcus.vance@college.edu'),
            ('Rahul Verma', 'CSE', '21CSE088', 'rahul.verma@college.edu'),
            ('Emily Watson', 'Mechanical', '21MECH014', 'emily.watson@college.edu'),
            ('Siddharth Nair', 'EEE', '21EEE031', 'siddharth.nair@college.edu'),
            ('Sophia Rodriguez', 'Civil', '21CIVIL005', 'sophia.rodriguez@college.edu'),
            ('Karthik Raja', 'ECX', '21ECX019', 'karthik.raja@college.edu')
        ]

        for i, (name, dept_code, roll, email) in enumerate(student_names, 1):
            uname = f"student{i}"
            u = User(username=uname, email=email, role='STUDENT')
            u.set_password('Student@123')
            db.session.add(u)
            db.session.flush()

            st = Student(
                user_id=u.id,
                student_id=roll,
                name=name,
                department_id=dept_objs[dept_code].id,
                phone=f"90000000{i:02d}",
                library_card_number=f"SLC-{u.id:05d}-{roll[-4:]}",
                max_borrow_limit=5
            )
            db.session.add(st)
            students.append(st)

        db.session.flush()

        print("Seeding Authors, Categories, Publishers & Locations...")
        authors = [
            Author(name='Guido van Rossum', bio='Creator of the Python programming language.'),
            Author(name='Stuart Russell', bio='Professor of Computer Science at UC Berkeley, AI pioneer.'),
            Author(name='Peter Norvig', bio='Director of Research at Google, author of AI: A Modern Approach.'),
            Author(name='Robert C. Martin', bio='Software pioneer and author of Clean Code.'),
            Author(name='Andrew S. Tanenbaum', bio='Renowned professor and author on Operating Systems.'),
            Author(name='Ian Goodfellow', bio='Deep learning researcher, creator of GANs.'),
            Author(name='Erich Gamma', bio='Design Patterns pioneer.'),
            Author(name='Martin Fowler', bio='Software architect and author on Refactoring.'),
            Author(name='Silberschatz & Galvin', bio='Classic Database and Operating System textbook authors.'),
            Author(name='Donald Knuth', bio='Legendary computer scientist, author of The Art of Computer Programming.')
        ]
        db.session.add_all(authors)

        categories = [
            Category(name='Computer Programming', description='Software development, Python, Java, C++, Clean Architecture'),
            Category(name='Artificial Intelligence & ML', description='Machine learning, Neural networks, Deep learning, NLP'),
            Category(name='Data Science & Analytics', description='Pandas, Data visualization, Big Data, Applied Statistics'),
            Category(name='Database Management Systems', description='Relational DBs, SQL, NoSQL, Query Optimization'),
            Category(name='Operating Systems', description='Linux, Kernel architecture, Process Scheduling, Distributed Systems'),
            Category(name='Computer Networks & Security', description='TCP/IP, Cybersecurity, Cryptography, Network Protocols'),
            Category(name='Software Engineering & Design', description='Design Patterns, System Architecture, Agile Methodologies'),
            Category(name='Electronics & VLSI', description='Microprocessors, Digital Signal Processing, Embedded Systems'),
            Category(name='Robotics & Automation', description='Control systems, Mechatronics, Computer Vision'),
            Category(name='General Science & Mathematics', description='Discrete Mathematics, Linear Algebra, Probability')
        ]
        db.session.add_all(categories)

        publishers = [
            Publisher(name='O\'Reilly Media'),
            Publisher(name='Pearson Education'),
            Publisher(name='MIT Press'),
            Publisher(name='McGraw-Hill'),
            Publisher(name='Addison-Wesley'),
            Publisher(name='Packt Publishing'),
            Publisher(name='Springer')
        ]
        db.session.add_all(publishers)

        locations = [
            BookLocation(block='CSE Block', floor='2', section='Programming', rack='R01', shelf='S01', position='01'),
            BookLocation(block='CSE Block', floor='2', section='Programming', rack='R01', shelf='S02', position='05'),
            BookLocation(block='AI & DS Block', floor='3', section='Artificial Intelligence', rack='R02', shelf='S01', position='03'),
            BookLocation(block='AI & DS Block', floor='3', section='Machine Learning', rack='R02', shelf='S03', position='12'),
            BookLocation(block='IT Block', floor='1', section='Databases', rack='R03', shelf='S01', position='08'),
            BookLocation(block='ECE Block', floor='2', section='Electronics', rack='R04', shelf='S02', position='10'),
            BookLocation(block='Central Library', floor='1', section='Reference', rack='R05', shelf='S04', position='15')
        ]
        db.session.add_all(locations)
        db.session.flush()

        print("Seeding 50+ Technical & Academic Books...")
        book_titles = [
            ("Python Crash Course: A Hands-On Project-Based Introduction", "9781593279288", 0, 0, 0, 2023, "Master Python programming fundamentals, data structures, matplotlib, Django, and automated testing from scratch."),
            ("Artificial Intelligence: A Modern Approach (4th Edition)", "9780134610993", 1, 1, 1, 2021, "The comprehensive standard textbook for AI covering search algorithms, knowledge representation, reinforcement learning, and ethics."),
            ("Deep Learning with Python & PyTorch", "9781617294433", 5, 1, 0, 2022, "Hands-on guide to building deep neural networks, computer vision models, and natural language transformers using PyTorch."),
            ("Clean Code: A Handbook of Agile Software Craftsmanship", "9780132350884", 3, 6, 4, 2020, "Essential principles of writing clean, maintainable, readable, and robust software with code smells and refactoring patterns."),
            ("Operating System Concepts (10th Edition)", "9781119456339", 8, 4, 1, 2018, "Classic guide to OS fundamentals: processes, threads, CPU scheduling, memory management, virtual memory, and storage structures."),
            ("Database System Concepts (7th Edition)", "9780078022159", 8, 3, 3, 2019, "Comprehensive introduction to relational databases, SQL queries, indexing, transaction processing, and distributed DBs."),
            ("Data Science from Scratch: First Principles with Python", "9781492041139", 0, 2, 0, 2020, "Learn data science math, algorithms, linear algebra, and machine learning models implemented in pure Python."),
            ("Design Patterns: Elements of Reusable Object-Oriented Software", "9780201633610", 6, 6, 4, 2016, "The seminal GoF catalog of 23 object-oriented design patterns including Singleton, Factory, Observer, Strategy, and Decorator."),
            ("Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow", "9781492032649", 1, 1, 0, 2022, "Practical guide to training machine learning algorithms, random forests, neural nets, and deploying ML pipelines."),
            ("Computer Networking: A Top-Down Approach (8th Edition)", "9780136681557", 4, 5, 1, 2021, "Layer-by-layer exploration of computer network protocols, internet architecture, TCP/IP, wireless security, and socket programming."),
            ("The Pragmatic Programmer: Your Journey to Mastery", "9780135957059", 7, 6, 4, 2019, "Timeless software engineering practices, self-improvement strategies, developer tools, and career advice."),
            ("Introduction to Algorithms (4th Edition - CLRS)", "9780262046305", 9, 0, 2, 2022, "The definitive textbook on data structures, dynamic programming, graph algorithms, NP-completeness, and complexity analysis."),
            ("Head First Design Patterns: Building Extensible & Maintainable Software", "9781492078005", 6, 6, 0, 2021, "Visually rich, interactive guide to OOP design principles and architectural patterns."),
            ("Designing Data-Intensive Applications", "9781449373320", 7, 3, 0, 2017, "Deep dive into data systems reliability, scalability, consensus protocols, batch processing, and event stream architecture."),
            ("Modern Operating Systems (5th Edition)", "9780137618880", 4, 4, 1, 2022, "Detailed analysis of Linux and Windows internals, virtual machines, kernel security, and multiprocessor scheduling."),
            ("Machine Learning: An Algorithmic Perspective", "9781466583283", 2, 1, 6, 2018, "Math-heavy algorithmic explanations of regression, SVMs, decision trees, neural nets, and Bayesian classification."),
            ("Learning Python: Powerful Object-Oriented Programming", "9781449355739", 0, 0, 0, 2017, "Comprehensive deep dive into Python syntax, modules, classes, generator expressions, and decorators."),
            ("Natural Language Processing with Transformers", "9781098103248", 5, 1, 0, 2022, "Building modern NLP applications using Hugging Face Transformers, BERT, GPT models, and text generation."),
            ("Cybersecurity Essentials", "9781119362395", 4, 5, 3, 2020, "Foundational principles of network security, ethical hacking, threat intelligence, firewalls, and encryption."),
            ("Microprocessor Architecture, Programming, and Applications with the 8085", "9788175960725", 8, 7, 1, 2017, "Classic textbook on 8085/8086 microprocessor assembly language, interfacing, memory mapping, and hardware timers."),
            ("Robotics, Vision and Control: Fundamental Algorithms in Python", "9783030331825", 2, 8, 6, 2020, "Kinematics, dynamics, visual servoing, navigation algorithms, and ROS programming for autonomous mobile robots."),
            ("Pattern Recognition and Machine Learning", "9780387310732", 1, 1, 6, 2016, "Bayesian inference, mixture models, expectation-maximization, variational inference, and kernel methods."),
            ("Continuous Delivery: Reliable Software Releases through Build Automation", "9780321601910", 7, 6, 4, 2019, "DevOps principles, CI/CD pipelines, automated testing strategies, and zero-downtime deployment tactics."),
            ("SQL in 10 Minutes, Sams Teach Yourself", "9780135182796", 8, 3, 1, 2019, "Fast-paced practical tutorial for writing SQL queries, joins, aggregates, subqueries, and stored procedures."),
            ("Effective Java (3rd Edition)", "9780134685991", 3, 0, 4, 2018, "Best practice programming idioms for Java developers covering generics, enums, lambda expressions, and concurrency.")
        ]

        books_created = []
        for title, isbn, a_idx, c_idx, p_idx, year, desc in book_titles:
            b = Book(
                title=title,
                isbn=isbn,
                author_id=authors[a_idx].id,
                category_id=categories[c_idx].id,
                publisher_id=publishers[p_idx].id,
                pub_year=year,
                description=desc,
                location_id=locations[c_idx % len(locations)].id
            )
            db.session.add(b)
            books_created.append(b)
        db.session.flush()

        print("Seeding 100+ Physical Book Copies...")
        all_copies = []
        for b in books_created:
            copy_count = random.randint(3, 6)
            for j in range(1, copy_count + 1):
                c = BookCopy(
                    copy_code=f"BC-{b.id:04d}-{j:02d}",
                    book_id=b.id,
                    condition_status=random.choice(['EXCELLENT', 'GOOD', 'GOOD', 'FAIR']),
                    status='AVAILABLE',
                    location_id=b.location_id
                )
                db.session.add(c)
                all_copies.append(c)
        db.session.flush()

        print("Seeding Historical Borrowing Transactions (for Analytics & ML)...")
        now = datetime.utcnow()
        for i in range(40):
            st = random.choice(students)
            cp = random.choice(all_copies)

            days_ago = random.randint(5, 120)
            issue_dt = now - timedelta(days=days_ago)
            due_dt = issue_dt + timedelta(days=14)

            # Historical completed returns
            ret_dt = issue_dt + timedelta(days=random.randint(7, 18))
            fine_amt = 0.0
            if ret_dt > due_dt:
                overdue_d = (ret_dt - due_dt).days
                fine_amt = max(0, overdue_d - 2) * 5.0

            tx = BorrowTransaction(
                copy_id=cp.id,
                student_id=st.id,
                issue_date=issue_dt,
                due_date=due_dt,
                return_date=ret_dt,
                status='RETURNED',
                fine_amount=fine_amt,
                is_fine_paid=True if fine_amt > 0 else False
            )
            db.session.add(tx)
            db.session.flush()

            # Add return transaction detail
            ret_tx = ReturnTransaction(
                borrow_transaction_id=tx.id,
                return_date=ret_dt,
                condition_on_return='GOOD',
                fine_assessed=fine_amt
            )
            db.session.add(ret_tx)

        # Active current issues
        for i in range(12):
            st = random.choice(students)
            cp = random.choice([c for c in all_copies if c.status == 'AVAILABLE'])
            cp.status = 'ISSUED'

            days_ago = random.randint(1, 20)
            issue_dt = now - timedelta(days=days_ago)
            due_dt = issue_dt + timedelta(days=14)

            tx = BorrowTransaction(
                copy_id=cp.id,
                student_id=st.id,
                issue_date=issue_dt,
                due_date=due_dt,
                status='ISSUED'
            )
            db.session.add(tx)

        print("Seeding Ratings, Reviews, Wishlists & Search Histories...")
        for st in students:
            # Reviews
            sample_books = random.sample(books_created, k=3)
            for b in sample_books:
                rr = RatingReview(
                    student_id=st.id,
                    book_id=b.id,
                    rating=random.randint(4, 5),
                    review_text=f"Extremely insightful book for {st.department.name} students!"
                )
                db.session.add(rr)

            # Wishlists
            w_books = random.sample(books_created, k=2)
            for wb in w_books:
                w = Wishlist(student_id=st.id, book_id=wb.id)
                db.session.add(w)

            # Search History
            queries = ["Python programming", "Machine learning artificial intelligence", "Data structures and algorithms", "SQL database design"]
            for q in random.sample(queries, k=2):
                sh = SearchHistory(student_id=st.id, query_text=q)
                db.session.add(sh)

        print("Seeding Announcements & Digital Resources...")
        ann = Announcement(
            title="Mid-Semester Library Extended Hours",
            message="The Central Library will remain open until 10:00 PM during upcoming mid-term examinations.",
            priority="HIGH",
            target_role="ALL",
            start_date=now.date(),
            end_date=(now + timedelta(days=30)).date(),
            created_by=admin_user.id
        )
        db.session.add(ann)

        res = DigitalResource(
            title="Python Data Science Cheat Sheet 2026",
            author="Library Technical Team",
            description="Comprehensive guide covering NumPy arrays, Pandas DataFrames, and Scikit-Learn pipelines.",
            category_id=categories[2].id,
            file_path="uploads/pdfs/sample_cheat_sheet.pdf",
            file_type="PDF",
            file_size=204800,
            target_department_id=dept_objs['CSE'].id,
            uploaded_by=lib1_user.id
        )
        db.session.add(res)

        db.session.commit()
        print("SEEDING COMPLETE SUCCESSFUL!")

if __name__ == '__main__':
    seed_database()
