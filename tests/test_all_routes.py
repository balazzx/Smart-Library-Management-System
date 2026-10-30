import unittest
from app import create_app, db
from app.models import User, Student, Librarian, Book, Category, Author
from seed import seed_database

class RouteCoverageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            seed_database()

    def set_session_user(self, username):
        with self.app.app_context():
            u = User.query.filter_by(username=username).first()
            with self.client.session_transaction() as sess:
                sess['user_id'] = u.id
                sess['username'] = u.username
                sess['email'] = u.email
                sess['role'] = u.role

    def test_auth_routes(self):
        # Clear session to test unauthenticated login GET
        with self.client.session_transaction() as sess:
            sess.clear()

        # Login page
        res = self.client.get('/auth/login')
        self.assertEqual(res.status_code, 200)

        # Register page
        res = self.client.get('/auth/register')
        self.assertEqual(res.status_code, 200)

        # Login POST
        res = self.client.post('/auth/login', data={'login_input': 'admin', 'password': 'Admin@123'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Logout
        res = self.client.get('/auth/logout', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

    def test_student_routes(self):
        self.set_session_user('student1')
        student_endpoints = [
            '/student/dashboard',
            '/student/books',
            '/student/my-books',
            '/student/requests',
            '/student/reservations',
            '/student/wishlist',
            '/student/recommendations',
            '/student/analytics',
            '/student/digital-library',
            '/student/digital-card',
            '/student/library-map',
            '/student/notifications',
            '/student/profile',
        ]
        for ep in student_endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 200, f"Failed endpoint: {ep}")

    def test_librarian_routes(self):
        self.set_session_user('librarian1')
        librarian_endpoints = [
            '/librarian/dashboard',
            '/librarian/books',
            '/librarian/books/add',
            '/librarian/requests',
            '/librarian/issue',
            '/librarian/return',
            '/librarian/fines',
            '/librarian/authors',
            '/librarian/categories',
            '/librarian/publishers',
            '/librarian/locations',
            '/librarian/digital-resources',
            '/librarian/announcements',
            '/librarian/reports',
            '/librarian/email-logs',
            '/librarian/audit-logs',
        ]
        for ep in librarian_endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 200, f"Failed endpoint: {ep}")

    def test_admin_routes(self):
        self.set_session_user('admin')
        admin_endpoints = [
            '/admin/dashboard',
            '/admin/users',
            '/admin/ml-demand',
            '/admin/acquisition-insights',
            '/admin/settings',
            '/admin/search-history',
        ]
        for ep in admin_endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 200, f"Failed endpoint: {ep}")

if __name__ == '__main__':
    unittest.main()
