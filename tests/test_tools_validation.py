import pytest

from src.schemas import MemoryType
from src.tools.memory_tools import _validate_entity_key, _validate_limit, _validate_memory_type


class TestValidateMemoryType:
    def test_valid_types(self):
        assert _validate_memory_type("user_memory") == MemoryType.USER_MEMORY
        assert _validate_memory_type("project_memory") == MemoryType.PROJECT_MEMORY
        assert _validate_memory_type("project_guidelines") == MemoryType.PROJECT_GUIDELINES
        assert _validate_memory_type("agent_memory") == MemoryType.AGENT_MEMORY

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid memory_type"):
            _validate_memory_type("invalid_type")

    def test_empty_type(self):
        with pytest.raises(ValueError):
            _validate_memory_type("")


class TestValidateLimit:
    def test_normal_limit(self):
        assert _validate_limit(10) == 10

    def test_clamp_upper(self):
        assert _validate_limit(9999) == 500

    def test_clamp_lower(self):
        assert _validate_limit(-5) == 1
        assert _validate_limit(0) == 1

    def test_boundary(self):
        assert _validate_limit(500) == 500
        assert _validate_limit(1) == 1


class TestValidateEntityKey:
    def test_normal_key(self):
        assert _validate_entity_key("my-project") == "my-project"

    def test_max_length(self):
        key = "x" * 512
        assert _validate_entity_key(key) == key

    def test_too_long(self):
        with pytest.raises(ValueError, match="max length"):
            _validate_entity_key("x" * 513)
