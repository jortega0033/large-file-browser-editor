import os
import sqlite3
import tempfile
import unittest

from line_editor import storage
from line_editor.storage import (
    DocumentLimit,
    NotFound,
    RevisionConflict,
    SchemaTooNew,
    Store,
    StoreError,
)
from line_editor.validation import MAX_DOCUMENTS


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def test_migration_idempotent(self):
        s1 = Store(self.dir)
        doc = s1.create_document("a", "b")
        s2 = Store(self.dir)
        self.assertEqual(s2.user_version(), 1)
        self.assertEqual(s2.get_document(doc["id"])["text"], "b")
        Store(self.dir)
        self.assertEqual(len(s2.list_documents()), 1)

    def test_creates_missing_data_dir(self):
        nested = os.path.join(self.dir, "a", "b")
        Store(nested)
        self.assertTrue(os.path.exists(os.path.join(nested, storage.DB_NAME)))

    def test_newer_schema_refused(self):
        path = os.path.join(self.dir, storage.DB_NAME)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA user_version=2")
        conn.close()
        with self.assertRaises(SchemaTooNew):
            Store(self.dir)

    def test_corrupt_file_refused(self):
        with open(os.path.join(self.dir, storage.DB_NAME), "wb") as f:
            f.write(b"this is definitely not a sqlite database" * 50)
        with self.assertRaises(StoreError):
            Store(self.dir)

    def test_bad_data_dirs(self):
        with self.assertRaises(StoreError):
            Store("")
        file_path = os.path.join(self.dir, "afile")
        with open(file_path, "w") as f:
            f.write("x")
        with self.assertRaises(StoreError):
            Store(file_path)

    def test_crud_and_revision(self):
        s = Store(self.dir)
        d = s.create_document("t", "line1\r\nline2\n")
        self.assertEqual((d["revision"], d["size_bytes"]), (1, 13))
        self.assertEqual(s.get_document(d["id"])["text"], "line1\r\nline2\n")
        u = s.update_document(d["id"], "t2", "é", 1)
        self.assertEqual((u["revision"], u["title"], u["size_bytes"]), (2, "t2", 2))
        with self.assertRaises(RevisionConflict) as cm:
            s.update_document(d["id"], "t3", "zzz", 1)
        self.assertEqual(cm.exception.current["revision"], 2)
        self.assertEqual(s.get_document(d["id"])["text"], "é")  # unchanged
        with self.assertRaises(NotFound):
            s.update_document(9999, "t", "x", 1)
        with self.assertRaises(NotFound):
            s.get_document(9999)

    def test_list_order_and_no_text(self):
        s = Store(self.dir)
        a = s.create_document("a", "1")
        b = s.create_document("b", "2")
        s.update_document(a["id"], "a", "11", 1)
        listing = s.list_documents()
        self.assertEqual([d["id"] for d in listing], [a["id"], b["id"]])
        self.assertNotIn("text", listing[0])
        self.assertEqual(listing[0]["size_bytes"], 2)

    def test_document_limit_and_recovery(self):
        s = Store(self.dir)
        for i in range(MAX_DOCUMENTS):
            s.create_document(f"d{i}", "")
        with self.assertRaises(DocumentLimit):
            s.create_document("extra", "")
        self.assertEqual(len(s.list_documents()), MAX_DOCUMENTS)
        # The failed insert must not leave a transaction or lock behind.
        s.update_document(1, "renamed", "x", 1)

    def test_db_check_constraints(self):
        s = Store(self.dir)
        with self.assertRaises(sqlite3.IntegrityError):
            s.create_document("", "x")
        with self.assertRaises(sqlite3.IntegrityError):
            s.create_document("t", "a" * 262145)


if __name__ == "__main__":
    unittest.main()
