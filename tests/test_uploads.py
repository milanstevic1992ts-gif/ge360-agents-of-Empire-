from pathlib import Path
import tempfile
import unittest

import ge360_agent.uploads as uploads


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = uploads.DB
        self.old_inbox = uploads.INBOX
        uploads.DB = Path(self.tmp.name) / "runtime.sqlite3"
        uploads.INBOX = Path(self.tmp.name) / "inbox"
        with uploads._connect() as conn:
            conn.execute(
                """
                CREATE TABLE uploaded_files (
                    id TEXT PRIMARY KEY,
                    uploaded_at TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()

    def tearDown(self):
        uploads.DB = self.old_db
        uploads.INBOX = self.old_inbox
        self.tmp.cleanup()

    def test_safe_filename_and_extensions(self):
        self.assertEqual(uploads.safe_filename("../../lista contatti.csv"), "lista contatti.csv")
        self.assertTrue(uploads.extension_allowed("lista.csv"))
        self.assertTrue(uploads.extension_allowed("lista.xlsx"))
        self.assertFalse(uploads.extension_allowed("script.sh"))

    def test_register_and_resolve_file(self):
        folder = uploads.INBOX / "abc"
        folder.mkdir(parents=True)
        path = folder / "lista.csv"
        path.write_text("nome,email\nMario,mario@example.com\n", encoding="utf-8")
        uploads.register_file("abc", "lista.csv", path, path.stat().st_size, "deadbeef", "text/csv")
        resolved = uploads.resolve_files(["abc"])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["original_name"], "lista.csv")


if __name__ == "__main__":
    unittest.main()
