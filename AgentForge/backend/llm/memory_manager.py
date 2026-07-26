import tiktoken
import uuid
import sqlite3
import os
from typing import List, Dict, Any
from config import BASE_DIR

DB_PATH = BASE_DIR / "agentforge.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        role TEXT,
        content TEXT,
        reasoning TEXT,
        sources TEXT,
        context TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )''')
    
    # Try adding columns in case the table already exists
    try:
        c.execute("ALTER TABLE messages ADD COLUMN sources TEXT")
        c.execute("ALTER TABLE messages ADD COLUMN context TEXT")
    except sqlite3.OperationalError:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS chunks (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        text TEXT,
        source TEXT,
        agent_name TEXT,
        timestamp REAL,
        embedding BLOB,
        FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )''')
    conn.commit()
    conn.close()

init_db()

class MemoryManager:
    def __init__(self, max_history_tokens: int = 2000):
        self.max_history_tokens = max_history_tokens
        self.encoder = tiktoken.get_encoding("cl100k_base")
        
    def add_message(self, session_id: str, role: str, content: str, reasoning: str = "", sources: str = "", context: str = ""):
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO sessions (id, title) VALUES (?, ?)", (session_id, "New Session"))
        msg_id = str(uuid.uuid4())
        c.execute("INSERT INTO messages (id, session_id, role, content, reasoning, sources, context) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (msg_id, session_id, role, content, reasoning, sources, context))
        
        if role == "user":
            c.execute("SELECT count(*) as c FROM messages WHERE session_id=? AND role='user'", (session_id,))
            if c.fetchone()['c'] == 1:
                title = content[:30] + "..." if len(content) > 30 else content
                c.execute("UPDATE sessions SET title=? WHERE id=?", (title, session_id))
        
        conn.commit()
        conn.close()

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY created_at ASC", (session_id,))
        rows = c.fetchall()
        conn.close()
        
        history = []
        total_tokens = 0
        for row in reversed(rows):
            content = row['content']
            role = row['role']
            tokens = len(self.encoder.encode(content))
            if total_tokens + tokens > self.max_history_tokens:
                break
            history.insert(0, {"role": role, "content": content})
            total_tokens += tokens
            
        return history
        
    def get_all_messages(self, session_id: str):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, role, content, reasoning, sources, context FROM messages WHERE session_id=? ORDER BY created_at ASC", (session_id,))
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_sessions(self):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, title, created_at FROM sessions ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def clear_session(self, session_id: str):
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        # Deleted explicitly: sqlite3 leaves PRAGMA foreign_keys off by default, so the
        # ON DELETE CASCADE declared on chunks never fired. Every embedding from every
        # deleted session stayed in the file forever.
        c.execute("DELETE FROM chunks WHERE session_id=?", (session_id,))
        c.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()
        conn.close()

memory_manager = MemoryManager()
