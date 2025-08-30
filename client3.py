import tkinter as tk
from tkinter import messagebox, ttk
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
        menu.add_command(label="主页", command=self.show_home)
        menu.add_command(label="退出", command=self.root.quit)
        menu.add_command(label="聊天", command=lambda: self.chat_entry.focus_set() if self.chat_entry else None)
        menu.tk_popup(event.x_root, event.y_root)
    
    def show_home(self):
        # 创建主页窗口
        HomePage(self.root)

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


# ----------------- 主页窗口 -----------------
class HomePage:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("桌面宠物主页")
        self.window.geometry("800x600")
        self.window.resizable(False, False)
        self.window.configure(bg="#f5f5f5")
        
        # 设置窗口图标（如果有的话）
        try:
            self.window.iconbitmap(resource_path("icon.ico"))
        except:
            pass
        
        # 创建主框架
        main_frame = tk.Frame(self.window, bg="#f5f5f5")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建左侧菜单栏
        self.menu_frame = tk.Frame(main_frame, width=150, bg="#e0e0e0", relief=tk.RAISED, bd=1)
        self.menu_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.menu_frame.pack_propagate(False)
        
        # 创建右侧内容区域
        self.content_frame = tk.Frame(main_frame, bg="white", relief=tk.SUNKEN, bd=1)
        self.content_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(10, 0))
        
        # 添加标题
        title_label = tk.Label(self.menu_frame, text="桌面宠物", font=("Arial", 16, "bold"), 
                              bg="#e0e0e0", fg="#333333")
        title_label.pack(pady=20)
        
        # 添加分隔线
        separator = ttk.Separator(self.menu_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=10, pady=10)
        
        # 添加菜单项
        self.create_menu()
        
        # 默认显示商城页面
        self.show_marketplace()
    
    def create_menu(self):
        # 商城按钮
        marketplace_btn = tk.Button(self.menu_frame, text="商城", width=15, height=2, 
                                   font=("Arial", 10), bg="#4CAF50", fg="white",
                                   command=self.show_marketplace)
        marketplace_btn.pack(pady=10)
        
        # 聊天室按钮
        chatroom_btn = tk.Button(self.menu_frame, text="聊天室", width=15, height=2,
                                font=("Arial", 10), bg="#2196F3", fg="white",
                                command=self.show_chatroom)
        chatroom_btn.pack(pady=10)
        
        # 好友按钮
        friends_btn = tk.Button(self.menu_frame, text="好友", width=15, height=2,
                               font=("Arial", 10), bg="#FF9800", fg="white",
                               command=self.show_friends)
        friends_btn.pack(pady=10)
        
        # 我的按钮
        profile_btn = tk.Button(self.menu_frame, text="我", width=15, height=2,
                               font=("Arial", 10), bg="#9C27B0", fg="white",
                               command=self.show_profile)
        profile_btn.pack(pady=10)
    
    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def show_marketplace(self):
        self.clear_content()
        title_label = tk.Label(self.content_frame, text="商城", font=("Arial", 16, "bold"), bg="white")
        title_label.pack(pady=10)
        
        # 创建滚动框架
        canvas = tk.Canvas(self.content_frame, bg="white")
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 模拟一些皮肤
        skins = [f"皮肤 {i+1}" for i in range(20)]
        rows = 4
        cols = 5
        
        for i, skin in enumerate(skins):
            row = i // cols
            col = i % cols
            
            skin_frame = tk.Frame(scrollable_frame, relief=tk.RAISED, bd=1, bg="white")
            skin_frame.grid(row=row, column=col, padx=10, pady=10)
            
            # 皮肤预览图
            preview_label = tk.Label(skin_frame, text=skin, width=10, height=3, 
                                    bg="#f0f0f0", relief=tk.SUNKEN, bd=1)
            preview_label.pack(padx=5, pady=5)
            
            btn_frame = tk.Frame(skin_frame, bg="white")
            btn_frame.pack(pady=5)
            
            preview_btn = tk.Button(btn_frame, text="预览", width=5, bg="#2196F3", fg="white",
                                   command=lambda s=skin: self.preview_skin(s))
            preview_btn.pack(side=tk.LEFT, padx=2)
            
            buy_btn = tk.Button(btn_frame, text="购买", width=5, bg="#4CAF50", fg="white",
                               command=lambda s=skin: self.buy_skin(s))
            buy_btn.pack(side=tk.LEFT, padx=2)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
    
    def preview_skin(self, skin_name):
        preview_window = tk.Toplevel(self.window)
        preview_window.title(f"预览 - {skin_name}")
        preview_window.geometry("300x300")
        preview_window.configure(bg="#f5f5f5")
        
        # 这里应该加载和显示皮肤动画
        tk.Label(preview_window, text=f"正在预览: {skin_name}", font=("Arial", 14), 
                bg="#f5f5f5").pack(pady=20)
        tk.Label(preview_window, text="这里是皮肤动画预览", bg="#f5f5f5").pack(pady=10)
        
        close_btn = tk.Button(preview_window, text="关闭", command=preview_window.destroy,
                             bg="#f44336", fg="white")
        close_btn.pack(pady=10)
    
    def buy_skin(self, skin_name):
        # 检查是否登录
        if not self.is_logged_in():
            messagebox.showinfo("提示", "请先登录才能购买皮肤")
            return
        
        # 弹出购买对话框
        buy_window = tk.Toplevel(self.window)
        buy_window.title(f"购买 - {skin_name}")
        buy_window.geometry("300x200")
        buy_window.configure(bg="#f5f5f5")
        
        tk.Label(buy_window, text=f"确定购买 {skin_name} 吗?", font=("Arial", 14), 
                bg="#f5f5f5").pack(pady=20)
        tk.Label(buy_window, text="价格: 100金币", bg="#f5f5f5").pack(pady=10)
        
        btn_frame = tk.Frame(buy_window, bg="#f5f5f5")
        btn_frame.pack(pady=10)
        
        confirm_btn = tk.Button(btn_frame, text="确认购买", bg="#4CAF50", fg="white",
                               command=lambda: self.confirm_purchase(skin_name, buy_window))
        confirm_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="取消", command=buy_window.destroy,
                              bg="#f44336", fg="white")
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def confirm_purchase(self, skin_name, window):
        window.destroy()
        messagebox.showinfo("购买成功", f"您已成功购买 {skin_name}!")
    
    def show_chatroom(self):
        self.clear_content()
        title_label = tk.Label(self.content_frame, text="聊天室", font=("Arial", 16, "bold"), bg="white")
        title_label.pack(pady=10)
        
        # 检查网络连接
        if not self.is_connected():
            tk.Label(self.content_frame, text="无法连接到服务器，请检查网络连接", 
                    bg="white").pack(pady=20)
            return
        
        # 创建聊天室按钮
        create_btn = tk.Button(self.content_frame, text="创建聊天室", bg="#4CAF50", fg="white",
                              command=self.create_chatroom)
        create_btn.pack(pady=10)
        
        # 模拟一些聊天室
        chatrooms = [f"聊天室 {i+1}" for i in range(15)]
        rows = 5
        cols = 3
        
        canvas = tk.Canvas(self.content_frame, bg="white")
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        for i, room in enumerate(chatrooms):
            row = i // cols
            col = i % cols
            
            room_frame = tk.Frame(scrollable_frame, relief=tk.RAISED, bd=1, bg="white")
            room_frame.grid(row=row, column=col, padx=10, pady=10)
            
            tk.Label(room_frame, text=room, width=15, height=2, bg="#f0f0f0").pack(padx=5, pady=5)
            
            join_btn = tk.Button(room_frame, text="加入", bg="#2196F3", fg="white",
                                command=lambda r=room: self.join_chatroom(r))
            join_btn.pack(pady=5)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
    
    def create_chatroom(self):
        create_window = tk.Toplevel(self.window)
        create_window.title("创建聊天室")
        create_window.geometry("300x200")
        create_window.configure(bg="#f5f5f5")
        
        tk.Label(create_window, text="聊天室名称:", bg="#f5f5f5").pack(pady=10)
        name_entry = tk.Entry(create_window, width=20)
        name_entry.pack(pady=5)
        
        tk.Label(create_window, text="密码(可选):", bg="#f5f5f5").pack(pady=10)
        password_entry = tk.Entry(create_window, width=20, show="*")
        password_entry.pack(pady=5)
        
        btn_frame = tk.Frame(create_window, bg="#f5f5f5")
        btn_frame.pack(pady=10)
        
        confirm_btn = tk.Button(btn_frame, text="创建", bg="#4CAF50", fg="white",
                               command=lambda: self.confirm_create_chatroom(
                                   name_entry.get(), password_entry.get(), create_window))
        confirm_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="取消", command=create_window.destroy,
                              bg="#f44336", fg="white")
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def confirm_create_chatroom(self, name, password, window):
        if not name:
            messagebox.showerror("错误", "聊天室名称不能为空")
            return
        
        window.destroy()
        messagebox.showinfo("成功", f"聊天室 '{name}' 创建成功!")
        # 这里应该实际创建聊天室的逻辑
    
    def join_chatroom(self, room_name):
        # 加入聊天室的逻辑
        messagebox.showinfo("加入聊天室", f"已加入 {room_name}")
        # 这里应该实现实际的加入聊天室逻辑
    
    def show_friends(self):
        self.clear_content()
        title_label = tk.Label(self.content_frame, text="好友", font=("Arial", 16, "bold"), bg="white")
        title_label.pack(pady=10)
        
        # 检查是否登录
        if not self.is_logged_in():
            tk.Label(self.content_frame, text="请先登录才能查看好友", bg="white").pack(pady=20)
            return
        
        # 模拟好友列表
        friends = [("好友1", "在线"), ("好友2", "离线"), ("好友3", "游戏中")]
        
        for name, status in friends:
            friend_frame = tk.Frame(self.content_frame, bg="white")
            friend_frame.pack(fill=tk.X, padx=20, pady=5)
            
            status_color = "green" if status == "在线" else "gray"
            tk.Label(friend_frame, text=name, width=10, bg="white").pack(side=tk.LEFT)
            tk.Label(friend_frame, text=status, fg=status_color, bg="white").pack(side=tk.LEFT)
    
    def show_profile(self):
        self.clear_content()
        title_label = tk.Label(self.content_frame, text="我的信息", font=("Arial", 16, "bold"), bg="white")
        title_label.pack(pady=10)
        
        # 检查是否登录
        if not self.is_logged_in():
            tk.Label(self.content_frame, text="请先登录才能查看个人信息", bg="white").pack(pady=20)
            
            btn_frame = tk.Frame(self.content_frame, bg="white")
            btn_frame.pack(pady=10)
            
            login_btn = tk.Button(btn_frame, text="登录", bg="#4CAF50", fg="white", 
                                 command=self.show_login)
            login_btn.pack(side=tk.LEFT, padx=10)
            
            register_btn = tk.Button(btn_frame, text="注册", bg="#2196F3", fg="white",
                                   command=self.show_register)
            register_btn.pack(side=tk.LEFT, padx=10)
            return
        
        # 显示用户信息
        user_info = {
            "用户名": "testuser",
            "等级": "10",
            "金币": "1000",
            "拥有的皮肤": "5"
        }
        
        info_frame = tk.Frame(self.content_frame, bg="white")
        info_frame.pack(pady=20)
        
        for i, (key, value) in enumerate(user_info.items()):
            tk.Label(info_frame, text=f"{key}: {value}", bg="white").grid(row=i, column=0, sticky=tk.W, pady=5)
    
    def show_login(self):
        login_window = tk.Toplevel(self.window)
        login_window.title("登录")
        login_window.geometry("300x250")
        login_window.configure(bg="#f5f5f5")
        
        tk.Label(login_window, text="用户名:", bg="#f5f5f5").pack(pady=10)
        username_entry = tk.Entry(login_window, width=20)
        username_entry.pack(pady=5)
        
        tk.Label(login_window, text="密码:", bg="#f5f5f5").pack(pady=10)
        password_entry = tk.Entry(login_window, width=20, show="*")
        password_entry.pack(pady=5)
        
        btn_frame = tk.Frame(login_window, bg="#f5f5f5")
        btn_frame.pack(pady=10)
        
        login_btn = tk.Button(btn_frame, text="登录", bg="#4CAF50", fg="white",
                             command=lambda: self.do_login(
                                 username_entry.get(), password_entry.get(), login_window))
        login_btn.pack(side=tk.LEFT, padx=5)
        
        register_btn = tk.Button(btn_frame, text="注册", bg="#2196F3", fg="white",
                                command=lambda: self.show_register_from_login(login_window))
        register_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="取消", command=login_window.destroy,
                              bg="#f44336", fg="white")
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def show_register(self):
        register_window = tk.Toplevel(self.window)
        register_window.title("注册")
        register_window.geometry("300x300")
        register_window.configure(bg="#f5f5f5")
        
        tk.Label(register_window, text="用户名:", bg="#f5f5f5").pack(pady=10)
        username_entry = tk.Entry(register_window, width=20)
        username_entry.pack(pady=5)
        
        tk.Label(register_window, text="密码:", bg="#f5f5f5").pack(pady=10)
        password_entry = tk.Entry(register_window, width=20, show="*")
        password_entry.pack(pady=5)
        
        tk.Label(register_window, text="确认密码:", bg="#f5f5f5").pack(pady=10)
        confirm_password_entry = tk.Entry(register_window, width=20, show="*")
        confirm_password_entry.pack(pady=5)
        
        btn_frame = tk.Frame(register_window, bg="#f5f5f5")
        btn_frame.pack(pady=10)
        
        register_btn = tk.Button(btn_frame, text="注册", bg="#4CAF50", fg="white",
                                command=lambda: self.do_register(
                                    username_entry.get(), password_entry.get(), 
                                    confirm_password_entry.get(), register_window))
        register_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="取消", command=register_window.destroy,
                              bg="#f44336", fg="white")
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def show_register_from_login(self, login_window):
        login_window.destroy()
        self.show_register()
    
    def do_login(self, username, password, window):
        if not username or not password:
            messagebox.showerror("错误", "用户名和密码不能为空")
            return
        
        # 这里应该实现实际的登录逻辑
        window.destroy()
        messagebox.showinfo("成功", "登录成功!")
        # 刷新页面显示用户信息
        self.show_profile()
    
    def do_register(self, username, password, confirm_password, window):
        if not username or not password:
            messagebox.showerror("错误", "用户名和密码不能为空")
            return
        
        if password != confirm_password:
            messagebox.showerror("错误", "两次输入的密码不一致")
            return
        
        # 这里应该实现实际的注册逻辑
        window.destroy()
        messagebox.showinfo("成功", "注册成功!")
        # 显示登录窗口
        self.show_login()
    
    def is_logged_in(self):
        # 这里应该检查用户是否已登录
        # 暂时返回False模拟未登录状态
        return False
    
    def is_connected(self):
        # 这里应该检查网络连接状态
        # 暂时返回True模拟已连接状态
        return True


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