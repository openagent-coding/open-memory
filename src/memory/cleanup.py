from __future__ import annotations

import asyncio
import logging

from ..config import Settings
from ..database.base import MemoryDatabase
from ..schemas import MemoryType

logger = logging.getLogger(__name__)


class CleanupService:
    def __init__(self, db: MemoryDatabase, settings: Settings):
        self._db = db
        self._settings = settings
        self._interval = settings.cleanup_interval_hours * 3600

    async def run_cleanup(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for mt in MemoryType:
            ttl = self._settings.ttl_for_type(mt.value)
            if ttl > 0:
                deleted = await self._db.delete_expired(mt.value, ttl)
                if deleted:
                    stats[f"{mt.value}_expired"] = deleted
        if stats:
            logger.info("Cleanup results: %s", stats)
        return stats

    async def start_background_loop(self) -> None:
        logger.info("Cleanup loop started (interval=%dh)", self._settings.cleanup_interval_hours)
        while True:
            try:
                await self.run_cleanup()
            except Exception:
                logger.exception("Cleanup cycle failed")
            await asyncio.sleep(self._interval)
