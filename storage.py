"""Local transactional state, one explicit namespace per user."""
import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def load(self, user='local'):
        row = self.db.execute('SELECT payload FROM sessions WHERE id=?', (user,)).fetchone()
        if not row:
            return {}
        data = json.loads(row[0])
        if data['version'] != 1:
            raise ValueError('Неподдерживаемая версия сохранённого диалога')
        return data['state']

    def save(self, state, user='local'):
        payload = json.dumps({'version': 1, 'state': state}, ensure_ascii=False)
        with self.db:
            self.db.execute('INSERT INTO sessions VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (user, payload))

    def close(self):
        self.db.close()
