import os
import unittest
from app import create_app, db
from app.models import User, Student, Librarian, Department, Book, BookCopy, BorrowTransaction, BookRequest, Fine
from app.services.issue_service import create_book_request, approve_and_issue_book
from app.services.return_service import process_book_return
from app.ml.nlp_search import search_books_nlp
from app.ml.recommendation_engine import get_personalized_recommendations
from app.ml.demand_predictor import predict_book_demand
from seed import seed_database

class SmartLibraryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            seed_database()

    def test_authentication(self):
        with self.app.app_context():
            # Test Admin login
            admin = User.query.filter_by(username='admin').first()
            self.assertIsNotNone(admin)
            self.assertTrue(admin.check_password('Admin@123'))
            self.assertTrue(admin.is_admin())

            # Test Student login
            student_user = User.query.filter_by(username='student1').first()
            self.assertIsNotNone(student_user)
            self.assertTrue(student_user.check_password('Student@123'))
            self.assertTrue(student_user.is_student())

    def test_nlp_search(self):
        with self.app.app_context():
            results = search_books_nlp("Python programming machine learning data science", top_n=5)
            self.assertGreater(len(results), 0)
            self.assertIn("Python", results[0]['book'].title)

    def test_borrow_issue_return_workflow(self):
        with self.app.app_context():
            admin = User.query.filter_by(role='ADMIN').first()
            student = Student.query.first()
            
            # Select a book with available copies that student does not currently have issued
            issued_book_ids = [tx.copy.book_id for tx in student.borrow_transactions.filter_by(status='ISSUED').all() if tx.copy]
            book = Book.query.filter(~Book.id.in_(issued_book_ids if issued_book_ids else [0]), Book.copies.any(status='AVAILABLE')).first()

            # Clear any pre-existing pending requests for this test pair
            BookRequest.query.filter_by(student_id=student.id, book_id=book.id).delete()
            db.session.commit()

            # 1. Student Requests Book
            success, msg = create_book_request(student.id, book.id)
            self.assertTrue(success, f"Request failed: {msg}")

            req = BookRequest.query.filter_by(student_id=student.id, book_id=book.id, status='PENDING').first()
            self.assertIsNotNone(req)

            # 2. Librarian Approves & Issues Book
            success, msg = approve_and_issue_book(req.id, admin.id)
            self.assertTrue(success)

            tx = BorrowTransaction.query.filter_by(student_id=student.id, status='ISSUED').first()
            self.assertIsNotNone(tx)
            self.assertEqual(tx.copy.status, 'ISSUED')

            # 3. Process Return
            success, msg = process_book_return(tx.id, condition='GOOD')
            self.assertTrue(success)

            tx_returned = BorrowTransaction.query.get(tx.id)
            self.assertEqual(tx_returned.status, 'RETURNED')
            self.assertEqual(tx_returned.copy.status, 'AVAILABLE')

    def test_ai_recommendation_and_ml_prediction(self):
        with self.app.app_context():
            student = Student.query.first()
            recs = get_personalized_recommendations(student.id, top_n=3)
            self.assertIsNotNone(recs)

            book = Book.query.first()
            pred = predict_book_demand(book.id)
            self.assertIsNotNone(pred)
            self.assertIn('predicted_demand', pred)

if __name__ == '__main__':
    unittest.main()
