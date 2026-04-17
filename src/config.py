from __future__ import annotations

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "open_memory"
    db_user: str = "memory_user"
    db_password: SecretStr = SecretStr("changeme")
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Embedding models
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_dim: int = 256

    # Dual embedding (text + code, enabled by default)
    dual_embedding: bool = True
    code_embedding_model: str = "nomic-ai/CodeRankEmbed"
    code_embedding_dim: int = 768

    # Dedup
    similarity_threshold: float = 0.85

    # TTL (days, 0 = permanent)
    user_memory_ttl_days: int = 0
    project_memory_ttl_days: int = 90
    project_guidelines_ttl_days: int = 0
    agent_memory_ttl_days: int = 30

    # Caps
    user_memory_cap: int = 500
    project_memory_cap: int = 1000
    project_guidelines_cap: int = 500
    agent_memory_cap: int = 500

    # Runtime
    enable_gpu: bool = False
    log_level: str = "INFO"
    mcp_transport: Literal["stdio", "streamable-http"] = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8080
    cleanup_interval_hours: int = 24

    @property
    def dsn(self) -> str:
        pw = self.db_password.get_secret_value()
        return f"postgresql://{self.db_user}:{pw}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def device(self) -> str:
        return "cuda" if self.enable_gpu else "cpu"

    _TTL_MAP = {
        "user_memory": "user_memory_ttl_days",
        "project_memory": "project_memory_ttl_days",
        "project_guidelines": "project_guidelines_ttl_days",
        "agent_memory": "agent_memory_ttl_days",
    }

    _CAP_MAP = {
        "user_memory": "user_memory_cap",
        "project_memory": "project_memory_cap",
        "project_guidelines": "project_guidelines_cap",
        "agent_memory": "agent_memory_cap",
    }

    def ttl_for_type(self, memory_type: str) -> int:
        attr = self._TTL_MAP.get(memory_type)
        if attr is None:
            raise ValueError(f"Unknown memory type: {memory_type!r}. Valid: {sorted(self._TTL_MAP)}")
        return getattr(self, attr)

    def cap_for_type(self, memory_type: str) -> int:
        attr = self._CAP_MAP.get(memory_type)
        if attr is None:
            raise ValueError(f"Unknown memory type: {memory_type!r}. Valid: {sorted(self._CAP_MAP)}")
        return getattr(self, attr)

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}
