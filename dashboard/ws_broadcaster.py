import asyncio
import json
from fastapi import WebSocket
from dashboard.data_collector import collect_dashboard_payload


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def broadcast_loop():
    while True:
        try:
            payload = await collect_dashboard_payload()
            await manager.broadcast(json.dumps(payload))
        except Exception:
            pass
        await asyncio.sleep(3)
