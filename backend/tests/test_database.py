import importlib
import os
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import Mock


class FacultyCatalogueTests(TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
        cls.database = importlib.import_module("backend.app.database")

    def test_startup_sync_renames_existing_rows_seeds_roster_and_removes_stale_rows(self):
        connection = Mock()

        @contextmanager
        def begin():
            yield connection

        db_engine = Mock()
        db_engine.begin.side_effect = begin

        self.database.initialize_faculty_table(db_engine)

        self.assertEqual(len(self.database.FACULTY_SEED), 41)
        self.assertEqual(len(set(self.database.FACULTY_SEED)), 41)
        self.assertEqual(
            connection.execute.call_count,
            1 + len(self.database.FACULTY_RENAMES) + len(self.database.FACULTY_SEED) + 1,
        )

        rename_calls = connection.execute.call_args_list[
            1:1 + len(self.database.FACULTY_RENAMES)
        ]
        renamed_pairs = [
            (call.args[1]["previous_name"], call.args[1]["official_name"])
            for call in rename_calls
        ]
        self.assertEqual(renamed_pairs, list(self.database.FACULTY_RENAMES.items()))

        delete_statement, delete_params = connection.execute.call_args_list[-1].args
        self.assertIn("DELETE FROM faculty WHERE name NOT IN", str(delete_statement))
        self.assertEqual(delete_params["faculty_names"], self.database.FACULTY_SEED)
