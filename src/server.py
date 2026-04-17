from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from .config import Settings
from .database.postgres import PostgresDatabase
from .embeddings.manager import EmbeddingManager
from .memory.cleanup import CleanupService
from .memory.service import MemoryService
from .tools.memory_tools import register_tools

logger = logging.getLogger("open-memory")


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    settings = Settings()

    db = PostgresDatabase(settings)
    await db.initialize()
    logger.info("Database ready")

    embeddings = EmbeddingManager(settings)
    await embeddings.initialize()

    memory_service = MemoryService(db, embeddings, settings)

    cleanup = CleanupService(db, settings)
    cleanup_task = asyncio.create_task(cleanup.start_background_loop())

    try:
        yield {"memory_service": memory_service, "settings": settings}
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        await db.close()
        logger.info("Shutdown complete")


def create_server() -> FastMCP:
    server = FastMCP(
        name="open-memory",
        instructions=(
            "Persistent memory server for AI coding agents. "
            "Store and retrieve user preferences, project context, "
            "coding guidelines, and agent-learned behaviors. "
            "All writes are automatically deduplicated using semantic similarity. "
            "Use search_memory for cross-type semantic search.\n\n"
            "Available memory types: user_memory, project_memory, "
            "project_guidelines, agent_memory."
        ),
        lifespan=lifespan,
    )
    register_tools(server)
    return server


def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    server = create_server()

    if settings.mcp_transport == "streamable-http":
        server.run(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
        )
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
