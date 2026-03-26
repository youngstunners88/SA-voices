"""Storage backends for state management"""

import json
import sqlite3
from abc import ABC, abstractmethod
from typing import Any, List, Optional
from pathlib import Path


class StorageBackend(ABC):
    """Abstract storage backend"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value with optional TTL"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass
    
    @abstractmethod
    async def list_keys(self, pattern: str) -> List[str]:
        """List keys matching pattern"""
        pass


class RedisStorage(StorageBackend):
    """Redis storage backend"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis = None
    
    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = await redis.from_url(self.redis_url)
        return self._redis
    
    async def get(self, key: str) -> Optional[str]:
        r = await self._get_redis()
        value = await r.get(key)
        return value.decode() if value else None
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        r = await self._get_redis()
        await r.set(key, value, ex=ttl)
        return True
    
    async def delete(self, key: str) -> bool:
        r = await self._get_redis()
        return await r.delete(key) > 0
    
    async def exists(self, key: str) -> bool:
        r = await self._get_redis()
        return await r.exists(key) > 0
    
    async def list_keys(self, pattern: str) -> List[str]:
        r = await self._get_redis()
        keys = []
        async for key in r.scan_iter(match=f"{pattern}*"):
            keys.append(key.decode())
        return keys


class SQLiteStorage(StorageBackend):
    """SQLite storage backend for local development"""
    
    def __init__(self, db_path: str = "./data/sa_voices_state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires ON state_store(expires_at)
            """)
            conn.commit()
    
    async def get(self, key: str) -> Optional[str]:
        with sqlite3.connect(str(self.db_path)) as conn:
            # Clean expired entries first
            conn.execute("DELETE FROM state_store WHERE expires_at < datetime('now')")
            
            cursor = conn.execute(
                "SELECT value FROM state_store WHERE key = ? AND (expires_at IS NULL OR expires_at > datetime('now'))",
                (key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        import datetime
        
        expires_at = None
        if ttl:
            expires_at = (datetime.datetime.now() + 
                         datetime.timedelta(seconds=ttl)).isoformat()
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO state_store (key, value, expires_at) 
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   expires_at = excluded.expires_at""",
                (key, value, expires_at)
            )
            conn.commit()
        return True
    
    async def delete(self, key: str) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("DELETE FROM state_store WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0
    
    async def exists(self, key: str) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM state_store WHERE key = ? AND (expires_at IS NULL OR expires_at > datetime('now'))",
                (key,)
            )
            return cursor.fetchone() is not None
    
    async def list_keys(self, pattern: str) -> List[str]:
        # Convert simple wildcard to SQL LIKE
        like_pattern = pattern.replace("*", "%") + "%"
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT key FROM state_store WHERE key LIKE ?",
                (like_pattern,)
            )
            return [row[0] for row in cursor.fetchall()]


class FileStorage(StorageBackend):
    """File-based storage for simple deployments"""
    
    def __init__(self, base_path: str = "./data/state"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, key: str) -> Path:
        """Get file path for key, with simple sanitization"""
        # Replace problematic characters
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.base_path / f"{safe_key}.json"
    
    async def get(self, key: str) -> Optional[str]:
        path = self._get_path(key)
        if not path.exists():
            return None
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                # Check expiration
                if 'expires_at' in data and data['expires_at']:
                    import datetime
                    if datetime.datetime.fromisoformat(data['expires_at']) < datetime.datetime.now():
                        path.unlink()
                        return None
                return json.dumps(data['value'])
        except (json.JSONDecodeError, IOError):
            return None
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        import datetime
        
        path = self._get_path(key)
        expires_at = None
        if ttl:
            expires_at = (datetime.datetime.now() + 
                         datetime.timedelta(seconds=ttl)).isoformat()
        
        data = {
            'key': key,
            'value': json.loads(value),
            'expires_at': expires_at,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        with open(path, 'w') as f:
            json.dump(data, f)
        return True
    
    async def delete(self, key: str) -> bool:
        path = self._get_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        path = self._get_path(key)
        return path.exists()
    
    async def list_keys(self, pattern: str) -> List[str]:
        keys = []
        for f in self.base_path.glob("*.json"):
            key = f.stem.replace("_", ":")
            if key.startswith(pattern.replace("*", "")):
                keys.append(key)
        return keys
