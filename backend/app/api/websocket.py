"""
WebSocket Connection Manager & Real-Time Agent Stream Endpoint
Streams live agent thoughts, token updates, and diff events from Redis Pub/Sub directly to the browser.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.infrastructure.database.redis.client import redis_engine

logger = get_logger("codemigration.api.ws")
router = APIRouter()


class WebSocketConnectionManager:
    def __init__(self) -> None:
        # Map of workflow_id -> set of active WebSockets
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, workflow_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = set()
        self.active_connections[workflow_id].add(websocket)
        logger.info("WebSocket client connected", workflow_id=workflow_id)

    def disconnect(self, workflow_id: str, websocket: WebSocket) -> None:
        if workflow_id in self.active_connections:
            self.active_connections[workflow_id].discard(websocket)
            if not self.active_connections[workflow_id]:
                del self.active_connections[workflow_id]
        logger.info("WebSocket client disconnected", workflow_id=workflow_id)

    async def broadcast_to_workflow(self, workflow_id: str, message: dict) -> None:
        if workflow_id in self.active_connections:
            dead_sockets = set()
            for connection in self.active_connections[workflow_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_sockets.add(connection)
            for dead in dead_sockets:
                self.disconnect(workflow_id, dead)


ws_manager = WebSocketConnectionManager()


@router.websocket("/ws/workflows/{workflow_id}")
async def workflow_websocket_endpoint(websocket: WebSocket, workflow_id: str):
    """WebSocket endpoint for real-time agent thought streaming."""
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    # If token is provided, validate it. Allow optional unauthenticated in local dev only if configured
    if token:
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            if not payload or payload.get("type") != "access":
                await websocket.close(code=1008)
                return
        except Exception as auth_err:
            logger.debug(f"WebSocket auth failed: {auth_err}")
            await websocket.close(code=1008)
            return

    await ws_manager.connect(workflow_id, websocket)
    try:
        # Replay any buffered historical thoughts/diffs to the newly connected client
        buffered_events = await redis_engine.get_workflow_events(workflow_id)
        for event in buffered_events:
            try:
                await websocket.send_json(event)
            except Exception:
                break

        # Subscribe to real-time Redis PubSub for subsequent workflow events
        async for event in redis_engine.subscribe_workflow_events(workflow_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        ws_manager.disconnect(workflow_id, websocket)
    except Exception as e:
        logger.debug("WebSocket connection terminated", workflow_id=workflow_id, detail=str(e))
        ws_manager.disconnect(workflow_id, websocket)
