from src.memory.dedup import DedupService


class TestMergeContent:
    def test_high_similarity_replaces(self):
        result = DedupService.merge_content("old content", "new content", 0.96)
        assert result == "new content"

    def test_boundary_similarity_replaces(self):
        result = DedupService.merge_content("old content", "new content", 0.90)
        assert result == "new content"

    def test_lower_similarity_appends(self):
        result = DedupService.merge_content("old content", "new content", 0.86)
        assert "old content" in result
        assert "new content" in result
        assert "---" in result

    def test_empty_existing(self):
        result = DedupService.merge_content("", "new content", 0.95)
        assert result == "new content"

    def test_empty_new(self):
        result = DedupService.merge_content("old content", "", 0.95)
        assert result == ""
