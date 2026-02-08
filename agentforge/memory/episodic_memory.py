import sqlite3
import json
import os
from datetime import datetime

class EpisodicMemory:
    def __init__(self, db_path="agentforge/data/episodic_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS research_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                result TEXT,
                timestamp DATETIME,
                metadata TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_task(self, topic: str, result: str, metadata: dict = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO research_tasks (topic, result, timestamp, metadata) VALUES (?, ?, ?, ?)',
            (topic, result, datetime.now(), json.dumps(metadata or {}))
        )
        conn.commit()
        conn.close()

    def get_similar_tasks(self, topic: str, limit=3):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT topic, result, timestamp FROM research_tasks WHERE topic LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{topic}%", limit)
        )
        results = cursor.fetchall()
        conn.close()
        return [{"topic": r[0], "result": r[1], "timestamp": r[2]} for r in results]
