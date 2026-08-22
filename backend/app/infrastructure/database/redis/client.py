"""
Redis Client & Pub/Sub Messaging Engine
Provides async caching, rate limiting counters, distributed locks, and real-time WebSocket channels.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("codemigration.db.redis")


class RedisEngine:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._loop: Any = None

    def reset(self) -> None:
        """Reset Redis connection reference so new event loops create fresh connections."""
        self._redis = None
        self._loop = None

    async def _ensure_redis(self) -> aioredis.Redis | None:
        """Ensure the Redis client is bound to the currently running event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._loop != current_loop or self._redis is None:
            self._redis = None
            self._loop = current_loop
            await self.connect()
        return self._redis

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        try:
            is_secure = settings.REDIS_HOST not in ("localhost", "127.0.0.1")
            if is_secure:
                url = f"rediss://default:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}?ssl_cert_reqs=none"
            else:
                url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}" if settings.REDIS_PASSWORD else f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"

            client = aioredis.from_url(
                url,
                decode_responses=True,
                max_connections=50,
            )
            await client.ping()
            self._redis = client
            logger.info("Connected to Redis Engine successfully")
        except Exception as e:
            self._redis = None
            logger.warning("Could not connect to Redis (will fallback or retry in live env)", error=str(e))

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None
            self._loop = None
            logger.info("Redis connection closed")

    async def get_json(self, key: str) -> Any | None:
        """Fetch and deserialize a JSON object from cache."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return None
            data = await redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.debug(f"Redis get_json failed for key {key}: {e}")
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Serialize and store a JSON object with TTL."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return False
            result = await redis.set(key, json.dumps(value), ex=ttl_seconds)
            return bool(result)
        except Exception as e:
            logger.debug(f"Redis set_json failed for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return False
            result = await redis.delete(key)
            return bool(result)
        except Exception as e:
            logger.debug(f"Redis delete failed for key {key}: {e}")
            return False

    async def publish_workflow_event(self, workflow_id: str, event_data: dict) -> int:
        """Publish a real-time agent event (e.g. thought, diff, step update) to subscribers and buffer in Redis."""
        redis = await self._ensure_redis()
        if not redis:
            return 0

        payload = json.dumps(event_data)
        history_key = f"workflow_events:{workflow_id}"

        try:
            # Buffer event to Redis list with 24-hour TTL for instant tab switching / rehydration
            await redis.rpush(history_key, payload)
            await redis.expire(history_key, 86400)
        except Exception as e:
            logger.debug(f"Failed to buffer workflow event in Redis: {e}")

        channel = f"ws:channel:workflow:{workflow_id}"
        try:
            return await redis.publish(channel, payload)
        except Exception as e:
            logger.debug(f"Failed to publish workflow event to Redis channel {channel}: {e}")
            return 0

    async def get_workflow_events(self, workflow_id: str) -> list[dict]:
        """Fetch all historical events buffered for this workflow."""
        redis = await self._ensure_redis()
        if not redis:
            return []

        history_key = f"workflow_events:{workflow_id}"
        try:
            raw_items = await redis.lrange(history_key, 0, -1)
            return [json.loads(item) for item in raw_items if item]
        except Exception as e:
            logger.debug(f"Failed to fetch buffered workflow events from Redis: {e}")
            return []

    async def subscribe_workflow_events(
        self, workflow_id: str
    ) -> AsyncGenerator[dict]:
        """Subscribe to a workflow's real-time event stream."""
        redis = await self._ensure_redis()
        if not redis:
            return

        pubsub = redis.pubsub()
        channel = f"ws:channel:workflow:{workflow_id}"
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()


redis_engine = RedisEngine()
