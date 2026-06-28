from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import os
import json
import sqlite3
import threading
from loguru import logger

class MemoryStore(ABC):
    """
    Abstract Base Class for memory key-value storage.
    """
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def put(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def keys(self) -> List[str]:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def save(self) -> None:
        pass

class InMemoryStore(MemoryStore):
    """
    Thread-safe in-memory memory storage implementation.
    """
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._data.get(key)

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._data.keys())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def save(self) -> None:
        pass

class JSONStore(InMemoryStore):
    """
    Thread-safe filesystem JSON storage extension of InMemoryStore.
    """
    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path
        self._load_from_file()

    def _load_from_file(self) -> None:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        self._data = json.loads(content)
                        logger.info(f"Loaded {len(self._data)} keys from JSON storage file '{self.file_path}'.")
            except Exception as e:
                logger.error(f"Failed to load JSON storage file '{self.file_path}': {str(e)}")

    def save(self) -> None:
        with self._lock:
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(self.file_path)), exist_ok=True)
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
                logger.debug(f"Saved JSON storage file '{self.file_path}'.")
            except Exception as e:
                logger.error(f"Failed to save JSON storage file '{self.file_path}': {str(e)}")

    def put(self, key: str, value: Any) -> None:
        super().put(key, value)
        self.save()

    def delete(self, key: str) -> None:
        super().delete(key)
        self.save()

    def clear(self) -> None:
        super().clear()
        self.save()

class SQLiteStore(MemoryStore):
    """
    Thread-safe SQLite-backed KV storage implementation.
    """
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memory_kv (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM memory_kv WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
            except Exception as e:
                logger.error(f"SQLiteStore get failed for key '{key}': {str(e)}")
                return None
            finally:
                conn.close()

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                val_str = json.dumps(value, ensure_ascii=False)
                cursor.execute("INSERT OR REPLACE INTO memory_kv (key, value) VALUES (?, ?)", (key, val_str))
                conn.commit()
            except Exception as e:
                logger.error(f"SQLiteStore put failed for key '{key}': {str(e)}")
            finally:
                conn.close()

    def delete(self, key: str) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memory_kv WHERE key = ?", (key,))
                conn.commit()
            except Exception as e:
                logger.error(f"SQLiteStore delete failed for key '{key}': {str(e)}")
            finally:
                conn.close()

    def keys(self) -> List[str]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT key FROM memory_kv")
                rows = cursor.fetchall()
                return [row[0] for row in rows]
            except Exception as e:
                logger.error(f"SQLiteStore keys failed: {str(e)}")
                return []
            finally:
                conn.close()

    def clear(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memory_kv")
                conn.commit()
            except Exception as e:
                logger.error(f"SQLiteStore clear failed: {str(e)}")
            finally:
                conn.close()

    def save(self) -> None:
        pass

