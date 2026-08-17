import os
import json
import logging
import threading
import contextlib
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("ai_os.postgres")

class PostgresClient:
    """
    Manages connections and operations on PostgreSQL for relational storage.
    Automatically falls back to an SQLite in-memory database with fully seeded
    analytical data if PostgreSQL is not available.
    """
    def __init__(self, dsn: Optional[str] = None):
        if not dsn:
            dsn = os.getenv("DATABASE_URL", "")
        if not dsn:
            try:
                from backend.config import settings
                dsn = settings.DATABASE_URL
            except Exception:
                dsn = ""
        self.dsn = dsn or None
        self.conn = None
        self.is_mocked = False
        self._write_lock = threading.Lock()
        self.connect()

    def connect(self):
        try:
            self.conn = psycopg2.connect(self.dsn)
            self.conn.autocommit = True
            logger.info("Connected to PostgreSQL successfully.")
            self.is_mocked = False
            self.initialize_tables()
            
            # Seed PostgreSQL
            from database.seed_data import seed_database
            seed_database(self.conn, is_sqlite=False)
        except Exception as e:
            logger.warning(f"Failed to connect to PostgreSQL: {e}. Falling back to SQLite In-Memory database.")
            self.is_mocked = True
            try:
                import sqlite3
                from backend.config import settings
                db_dir = settings.storage_dir
                os.makedirs(db_dir, exist_ok=True)
                db_path = os.path.join(db_dir, "ai_os.db")
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self.conn.execute("PRAGMA journal_mode=WAL")
                self.conn.execute("PRAGMA synchronous=NORMAL")
                self.conn.execute("PRAGMA cache_size=-64000")
                self.conn.commit()
                self.initialize_sqlite_tables()
            except Exception as se:
                logger.error(f"Failed to initialize SQLite fallback connection: {se}")

    def initialize_tables(self):
        create_queries = [
            """
            CREATE TABLE IF NOT EXISTS conversations (
                session_id VARCHAR(255) PRIMARY KEY,
                phone_number VARCHAR(50) NOT NULL,
                messages JSONB DEFAULT '[]'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                phone_number VARCHAR(50) NOT NULL,
                memory_key VARCHAR(255) NOT NULL,
                memory_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (phone_number, memory_key)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                description TEXT NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                assigned_to VARCHAR(100),
                priority VARCHAR(20) DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                phone_number VARCHAR(50),
                action VARCHAR(255) NOT NULL,
                details JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,

            """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id SERIAL PRIMARY KEY,
                topic VARCHAR(100) NOT NULL,
                document_type VARCHAR(50) DEFAULT 'general',
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                source VARCHAR(255) NOT NULL DEFAULT 'auto',
                confidence REAL NOT NULL DEFAULT 0.7,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (question)
            );
            """
        ]
        alter_queries = [
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'medium';",
            "ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS document_type VARCHAR(50) DEFAULT 'general';",
        ]
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at);",
            "CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
            "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);",
            "CREATE INDEX IF NOT EXISTS idx_knowledge_base_topic ON knowledge_base(topic);",
            "CREATE INDEX IF NOT EXISTS idx_knowledge_base_document_type ON knowledge_base(document_type);",
            "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            "CREATE INDEX IF NOT EXISTS idx_kb_question_trgm ON knowledge_base USING gin(question gin_trgm_ops);",
        ]
        try:
            with self.conn.cursor() as cur:
                for query in create_queries:
                    cur.execute(query)
                for query in alter_queries:
                    cur.execute(query)
                for query in index_queries:
                    cur.execute(query)
            logger.info("Relational PostgreSQL tables initialized.")
        except Exception as e:
            logger.error(f"Error initializing tables: {e}. Switching to mocked mode.")
            self.is_mocked = True

    def initialize_sqlite_tables(self):
        create_queries = [
            """
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY,
                phone_number TEXT NOT NULL,
                messages TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                phone_number TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (phone_number, memory_key)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                assigned_to TEXT,
                priority TEXT DEFAULT 'medium',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT,
                action TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """,

            """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                document_type TEXT DEFAULT 'general',
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                source TEXT DEFAULT 'auto',
                confidence REAL DEFAULT 0.7,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (question)
            );
            """
        ]
        alter_queries = [
            "ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'medium';",
            "ALTER TABLE knowledge_base ADD COLUMN document_type TEXT DEFAULT 'general';",
        ]
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at);",
            "CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
            "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);",
            "CREATE INDEX IF NOT EXISTS idx_knowledge_base_topic ON knowledge_base(topic);",
            "CREATE INDEX IF NOT EXISTS idx_knowledge_base_document_type ON knowledge_base(document_type);",
        ]
        fts_queries = [
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_base_fts USING fts5(
                question, answer, topic,
                content='knowledge_base',
                content_rowid='id'
            );
            """,
            """
            CREATE TRIGGER IF NOT EXISTS kb_ai AFTER INSERT ON knowledge_base BEGIN
                INSERT INTO knowledge_base_fts(rowid, question, answer, topic)
                VALUES (new.id, new.question, new.answer, new.topic);
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS kb_ad AFTER DELETE ON knowledge_base BEGIN
                INSERT INTO knowledge_base_fts(knowledge_base_fts, rowid, question, answer, topic)
                VALUES ('delete', old.id, old.question, old.answer, old.topic);
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS kb_au AFTER UPDATE ON knowledge_base BEGIN
                INSERT INTO knowledge_base_fts(knowledge_base_fts, rowid, question, answer, topic)
                VALUES ('delete', old.id, old.question, old.answer, old.topic);
                INSERT INTO knowledge_base_fts(rowid, question, answer, topic)
                VALUES (new.id, new.question, new.answer, new.topic);
            END;
            """,
        ]
        try:
            cur = self.conn.cursor()
            for query in create_queries:
                cur.execute(query)
            for query in alter_queries:
                try:
                    cur.execute(query)
                except Exception:
                    pass  # Column already exists
            for query in index_queries:
                cur.execute(query)
            for query in fts_queries:
                cur.execute(query)
            self.conn.commit()
            
            # Seed SQLite DB
            from database.seed_data import seed_database
            seed_database(self.conn, is_sqlite=True)
            logger.info("SQLite fallback tables initialized and seeded.")
        except Exception as e:
            logger.error(f"Error initializing SQLite tables: {e}")

    # Generic execution wrapper to support SQL compatibility
    def ping(self) -> bool:
        """Return True if the database is reachable."""
        row = self._execute("SELECT 1 AS ok;", (), fetch="one")
        return bool(row)

    def _execute(self, sql: str, params: tuple = (), fetch: str = None) -> Any:
        if self.is_mocked:
            sql = sql.replace("%s", "?")
            sql = sql.replace("CURRENT_TIMESTAMP", "datetime('now')")
            sql = sql.replace("ON CONFLICT (session_id) DO UPDATE SET messages = EXCLUDED.messages, updated_at = CURRENT_TIMESTAMP", 
                              "ON CONFLICT(session_id) DO UPDATE SET messages=excluded.messages, updated_at=datetime('now')")
            sql = sql.replace("ON CONFLICT (phone_number, memory_key) DO UPDATE SET memory_value = EXCLUDED.memory_value, updated_at = CURRENT_TIMESTAMP",
                              "ON CONFLICT(phone_number, memory_key) DO UPDATE SET memory_value=excluded.memory_value, updated_at=datetime('now')")
            returning_insert = "RETURNING id" in sql
            sql = sql.replace("RETURNING id", "")

            # SQLite is single-writer; serialize concurrent WRITES to avoid
            # "database is locked" errors during chat streaming + telemetry.
            # Reads acquire a shared lock; writes acquire the exclusive lock.
            is_write = not fetch
            lock = self._write_lock if is_write else contextlib.nullcontext()
            with lock:
                try:
                    cur = self.conn.cursor()
                    cur.execute(sql, params)
                    if is_write:
                        self.conn.commit()
                    if fetch == "one":
                        row = cur.fetchone()
                        return dict(row) if row else None
                    elif fetch == "all":
                        rows = cur.fetchall()
                        return [dict(r) for r in rows]
                    elif returning_insert:
                        return cur.lastrowid
                    return None
                except Exception as e:
                    logger.error(f"SQLite error running: {sql}. Error: {e}")
                    return None
        else:
            try:
                cursor_factory = RealDictCursor if fetch else None
                with self.conn.cursor(cursor_factory=cursor_factory) as cur:
                    cur.execute(sql, params)
                    if fetch == "one":
                        return cur.fetchone()
                    elif fetch == "all":
                        return cur.fetchall()
                    elif "RETURNING" in sql:
                        row = cur.fetchone()
                        return row[0] if row else None
                    return None
            except Exception as e:
                logger.error(f"Postgres error running: {sql}. Error: {e}")
                return None

    # Conversation queries
    def get_chat_sessions(self, limit: int = 25) -> List[Dict[str, Any]]:
        sql = "SELECT session_id, updated_at, messages FROM conversations ORDER BY updated_at DESC LIMIT %s;"
        rows = self._execute(sql, (limit,), fetch="all") or []
        sessions = []
        for row in rows:
            messages = json.loads(row["messages"]) if isinstance(row["messages"], str) else row["messages"]
            title = "New Session"
            if messages and len(messages) > 0:
                first_msg = messages[0].get("content", "")
                title = first_msg[:30] + "..." if len(first_msg) > 30 else first_msg
            sessions.append({
                "id": row["session_id"],
                "title": title,
                "time": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else str(row["updated_at"])
            })
        return sessions

    def get_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT messages FROM conversations WHERE session_id = %s;"
        row = self._execute(sql, (session_id,), fetch="one")
        if row:
            msg_data = row["messages"]
            return json.loads(msg_data) if isinstance(msg_data, str) else msg_data
        return []

    def save_conversation(self, session_id: str, phone_number: str, messages: List[Dict[str, Any]]):
        sql = """
            INSERT INTO conversations (session_id, phone_number, messages, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (session_id)
            DO UPDATE SET messages = EXCLUDED.messages, updated_at = CURRENT_TIMESTAMP;
        """
        self._execute(sql, (session_id, phone_number, json.dumps(messages)))

    def save_user_message(self, session_id: str, phone_number: str, content: str):
        """Persist a user message immediately so it survives errors/disconnects.

        Idempotent: won't duplicate the same message if the request is retried.
        """
        existing = self.get_conversation(session_id) or []
        if existing and existing[-1].get("role") == "user" and existing[-1].get("content") == content:
            return
        existing.append({"role": "user", "content": content})
        self.save_conversation(session_id, phone_number, existing)

    def append_conversation(self, session_id: str, phone_number: str, new_messages: List[Dict[str, Any]]):
        """Append messages to an existing conversation (e.g. the assistant reply)."""
        existing = self.get_conversation(session_id) or []
        existing.extend(new_messages)
        self.save_conversation(session_id, phone_number, existing)

    # User memory queries
    def get_user_memories(self, phone_number: str) -> Dict[str, str]:
        sql = "SELECT memory_key, memory_value FROM user_memories WHERE phone_number = %s;"
        rows = self._execute(sql, (phone_number,), fetch="all")
        if rows:
            return {row["memory_key"]: row["memory_value"] for row in rows}
        return {}

    def save_user_memory(self, phone_number: str, key: str, value: str):
        sql = """
            INSERT INTO user_memories (phone_number, memory_key, memory_value, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (phone_number, memory_key)
            DO UPDATE SET memory_value = EXCLUDED.memory_value, updated_at = CURRENT_TIMESTAMP;
        """
        self._execute(sql, (phone_number, key, value))

    # Tasks queries
    def create_task(self, description: str, assigned_to: Optional[str] = None) -> int:
        sql = "INSERT INTO tasks (description, assigned_to) VALUES (%s, %s) RETURNING id;"
        res = self._execute(sql, (description, assigned_to))
        return res if res is not None else -1

    def list_tasks(self) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM tasks ORDER BY created_at DESC;"
        return self._execute(sql, (), fetch="all") or []

    # Audit Logs
    def log_audit(self, phone_number: Optional[str], action: str, details: Dict[str, Any]):
        sql = "INSERT INTO audit_logs (phone_number, action, details) VALUES (%s, %s, %s);"
        self._execute(sql, (phone_number, action, json.dumps(details)))



    # Knowledge base (idle self-improvement / fast answers)
    def add_knowledge(self, topic: str, question: str, answer: str,
                      source: str = "auto", confidence: float = 0.7):
        sql = """
            INSERT INTO knowledge_base (topic, question, answer, source, confidence)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (question) DO UPDATE SET
                answer = EXCLUDED.answer, topic = EXCLUDED.topic,
                confidence = EXCLUDED.confidence, source = EXCLUDED.source;
        """
        self._execute(sql, (topic, question, answer, source, confidence))

    def search_knowledge(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        if self.is_mocked:
            sql = """
                SELECT question, answer, topic, source, confidence
                FROM knowledge_base_fts
                WHERE knowledge_base_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
            """
            results = self._execute(sql, (query, limit), fetch="all") or []
            if not results:
                sql = """
                    SELECT question, answer, topic, source, confidence
                    FROM knowledge_base
                    WHERE LOWER(question) LIKE LOWER(?)
                    ORDER BY confidence DESC LIMIT ?;
                """
                results = self._execute(sql, (f"%{query}%", limit), fetch="all") or []
            return results
        else:
            sql = """
                SELECT question, answer, topic, source, confidence
                FROM knowledge_base
                WHERE question %% %s
                ORDER BY similarity(question, %s) DESC, confidence DESC
                LIMIT %s;
            """
            results = self._execute(sql, (query, query, limit), fetch="all") or []
            if not results:
                sql = """
                    SELECT question, answer, topic, source, confidence
                    FROM knowledge_base
                    WHERE LOWER(question) LIKE LOWER(%s)
                    ORDER BY confidence DESC LIMIT %s;
                """
                results = self._execute(sql, (f"%{query}%", limit), fetch="all") or []
            return results

    def knowledge_count(self) -> int:
        sql = "SELECT COUNT(*) AS c FROM knowledge_base;"
        row = self._execute(sql, (), fetch="one")
        return int(row["c"]) if row else 0

    def count_tasks(self) -> int:
        sql = "SELECT COUNT(*) AS c FROM tasks WHERE status != 'completed';"
        row = self._execute(sql, (), fetch="one")
        if row is None:
            return 0
        val = row.get("c") if isinstance(row, dict) else row[0]
        return int(val)

    def count_documents(self) -> int:
        sql = "SELECT COUNT(*) AS c FROM knowledge_base;"
        row = self._execute(sql, (), fetch="one")
        if row is None:
            return 0
        val = row.get("c") if isinstance(row, dict) else row[0]
        return int(val)

    # Analytical Table Queries
    ALLOWED_TABLES = frozenset([
        "production_logs", "department_budgets", "equipment_status", "sops",
        "conversations", "user_memories", "tasks", "audit_logs"
    ])

    ALLOWED_COLUMNS = frozenset([
        "id", "session_id", "phone_number", "messages", "created_at", "updated_at",
        "memory_key", "memory_value", "description", "status", "assigned_to",
        "action", "details", "date", "shift", "shaft", "tons_milled",
        "head_grade_cu", "recovery_rate", "concentrate_produced",
        "department", "fiscal_year", "budget_allocated", "actual_spend",
        "variance", "budget_status",
        "equipment_id", "type", "operating_hours", "engine_temp_c",
        "oil_pressure_psi", "next_service", "tire_pressure_psi",
        "hydraulic_fluid_pct", "sensor_readings",
        "topic", "content", "version"
    ])

    def query_table(self, table_name: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Generic getter for seeded tables (production_logs, department_budgets, equipment_status, sops).
        Uses allowlists to prevent SQL injection.
        """
        if table_name not in self.ALLOWED_TABLES:
            logger.warning(f"Blocked query to non-allowed table: {table_name}")
            return []

        safe_table = f'"{table_name}"'
        sql = f"SELECT * FROM {safe_table}"
        params = []
        if filters:
            conditions = []
            for col, val in filters.items():
                if col not in self.ALLOWED_COLUMNS:
                    logger.warning(f"Blocked query to non-allowed column: {col}")
                    continue
                conditions.append(f'"{col}" = %s')
                params.append(val)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
        sql += ";"
        return self._execute(sql, tuple(params), fetch="all") or []
