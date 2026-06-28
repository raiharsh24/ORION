import os
import tempfile
import pytest
import sqlite3
from unittest.mock import MagicMock

from app.memory.store import JSONStore, SQLiteStore
from app.memory.engine import MemoryEngine
from app.kernel import FridayKernel

def test_sqlite_store_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_store.db")
        store = SQLiteStore(db_path)
        
        # Initial check
        assert store.get("key1") is None
        assert store.keys() == []
        
        # Put & Get
        store.put("key1", {"name": "test", "value": 42})
        assert store.get("key1") == {"name": "test", "value": 42}
        assert store.keys() == ["key1"]
        
        # Put overwrite
        store.put("key1", "overwritten")
        assert store.get("key1") == "overwritten"
        
        # Delete
        store.delete("key1")
        assert store.get("key1") is None
        assert store.keys() == []
        
        # Clear
        store.put("k1", 1)
        store.put("k2", 2)
        assert sorted(store.keys()) == ["k1", "k2"]
        store.clear()
        assert store.keys() == []

def test_sqlite_store_restart_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_store.db")
        
        # Write to store 1
        store1 = SQLiteStore(db_path)
        store1.put("session_1", {"data": "foo"})
        
        # Open store 2 on same DB
        store2 = SQLiteStore(db_path)
        assert store2.get("session_1") == {"data": "foo"}

@pytest.mark.anyio
async def test_json_to_sqlite_migration(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "friday_memory.json")
        db_path = os.path.join(tmpdir, "friday_memory.db")
        
        # 1. Create a JSON store and seed it with data
        json_store = JSONStore(json_path)
        json_store.put("session:1", {"session_id": "1", "data": "migrated"})
        json_store.put("user:default", {"user_id": "default", "pref": "dark"})
        json_store.save()
        
        # Set environment and config for mock kernel
        monkeypatch.setenv("FRIDAY_USE_SQLITE", "true")
        
        # Mock FridayKernel
        kernel = FridayKernel.get_instance()
        
        # Save original config
        original_config = getattr(kernel, "_config", None)
        
        # Create a mock config with persist_dir pointing to our temp directory
        class MockPaths:
            persist_dir = tmpdir
        class MockConfig:
            paths = MockPaths()
            
        kernel._config = MockConfig()
        
        try:
            # Instantiate memory engine
            engine = MemoryEngine()
            await engine.initialize()
            
            # Check database persistence
            store = engine._manager._store
            assert isinstance(store, SQLiteStore)
            
            # Assert keys were migrated successfully
            assert store.get("session:1") == {"session_id": "1", "data": "migrated"}
            assert store.get("user:default") == {"user_id": "default", "pref": "dark"}
            
            # Clean shutdown
            await engine.shutdown()
        finally:
            kernel._config = original_config

@pytest.mark.anyio
async def test_migration_idempotency_and_fallback_safety(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "friday_memory.json")
        db_path = os.path.join(tmpdir, "friday_memory.db")
        
        # 1. Seed SQLite directly with a key
        db_store = SQLiteStore(db_path)
        db_store.put("session:1", {"data": "sqlite_original"})
        
        # 2. Seed JSON with same key but different value, and a new key
        json_store = JSONStore(json_path)
        json_store.put("session:1", {"data": "json_value"})
        json_store.put("session:2", {"data": "json_only"})
        json_store.save()
        
        monkeypatch.setenv("FRIDAY_USE_SQLITE", "true")
        kernel = FridayKernel.get_instance()
        original_config = getattr(kernel, "_config", None)
        
        class MockPaths:
            persist_dir = tmpdir
        class MockConfig:
            paths = MockPaths()
            
        kernel._config = MockConfig()
        
        try:
            # First, check IDEMPOTENCY: Since sqlite has keys, migration shouldn't overwrite or run
            engine = MemoryEngine()
            await engine.initialize()
            
            store = engine._manager._store
            assert isinstance(store, SQLiteStore)
            # The value should remain the original SQLite value
            assert store.get("session:1") == {"data": "sqlite_original"}
            # The JSON-only key should NOT have been migrated (because sqlite was not empty)
            assert store.get("session:2") is None
            
            await engine.shutdown()
            
            # Now, test FALLBACK SAFETY: mock SQLite failure
            # If the database file is corrupted or write fails, it should fallback to JSONStore
            # Let's write dummy text into friday_memory.db so sqlite fails to parse/initialize it
            with open(db_path, "w") as f:
                f.write("corrupted db file content")
                
            engine_fallback = MemoryEngine()
            await engine_fallback.initialize()
            
            fallback_store = engine_fallback._manager._store
            # Should have fallback to JSONStore
            assert isinstance(fallback_store, JSONStore)
            # JSONStore should return JSON values
            assert fallback_store.get("session:1") == {"data": "json_value"}
            assert fallback_store.get("session:2") == {"data": "json_only"}
            
            await engine_fallback.shutdown()
        finally:
            kernel._config = original_config
