from src.schemas import MemoryEntry, MemoryType, SaveMemoryResponse, SearchResult


class TestEnums:
    def test_memory_type_values(self):
        assert MemoryType.USER_MEMORY.value == "user_memory"
        assert MemoryType.PROJECT_MEMORY.value == "project_memory"
        assert MemoryType.PROJECT_GUIDELINES.value == "project_guidelines"
        assert MemoryType.AGENT_MEMORY.value == "agent_memory"

    def test_memory_type_from_string(self):
        assert MemoryType("user_memory") == MemoryType.USER_MEMORY
        assert MemoryType("project_guidelines") == MemoryType.PROJECT_GUIDELINES


class TestMemoryEntry:
    def test_minimal_entry(self):
        entry = MemoryEntry(
            id="abc", memory_type="user_memory", entity_key="user1", content="test"
        )
        assert entry.id == "abc"
        assert entry.metadata == {}
        assert entry.access_count == 0

    def test_full_entry(self):
        entry = MemoryEntry(
            id="abc",
            memory_type="project_guidelines",
            entity_key="proj1",
            content="use DI",
            metadata={"key": "val"},
            content_type="code",
            access_count=5,
        )
        assert entry.content_type == "code"
        assert entry.metadata["key"] == "val"
        assert entry.memory_type == "project_guidelines"


class TestSaveMemoryResponse:
    def test_inserted(self):
        resp = SaveMemoryResponse(id="abc", action="inserted")
        assert resp.merged_with_id is None

    def test_merged(self):
        resp = SaveMemoryResponse(id="abc", action="merged", merged_with_id="def")
        assert resp.merged_with_id == "def"


class TestSearchResult:
    def test_search_result(self):
        entry = MemoryEntry(
            id="abc", memory_type="user_memory", entity_key="u1", content="test"
        )
        result = SearchResult(entry=entry, similarity=0.92)
        assert result.similarity == 0.92
