"""SQLite-backed storage for FHIR resources (versioned)."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone


class Store:
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS resources (
                 type TEXT, id TEXT, version INTEGER, body TEXT,
                 PRIMARY KEY (type, id))"""
        )

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _stamp(self, res, rid, version):
        res["id"] = rid
        res["meta"] = {"versionId": str(version), "lastUpdated": self._now()}
        return res

    def create(self, rtype, res, rid=None):
        rid = rid or str(uuid.uuid4())
        res = self._stamp(dict(res), rid, 1)
        self.conn.execute("INSERT INTO resources VALUES (?,?,?,?)",
                          (rtype, rid, 1, json.dumps(res)))
        self.conn.commit()
        return res

    def read(self, rtype, rid):
        row = self.conn.execute(
            "SELECT body FROM resources WHERE type=? AND id=?", (rtype, rid)).fetchone()
        return json.loads(row[0]) if row else None

    def update(self, rtype, rid, res):
        """Returns (resource, created_flag)."""
        row = self.conn.execute(
            "SELECT version FROM resources WHERE type=? AND id=?", (rtype, rid)).fetchone()
        if not row:
            return self.create(rtype, res, rid), True
        version = row[0] + 1
        res = self._stamp(dict(res), rid, version)
        self.conn.execute("UPDATE resources SET version=?, body=? WHERE type=? AND id=?",
                          (version, json.dumps(res), rtype, rid))
        self.conn.commit()
        return res, False

    def delete(self, rtype, rid):
        cur = self.conn.execute("DELETE FROM resources WHERE type=? AND id=?", (rtype, rid))
        self.conn.commit()
        return cur.rowcount > 0

    def all(self, rtype):
        rows = self.conn.execute("SELECT body FROM resources WHERE type=?", (rtype,))
        return [json.loads(r[0]) for r in rows]
