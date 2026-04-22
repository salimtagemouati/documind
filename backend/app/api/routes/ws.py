"""
WebSocket API — real-time document processing progress.

Endpoint:
    GET /api/v1/ws/documents/{document_id}

Protocol:
    1. Client connects via WebSocket
    2. Server subscribes to the Redis pub/sub channel for this document
    3. As processing events arrive, they are forwarded to the client as JSON
    4. Connection closes when stage = "complete" or "error", or on timeout

Authentication:
    The WebSocket accepts a `token` query parameter for JWT auth.
    Example: ws://localhost:8000/api/v1/ws/documents/{id}?token=eyJ...

Messages sent to client:
    {"stage": "extracting", "progress": 10, "message": "Extracting text..."}
    {"stage": "chunking",   "progress": 30, "message": "Creating 47 chunks..."}
    {"stage": "embedding",  "progress": 55, "message": "Building vector index..."}
    {"stage": "analyzing",  "progress": 80, "message": "Running AI analysis..."}
    {"stage": "complete",   "progress": 100, "message": "Ready!"}
    {"stage": "error",      "progress": 0,  "message": "Failed: <reason>"}
"""
import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.database import AsyncSessionLocal
from app.models.models import Document, DocumentStatus
from app.services.progress_service import subscribe_progress

router = APIRouter(prefix="/ws", tags=["WebSocket"])
logger = get_logger(__name__)


@router.websocket("/documents/{document_id}")
async def document_progress_ws(
    websocket: WebSocket,
    document_id: str,
    token: str = Query(default=None),
):
    """
    WebSocket endpoint for real-time document processing progress.
    Authenticates via JWT token passed as query parameter.
    """
    # ─── Auth ─────────────────────────────────────────────────────────────
    if not token:
        await websocket.close(code=4001, reason="Missing auth token")
        return

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # ─── Accept connection ────────────────────────────────────────────────
    await websocket.accept()

    logger.info(
        "ws_connected",
        document_id=document_id,
        user_id=user_id,
    )

    try:
        # ─── Check current document status ────────────────────────────────
        # If the document is already ready or failed, send that immediately
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Document).where(
                    Document.id == UUID(document_id),
                )
            )
            doc = result.scalar_one_or_none()

            if not doc:
                await websocket.send_json({
                    "stage": "error",
                    "progress": 0,
                    "message": "Document not found",
                })
                await websocket.close()
                return

            # Verify ownership
            if str(doc.user_id) != user_id:
                await websocket.send_json({
                    "stage": "error",
                    "progress": 0,
                    "message": "Unauthorized",
                })
                await websocket.close()
                return

            if doc.status == DocumentStatus.ready:
                await websocket.send_json({
                    "stage": "complete",
                    "progress": 100,
                    "message": "Ready!",
                })
                await websocket.close()
                return

            if doc.status == DocumentStatus.failed:
                await websocket.send_json({
                    "stage": "error",
                    "progress": 0,
                    "message": f"Failed: {doc.error_message or 'Unknown error'}",
                })
                await websocket.close()
                return

        # ─── Subscribe to progress events ─────────────────────────────────
        # Run subscription in a separate task so we can also listen for
        # client disconnect (which raises WebSocketDisconnect)
        async def forward_events():
            async for event_json in subscribe_progress(document_id):
                try:
                    await websocket.send_text(event_json)
                    data = json.loads(event_json)
                    if data.get("stage") in ("complete", "error"):
                        break
                except (WebSocketDisconnect, RuntimeError):
                    break

        # Create tasks for both forwarding and listening for disconnect
        forward_task = asyncio.create_task(forward_events())

        try:
            # Wait for either: events finish naturally, or client disconnects
            while True:
                try:
                    # This will raise WebSocketDisconnect if client closes
                    await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    if forward_task.done():
                        break
                    continue
        except WebSocketDisconnect:
            pass
        finally:
            forward_task.cancel()
            try:
                await forward_task
            except (asyncio.CancelledError, Exception):
                pass

    except WebSocketDisconnect:
        logger.info("ws_disconnected", document_id=document_id)
    except Exception as e:
        logger.error("ws_error", document_id=document_id, error=str(e))
        try:
            await websocket.send_json({
                "stage": "error",
                "progress": 0,
                "message": "Internal server error",
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

        logger.info("ws_closed", document_id=document_id)
