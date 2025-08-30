import tkinter as tk
from tkinter import ttk, messagebox
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
                self.chat_label.place_forget()
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


# ----------------- 现代化的主页窗口 -----------------
class HomePage:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("桌面宠物主页")
        self.window.geometry("900x650")
        self.window.resizable(False, False)
        self.window.configure(bg="#2c3e50")
        
        # 先居中窗口，避免闪烁
        self.center_window(self.window, 900, 650)
        
        # 设置样式
        self.style = ttk.Style()
        self.style.theme_use('clam')  # 使用clam主题，更现代化
        
        # 配置样式
        self.style.configure('TFrame', background='#2c3e50')
        self.style.configure('Header.TLabel', background='#2c3e50', foreground='white', font=('Arial', 18, 'bold'))
        self.style.configure('Content.TFrame', background='#ecf0f1')
        self.style.configure('Menu.TButton', background='#34495e', foreground='white', 
                            font=('Arial', 12), width=15, padding=10)
        self.style.map('Menu.TButton', background=[('active', '#3498db')])
        self.style.configure('Action.TButton', background='#3498db', foreground='white', 
                            font=('Arial', 10), padding=5)
        self.style.map('Action.TButton', background=[('active', '#2980b9')])
        
        # 创建主框架
        main_frame = ttk.Frame(self.window, style='TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 创建标题
        header = ttk.Frame(main_frame, style='TFrame')
        header.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ttk.Label(header, text="桌面宠物管理中心", style='Header.TLabel')
        title_label.pack(side=tk.LEFT)
        
        # 创建内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建左侧菜单栏
        self.menu_frame = ttk.Frame(content_frame, width=180, style='TFrame')
        self.menu_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.menu_frame.pack_propagate(False)
        
        # 创建右侧内容区域
        self.content_frame = ttk.Frame(content_frame, style='Content.TFrame')
        self.content_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(20, 0))
        
        # 添加菜单项
        self.create_menu()
        
        # 默认显示商城页面
        self.show_marketplace()
    
    def create_menu(self):
        # 商城按钮
        marketplace_btn = ttk.Button(self.menu_frame, text="商城", style='Menu.TButton',
                                    command=self.show_marketplace)
        marketplace_btn.pack(pady=10)
        
        # 聊天室按钮
        chatroom_btn = ttk.Button(self.menu_frame, text="聊天室", style='Menu.TButton',
                                 command=self.show_chatroom)
        chatroom_btn.pack(pady=10)
        
        # 好友按钮
        friends_btn = ttk.Button(self.menu_frame, text="好友", style='Menu.TButton',
                                command=self.show_friends)
        friends_btn.pack(pady=10)
        
        # 我的按钮
        profile_btn = ttk.Button(self.menu_frame, text="我", style='Menu.TButton',
                                command=self.show_profile)
        profile_btn.pack(pady=10)
    
    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def center_window(self, window, width, height):
        """将窗口居中显示"""
        window.update_idletasks()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f'{width}x{height}+{x}+{y}')
    
    def show_marketplace(self):
        self.clear_content()
        
        # 标题
        title_frame = ttk.Frame(self.content_frame, style='Content.TFrame')
        title_frame.pack(fill=tk.X, pady=10)
        
        title_label = ttk.Label(title_frame, text="皮肤商城", 
                               font=('Arial', 16, 'bold'), background='#ecf0f1')
        title_label.pack()
        
        # 创建滚动框架
        container = ttk.Frame(self.content_frame, style='Content.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(container, bg='#ecf0f1', highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Content.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 设置网格列权重，确保均匀分布
        for i in range(4):
            scrollable_frame.columnconfigure(i, weight=1)
        
        # 模拟一些皮肤
        skins = [f"皮肤 {i+1}" for i in range(20)]
        
        for i, skin in enumerate(skins):
            row = i // 4
            col = i % 4
            
            skin_frame = ttk.Frame(scrollable_frame, style='Content.TFrame', 
                                  relief='raised', padding=10)
            skin_frame.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            
            # 皮肤预览图 - 使用Frame包装Label来设置高度
            preview_frame = ttk.Frame(skin_frame, height=100, width=120, style='Content.TFrame')
            preview_frame.pack_propagate(False)  # 阻止Frame自动调整大小
            preview_frame.pack(pady=5, fill=tk.X, expand=True)
            
            preview = ttk.Label(preview_frame, text=skin, 
                               background='#bdc3c7',
                               anchor='center', font=('Arial', 10))
            preview.pack(fill=tk.BOTH, expand=True)
            
            btn_frame = ttk.Frame(skin_frame, style='Content.TFrame')
            btn_frame.pack(pady=5, fill=tk.X)
            
            preview_btn = ttk.Button(btn_frame, text="预览", style='Action.TButton',
                                    command=lambda s=skin: self.preview_skin(s))
            preview_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            
            buy_btn = ttk.Button(btn_frame, text="购买", style='Action.TButton',
                                command=lambda s=skin: self.buy_skin(s))
            buy_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def preview_skin(self, skin_name):
        preview_window = tk.Toplevel(self.window)
        preview_window.title(f"预览 - {skin_name}")
        preview_window.geometry("350x400")
        preview_window.configure(bg='#ecf0f1')
        preview_window.transient(self.window)  # 设置为模态窗口
        preview_window.grab_set()  # 捕获所有事件
        self.center_window(preview_window, 350, 400)  # 居中窗口
        
        # 使用Frame包装内容，使其居中
        main_frame = ttk.Frame(preview_window, style='Content.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 这里应该加载和显示皮肤动画
        ttk.Label(main_frame, text=f"正在预览: {skin_name}", 
                 font=('Arial', 14), background='#ecf0f1').pack(pady=20)
        
        # 模拟预览区域
        preview_area = ttk.Frame(main_frame, width=200, height=200, 
                                style='Content.TFrame')
        preview_area.pack(pady=10)
        preview_area.pack_propagate(False)
        
        ttk.Label(preview_area, text="皮肤动画预览", 
                 background='#bdc3c7', anchor='center').pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(main_frame, text="关闭", style='Action.TButton',
                  command=preview_window.destroy).pack(pady=10)
    
    def buy_skin(self, skin_name):
        # 检查是否登录
        if not self.is_logged_in():
            messagebox.showinfo("提示", "请先登录才能购买皮肤")
            return
        
        # 弹出购买对话框
        buy_window = tk.Toplevel(self.window)
        buy_window.title(f"购买 - {skin_name}")
        buy_window.geometry("350x200")
        buy_window.configure(bg='#ecf0f1')
        buy_window.transient(self.window)  # 设置为模态窗口
        buy_window.grab_set()  # 捕获所有事件
        self.center_window(buy_window, 350, 200)  # 居中窗口
        
        # 使用Frame包装内容，使其居中
        main_frame = ttk.Frame(buy_window, style='Content.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text=f"确定购买 {skin_name} 吗?", 
                 font=('Arial', 14), background='#ecf0f1').pack(pady=10)
        ttk.Label(main_frame, text="价格: 100金币", background='#ecf0f1').pack(pady=5)
        
        btn_frame = ttk.Frame(main_frame, style='Content.TFrame')
        btn_frame.pack(pady=10)
        
        confirm_btn = ttk.Button(btn_frame, text="确认购买", style='Action.TButton',
                                command=lambda: self.confirm_purchase(skin_name, buy_window))
        confirm_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(btn_frame, text="取消", style='Action.TButton',
                               command=buy_window.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def confirm_purchase(self, skin_name, window):
        window.destroy()
        messagebox.showinfo("购买成功", f"您已成功购买 {skin_name}!")
    
    def show_chatroom(self):
        self.clear_content()
        
        # 标题和创建按钮
        header_frame = ttk.Frame(self.content_frame, style='Content.TFrame')
        header_frame.pack(fill=tk.X, pady=10)
        
        title_label = ttk.Label(header_frame, text="聊天室", 
                               font=('Arial', 16, 'bold'), background='#ecf0f1')
        title_label.pack(side=tk.LEFT, padx=10)
        
        create_btn = ttk.Button(header_frame, text="创建聊天室", style='Action.TButton',
                               command=self.create_chatroom)
        create_btn.pack(side=tk.RIGHT, padx=10)
        
        # 检查网络连接
        if not self.is_connected():
            ttk.Label(self.content_frame, text="无法连接到服务器，请检查网络连接", 
                     background='#ecf0f1').pack(pady=20)
            return
        
        # 创建聊天室列表
        container = ttk.Frame(self.content_frame, style='Content.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(container, bg='#ecf0f1', highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Content.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 模拟聊天室列表
        chatrooms = [f"聊天室 {i+1}" for i in range(15)]
        
        for i, room in enumerate(chatrooms):
            room_frame = ttk.Frame(scrollable_frame, style='Content.TFrame', 
                                  relief='raised', padding=10)
            room_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(room_frame, text=room, background='#ecf0f1', 
                     font=('Arial', 12)).pack(side=tk.LEFT)
            
            join_btn = ttk.Button(room_frame, text="加入", style='Action.TButton',
                                 command=lambda r=room: self.join_chatroom(r))
            join_btn.pack(side=tk.RIGHT)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_chatroom(self):
        create_window = tk.Toplevel(self.window)
        create_window.title("创建聊天室")
        create_window.geometry("400x200")
        create_window.configure(bg='#ecf0f1')
        create_window.transient(self.window)  # 设置为模态窗口
        create_window.grab_set()  # 捕获所有事件
        self.center_window(create_window, 400, 200)  # 居中窗口
        
        # 使用Frame包装内容，使其居中
        main_frame = ttk.Frame(create_window, style='Content.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 使用Grid布局让标签和输入框在同一行
        ttk.Label(main_frame, text="聊天室名称:", background='#ecf0f1').grid(row=0, column=0, padx=10, pady=10, sticky='e')
        name_entry = ttk.Entry(main_frame, width=20)
        name_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')
        
        ttk.Label(main_frame, text="密码(可选):", background='#ecf0f1').grid(row=1, column=0, padx=10, pady=10, sticky='e')
        password_entry = ttk.Entry(main_frame, width=20, show="*")
        password_entry.grid(row=1, column=1, padx=10, pady=10, sticky='w')
        
        btn_frame = ttk.Frame(main_frame, style='Content.TFrame')
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        confirm_btn = ttk.Button(btn_frame, text="创建", style='Action.TButton',
                                command=lambda: self.confirm_create_chatroom(
                                    name_entry.get(), password_entry.get(), create_window))
        confirm_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(btn_frame, text="取消", style='Action.TButton',
                               command=create_window.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def confirm_create_chatroom(self, name, password, window):
        if not name:
            messagebox.showerror("错误", "聊天室名称不能为空")
            return
        
        window.destroy()
        messagebox.showinfo("成功", f"聊天室 '{name}' 创建成功!")
    
    def join_chatroom(self, room_name):
        messagebox.showinfo("加入聊天室", f"已加入 {room_name}")
    
    def show_friends(self):
        self.clear_content()
        ttk.Label(self.content_frame, text="好友列表", 
                 font=('Arial', 16, 'bold'), background='#ecf0f1').pack(pady=10)
        
        # 检查是否登录
        if not self.is_logged_in():
            ttk.Label(self.content_frame, text="请先登录才能查看好友", 
                     background='#ecf0f1').pack(pady=20)
            return
        
        # 模拟好友列表
        friends = [("好友1", "在线"), ("好友2", "离线"), ("好友3", "游戏中")]
        
        for name, status in friends:
            friend_frame = ttk.Frame(self.content_frame, style='Content.TFrame')
            friend_frame.pack(fill=tk.X, padx=20, pady=5)
            
            status_color = "green" if status == "在线" else "gray"
            ttk.Label(friend_frame, text=name, width=10, background='#ecf0f1').pack(side=tk.LEFT)
            ttk.Label(friend_frame, text=status, foreground=status_color, 
                     background='#ecf0f1').pack(side=tk.LEFT)
    
    def show_profile(self):
        self.clear_content()
        ttk.Label(self.content_frame, text="个人信息", 
                 font=('Arial', 16, 'bold'), background='#ecf0f1').pack(pady=10)
        
        # 检查是否登录
        if not self.is_logged_in():
            ttk.Label(self.content_frame, text="请先登录才能查看个人信息", 
                     background='#ecf0f1').pack(pady=20)
            
            btn_frame = ttk.Frame(self.content_frame, style='Content.TFrame')
            btn_frame.pack(pady=10)
            
            login_btn = ttk.Button(btn_frame, text="登录", style='Action.TButton',
                                  command=self.show_login)
            login_btn.pack(side=tk.LEFT, padx=10)
            
            register_btn = ttk.Button(btn_frame, text="注册", style='Action.TButton',
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
        
        info_frame = ttk.Frame(self.content_frame, style='Content.TFrame')
        info_frame.pack(pady=20)
        
        for i, (key, value) in enumerate(user_info.items()):
            ttk.Label(info_frame, text=f"{key}:", background='#ecf0f1', 
                     font=('Arial', 12, 'bold')).grid(row=i, column=0, sticky=tk.W, pady=5, padx=10)
            ttk.Label(info_frame, text=value, background='#ecf0f1').grid(row=i, column=1, sticky=tk.W, pady=5)
    
    def show_login(self):
        login_window = tk.Toplevel(self.window)
        login_window.title("登录")
        login_window.geometry("400x200")
        login_window.configure(bg='#ecf0f1')
        login_window.transient(self.window)  # 设置为模态窗口
        login_window.grab_set()  # 捕获所有事件
        self.center_window(login_window, 400, 200)  # 居中窗口
        
        # 使用Frame包装内容，使其居中
        main_frame = ttk.Frame(login_window, style='Content.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 使用Grid布局让标签和输入框在同一行
        ttk.Label(main_frame, text="用户名:", background='#ecf0f1').grid(row=0, column=0, padx=10, pady=10, sticky='e')
        username_entry = ttk.Entry(main_frame, width=20)
        username_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')
        
        ttk.Label(main_frame, text="密码:", background='#ecf0f1').grid(row=1, column=0, padx=10, pady=10, sticky='e')
        password_entry = ttk.Entry(main_frame, width=20, show="*")
        password_entry.grid(row=1, column=1, padx=10, pady=10, sticky='w')
        
        btn_frame = ttk.Frame(main_frame, style='Content.TFrame')
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        
        login_btn = ttk.Button(btn_frame, text="登录", style='Action.TButton',
                              command=lambda: self.do_login(
                                  username_entry.get(), password_entry.get(), login_window))
        login_btn.pack(side=tk.LEFT, padx=5)
        
        register_btn = ttk.Button(btn_frame, text="注册", style='Action.TButton',
                                 command=lambda: self.show_register_from_login(login_window))
        register_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(btn_frame, text="取消", style='Action.TButton',
                               command=login_window.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def show_register(self):
        register_window = tk.Toplevel(self.window)
        register_window.title("注册")
        register_window.geometry("400x250")
        register_window.configure(bg='#ecf0f1')
        register_window.transient(self.window)  # 设置为模态窗口
        register_window.grab_set()  # 捕获所有事件
        self.center_window(register_window, 400, 250)  # 居中窗口
        
        # 使用Frame包装内容，使其居中
        main_frame = ttk.Frame(register_window, style='Content.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 使用Grid布局让标签和输入框在同一行
        ttk.Label(main_frame, text="用户名:", background='#ecf0f1').grid(row=0, column=0, padx=10, pady=10, sticky='e')
        username_entry = ttk.Entry(main_frame, width=20)
        username_entry.grid(row=0, column=1, padx=10, pady=10, sticky='w')
        
        ttk.Label(main_frame, text="密码:", background='#ecf0f1').grid(row=1, column=0, padx=10, pady=10, sticky='e')
        password_entry = ttk.Entry(main_frame, width=20, show="*")
        password_entry.grid(row=1, column=1, padx=10, pady=10, sticky='w')
        
        ttk.Label(main_frame, text="确认密码:", background='#ecf0f1').grid(row=2, column=0, padx=10, pady=10, sticky='e')
        confirm_password_entry = ttk.Entry(main_frame, width=20, show="*")
        confirm_password_entry.grid(row=2, column=1, padx=10, pady=10, sticky='w')
        
        btn_frame = ttk.Frame(main_frame, style='Content.TFrame')
        btn_frame.grid(row=3, column=0, columnspan=2, pady=15)
        
        register_btn = ttk.Button(btn_frame, text="注册", style='Action.TButton',
                                 command=lambda: self.do_register(
                                     username_entry.get(), password_entry.get(), 
                                     confirm_password_entry.get(), register_window))
        register_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(btn_frame, text="取消", style='Action.TButton',
                               command=register_window.destroy)
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
        self.show_login()
    
    def is_logged_in(self):
        # 这里应该检查用户是否已登录
        return False
    
    def is_connected(self):
        # 这里应该检查网络连接状态
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