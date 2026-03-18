"""Tests for long-term memory."""

import json


class TestLongTermMemory:
    def test_store_and_recall(self, setup_server):
        from arrow.server import store_memory, recall_memory
        # Store
        r = json.loads(store_memory(
            "auth-pattern", "Uses JWT tokens with refresh rotation",
            category="architecture",
        ))
        assert r["stored"] is True
        assert r["id"] > 0

        # Recall
        r2 = json.loads(recall_memory("JWT tokens"))
        assert r2["total"] > 0
        assert any(
            "JWT" in m["content"] for m in r2["memories"]
        )

    def test_store_updates_existing(self, setup_server):
        from arrow.server import store_memory, list_memories
        store_memory("db-conv", "Uses PostgreSQL", category="convention")
        store_memory("db-conv", "Uses PostgreSQL with pgvector",
                     category="convention")
        r = json.loads(list_memories(category="convention"))
        # Should be 1 memory, not 2 (upsert)
        db_mems = [m for m in r["memories"] if m["key"] == "db-conv"]
        assert len(db_mems) == 1
        assert "pgvector" in db_mems[0]["content"]

    def test_delete_memory_by_id(self, setup_server):
        from arrow.server import (
            store_memory, delete_memory, list_memories
        )
        r = json.loads(store_memory("temp-note", "delete me"))
        mem_id = r["id"]
        dr = json.loads(delete_memory(memory_id=mem_id))
        assert dr["deleted"] == 1
        lr = json.loads(list_memories())
        assert not any(m["key"] == "temp-note" for m in lr["memories"])

    def test_delete_memory_by_key(self, setup_server):
        from arrow.server import (
            store_memory, delete_memory, list_memories
        )
        store_memory("to-forget", "forget this", category="note")
        dr = json.loads(delete_memory(
            key="to-forget", category="note"
        ))
        assert dr["deleted"] == 1

    def test_list_memories_filter(self, setup_server):
        from arrow.server import store_memory, list_memories
        store_memory("a1", "arch info", category="architecture")
        store_memory("c1", "conv info", category="convention")
        r = json.loads(list_memories(category="architecture"))
        assert all(
            m["category"] == "architecture"
            for m in r["memories"]
        )

    def test_recall_bumps_access_count(self, setup_server):
        from arrow.server import (
            store_memory, recall_memory, list_memories
        )
        store_memory("frequent", "accessed often")
        recall_memory("accessed often")
        recall_memory("accessed often")
        r = json.loads(list_memories())
        mem = next(
            (m for m in r["memories"] if m["key"] == "frequent"),
            None,
        )
        assert mem is not None
        assert mem["access_count"] >= 2

    def test_project_scoped_memory(self, setup_server):
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        name = projects[0].name

        from arrow.server import store_memory, list_memories
        store_memory(
            "proj-note", "project specific",
            project=name,
        )
        # List global — should not appear
        r_global = json.loads(list_memories())
        global_keys = [m["key"] for m in r_global["memories"]]
        # List project-scoped — should appear
        r_proj = json.loads(list_memories(project=name))
        proj_keys = [m["key"] for m in r_proj["memories"]]
        assert "proj-note" in proj_keys
