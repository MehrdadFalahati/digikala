from django.db import connection
from django.test import TestCase


class DatabaseBackendTests(TestCase):
    def test_database_is_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone(), (1,))
