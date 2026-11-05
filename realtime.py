import asyncio
from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    """Single-process rooms. Events contain invalidations, never answers or session data."""
    def __init__(self):
        self.rooms: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, edition_id: int, socket: WebSocket):
        await socket.accept()
        self.rooms[edition_id].add(socket)
        await socket.send_json({"event": "SYNC", "edition_id": edition_id})

    def disconnect(self, edition_id: int, socket: WebSocket):
        self.rooms[edition_id].discard(socket)
        if not self.rooms[edition_id]:
            del self.rooms[edition_id]

    async def broadcast(self, edition_id: int, event: str, revision: int):
        async def send(socket):
            try:
                await asyncio.wait_for(socket.send_json({"event": event, "edition_id": edition_id, "revision": revision}), timeout=3)
            except Exception:
                room = 0 if socket in self.rooms.get(0, ()) else edition_id
                self.disconnect(room, socket)
                try:
                    await socket.close()
                except Exception:
                    pass
        recipients = set(self.rooms.get(edition_id, ())) | set(self.rooms.get(0, ()))
        await asyncio.gather(*(send(socket) for socket in recipients))


hub = ConnectionManager()
