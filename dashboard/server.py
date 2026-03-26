import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from dashboard.ws_broadcaster import manager, broadcast_loop

app = FastAPI(title="Sniper Bot Dashboard")


@app.on_event("startup")
async def startup():
    asyncio.create_task(broadcast_loop())


@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
