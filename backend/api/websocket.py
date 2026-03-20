from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ThoughtBroadcaster:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, payload: dict) -> None:
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


thought_broadcaster = ThoughtBroadcaster()


@router.websocket("/ws/agent-thoughts")
async def agent_thoughts(websocket: WebSocket) -> None:
    await thought_broadcaster.connect(websocket)
    try:
        while True:
            # Keep connection alive; client may send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        thought_broadcaster.disconnect(websocket)
