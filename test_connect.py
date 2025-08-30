# test_connection.py
import asyncio
import websockets

async def test_connection():
    try:
        async with websockets.connect('ws://localhost:8765') as websocket:
            print("连接成功!")
            await websocket.send('{"type": "test"}')
            response = await websocket.recv()
            print(f"收到响应: {response}")
    except Exception as e:
        print(f"连接失败: {e}")

asyncio.run(test_connection())