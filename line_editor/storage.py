"""SQLite persistence. One connection per operation; ordered migrations."""

import contextlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from .validation import MAX_DOCUMENTS

DB_NAME = "line_editor.sqlite3"
SCHEMA_VERSION = 1

# Ordered, deterministic migrations: (target user_version, statements).
MIGRATIONS = [
    (
        1,
        [
            """CREATE TABLE documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
  text TEXT NOT NULL CHECK (length(CAST(text AS BLOB)) <= 262144),
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)""",
            "CREATE INDEX documents_updated ON documents (updated_at DESC, id DESC)",
        ],
    ),
]

_SUMMARY_COLS = (
    "id, title, revision, length(CAST(text AS BLOB)) AS size_bytes, "
    "created_at, updated_at"
)
_FULL_COLS = (
    "id, title, text, revision, length(CAST(text AS BLOB)) AS size_bytes, "
    "created_at, updated_at"
)


class StoreError(Exception):
    """The data directory or database cannot be used."""


class SchemaTooNew(StoreError):
    pass


class NotFound(Exception):
    pass


class DocumentLimit(Exception):
    pass


class RevisionConflict(Exception):
    def __init__(self, current):
        super().__init__("revision conflict")
        self.current = current


_STAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _now():
    return datetime.now(timezone.utc).strftime(_STAMP_FORMAT)


def _next_stamp(conn):
    """Timestamp strictly greater than any stored one; call inside the write transaction."""
    now = _now()
    prev = conn.execute("SELECT max(updated_at) FROM documents").fetchone()[0]
    if prev is not None and now <= prev:
        bumped = datetime.strptime(prev, _STAMP_FORMAT) + timedelta(microseconds=1)
        now = bumped.strftime(_STAMP_FORMAT)
    return now


def _row_to_doc(row, with_text):
    doc = {"id": row["id"], "title": row["title"]}
    if with_text:
        doc["text"] = row["text"]
    doc["revision"] = row["revision"]
    doc["size_bytes"] = row["size_bytes"]
    doc["created_at"] = row["created_at"]
    doc["updated_at"] = row["updated_at"]
    return doc


class Store:
    def __init__(self, data_dir):
        if not isinstance(data_dir, str) or data_dir == "":
            raise StoreError("data directory must not be empty")
        try:
            os.makedirs(data_dir, exist_ok=True)
        except OSError as e:
            raise StoreError(
                f"cannot use data directory {data_dir!r}: {e.strerror or e}"
            ) from None
        if not os.path.isdir(data_dir):
            raise StoreError(f"data directory {data_dir!r} is not a directory")
        self.path = os.path.join(os.path.abspath(data_dir), DB_NAME)
        self._migrate()

    @contextlib.contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _rollback(conn):
        if conn.in_transaction:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass

    def _migrate(self):
        try:
            with self._conn() as conn:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                self._check_version(version)
                if version == SCHEMA_VERSION:
                    return
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # Re-check under the write lock: another process may have migrated.
                    version = conn.execute("PRAGMA user_version").fetchone()[0]
                    self._check_version(version)
                    for target, statements in MIGRATIONS:
                        if target > version:
                            for stmt in statements:
                                conn.execute(stmt)
                            conn.execute(f"PRAGMA user_version={int(target)}")
                    conn.execute("COMMIT")
                except BaseException:
                    self._rollback(conn)
                    raise
        except sqlite3.Error as e:
            raise StoreError(f"cannot open database {self.path!r}: {e}") from None

    @staticmethod
    def _check_version(version):
        if version > SCHEMA_VERSION:
            raise SchemaTooNew(
                f"database schema version {version} is newer than supported "
                f"version {SCHEMA_VERSION}"
            )

    def user_version(self):
        with self._conn() as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def list_documents(self):
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT {_SUMMARY_COLS} FROM documents "
                "ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [_row_to_doc(r, False) for r in rows]

    def get_document(self, doc_id):
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT {_FULL_COLS} FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        if row is None:
            raise NotFound()
        return _row_to_doc(row, True)

    def create_document(self, title, text):
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = _next_stamp(conn)
                count = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
                if count >= MAX_DOCUMENTS:
                    raise DocumentLimit()
                cur = conn.execute(
                    "INSERT INTO documents (title, text, revision, created_at, updated_at) "
                    "VALUES (?, ?, 1, ?, ?)",
                    (title, text, now, now),
                )
                row = conn.execute(
                    f"SELECT {_FULL_COLS} FROM documents WHERE id = ?",
                    (cur.lastrowid,),
                ).fetchone()
                conn.execute("COMMIT")
            except BaseException:
                self._rollback(conn)
                raise
        return _row_to_doc(row, True)

    def update_document(self, doc_id, title, text, base_revision):
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = _next_stamp(conn)
                cur = conn.execute(
                    "UPDATE documents SET title = ?, text = ?, "
                    "revision = revision + 1, updated_at = ? "
                    "WHERE id = ? AND revision = ?",
                    (title, text, now, doc_id, base_revision),
                )
                row = conn.execute(
                    f"SELECT {_FULL_COLS} FROM documents WHERE id = ?", (doc_id,)
                ).fetchone()
                if cur.rowcount == 0:
                    if row is None:
                        raise NotFound()
                    raise RevisionConflict(_row_to_doc(row, True))
                conn.execute("COMMIT")
            except BaseException:
                self._rollback(conn)
                raise
        return _row_to_doc(row, True)
