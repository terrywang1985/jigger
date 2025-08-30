import tkinter as tk
import PIL
import PIL.Image
import PIL.ImageTk
from PIL import Image, ImageTk
import asyncio
import websockets
import threading
import queue
import json
import time
import sys, os
from pynput import mouse, keyboard


def resource_path(filename):
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, filename)
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.dirname(__file__), filename)

# ----------------- DesktopPet -----------------
class DesktopPet:
    def __init__(self, root, sprite_path, player_id, ws=None, is_self=True):
        self.root = root
        self.ws = ws
        self.player_id = player_id
        self.is_self = is_self

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "white")

        # 加载图片
        self.idle_sprites = self.load_sprites(sprite_path, 3, scale=0.5)
        self.action_sprites = list(self.idle_sprites[::-1])
        self.current_image = self.idle_sprites[0]

        self.label = tk.Label(root, image=self.current_image, bg="white")
        self.label.pack()
        self.root.geometry(f"{self.idle_sprites[0].width()}x{self.idle_sprites[0].height()}")

        self.frame = 0
        self.events = []  # 最近1秒的动作事件
        self.chat_text = None
        self.chat_label = None

        # 拖动支持
        self.label.bind("<Button-1>", self.start_move)
        self.label.bind("<B1-Motion>", self.on_move)

        if is_self:
            self.root.bind("<Button-3>", self.show_menu)
            self.chat_entry = tk.Entry(self.root)
            self.chat_entry.pack(side=tk.BOTTOM, fill=tk.X)
            self.chat_entry.bind("<Return>", self.send_chat)
            self.start_listeners()
        else:
            self.chat_entry = None

        self.animate()

    def load_sprites(self, path, frame_count, scale=1.0):
        sheet = Image.open(path)
        w, h = sheet.size
        frame_width = w // frame_count
        frames = []
        for i in range(frame_count):
            frame = sheet.crop((i*frame_width,0,(i+1)*frame_width,h))
            if scale != 1.0:
                frame = frame.resize((int(frame_width*scale), int(h*scale)), Image.Resampling.LANCZOS)
            frames.append(ImageTk.PhotoImage(frame))
        return frames

    def show_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="退出", command=self.root.quit)
        menu.add_command(label="聊天", command=lambda: self.chat_entry.focus_set() if self.chat_entry else None)
        menu.tk_popup(event.x_root, event.y_root)

    def send_chat(self, event=None):
        text = self.chat_entry.get()
        if text.strip() and self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps({
                "type":"chat","player_id":self.player_id,"text":text
            })), asyncio.get_event_loop())
            self.chat_entry.delete(0, tk.END)

    def animate(self):
        now = time.time()
        # 保留最近1秒动作事件
        self.events = [t for t in self.events if now - t < 1]
        action_count = len(self.events)

        if action_count > 0:
            # 动画速度随动作频率增加
            delay = max(50, 200 - action_count*20)
            self.frame = (self.frame + 1) % len(self.action_sprites)
            self.current_image = self.action_sprites[self.frame]
            self.label.config(image=self.current_image)
        else:
            self.current_image = self.idle_sprites[0]
            self.label.config(image=self.current_image)
            delay = 200

        # 显示聊天
        if self.chat_text:
            if not self.chat_label:
                self.chat_label = tk.Label(self.root, text=self.chat_text, bg="yellow")
                self.chat_label.place(x=0, y=-20)
            if now - self.chat_start > 1:
                self.chat_label.destroy()
                self.chat_label = None
                self.chat_text = None

        self.root.after(delay, self.animate)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def on_move(self, event):
        dx = event.x - self.x
        dy = event.y - self.y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self.trigger_action()

    def trigger_action(self):
        self.events.append(time.time())
        if self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps({
                "type":"action","player_id":self.player_id
            })), asyncio.get_event_loop())

    def receive_action(self):
        self.events.append(time.time())

    def receive_chat(self, text):
        self.chat_text = text
        self.chat_start = time.time()

    def start_listeners(self):
        def on_click(x, y, button, pressed):
            if pressed:
                self.trigger_action()
        def on_key_press(key):
            self.trigger_action()
        mouse.Listener(on_click=on_click).start()
        keyboard.Listener(on_press=on_key_press).start()


# ----------------- Client -----------------
class Client:
    def __init__(self, sprite_path):
        self.sprite_path = sprite_path
        self.players = {}
        self.player_id = id(self)
        self.ws = None
        self.online = False
        self.event_queue = queue.Queue()

        self.root = tk.Tk()
        self.root.withdraw()
        self.start_pet(self.player_id, self.ws, is_self=True)

        threading.Thread(target=self.ws_loop, daemon=True).start()
        self.root.after(50, self.process_queue)
        self.root.mainloop()

    def start_pet(self, player_id, ws, is_self):
        window = tk.Toplevel(self.root)
        pet = DesktopPet(window, self.sprite_path, player_id, ws, is_self)
        self.players[player_id] = pet

    def process_queue(self):
        while not self.event_queue.empty():
            event = self.event_queue.get()
            pid = event.get("player_id")
            if pid not in self.players:
                self.start_pet(pid, self.ws, is_self=False)
            pet = self.players[pid]
            if event["type"] == "action":
                pet.receive_action()
            elif event["type"] == "chat":
                pet.receive_chat(event["text"])
        self.root.after(50, self.process_queue)

    def ws_loop(self):
        asyncio.run(self.ws_main())

    async def ws_main(self):
        uri = "ws://127.0.0.1:8765"
        try:
            self.ws = await asyncio.wait_for(websockets.connect(uri), timeout=1)
            self.online = True
            print("联网模式")
            room_name = "room1"
            await self.ws.send(json.dumps({"type":"join","room":room_name,"password":None}))
        except Exception:
            self.ws = None
            self.online = False
            print("单机模式")

        if self.online:
            try:
                async for msg in self.ws:
                    event = json.loads(msg)
                    self.event_queue.put(event)
            except Exception:
                self.online = False
                print("断开，切换单机模式")

        while not self.online:
            await asyncio.sleep(5)
            print("尝试重连服务器...")
            await self.ws_main()
            return

if __name__=="__main__":
    sprite_path = resource_path("spritesheet.png")
    Client(sprite_path)