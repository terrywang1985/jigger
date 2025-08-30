import asyncio
import websockets
import json

rooms = {}  # room_id -> {"password": str, "players": set of websockets}

async def handler(ws):
    player_room = None
    player_id = id(ws)
    try:
        async for msg in ws:
            data = json.loads(msg)
            if data["type"] == "list_rooms":
                room_list = [{"room": r, "has_password": bool(info.get("password"))} for r, info in rooms.items()]
                await ws.send(json.dumps({"type":"room_list", "rooms": room_list}))
            elif data["type"] == "join":
                room_id = data["room"]
                password = data.get("password")
                # 如果房间不存在，创建房间
                if room_id not in rooms:
                    rooms[room_id] = {"password": password, "players": set()}
                else:
                    # 检查密码
                    if rooms[room_id].get("password") and rooms[room_id]["password"] != password:
                        await ws.send(json.dumps({"type":"join_failed","reason":"wrong password"}))
                        continue
                player_room = room_id
                rooms[room_id]["players"].add(ws)
                # 发送当前房间玩家列表
                players = [id(p) for p in rooms[room_id]["players"]]
                await ws.send(json.dumps({"type":"room_players","players":players}))
            elif data["type"] in ("action","chat"):
                # 广播给同房间其他玩家
                for p in rooms.get(player_room, {}).get("players", set()):
                    if p != ws:
                        await p.send(msg)
    finally:
        if player_room and ws in rooms.get(player_room, {}).get("players", set()):
            rooms[player_room]["players"].remove(ws)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Server started at ws://0.0.0.0:8765")
        await asyncio.Future()

asyncio.run(main())
