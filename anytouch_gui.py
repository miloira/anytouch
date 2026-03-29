"""
AnyTouch GUI - 基于 tkinter 的交互界面
打开即启动服务，显示二维码、连接信息和日志
"""

import tkinter as tk
from tkinter import ttk
import threading
import random

import anytouch
from anytouch import Handler, run_ws, get_local_ip, get_free_port
from http.server import HTTPServer

BG = "#0a0a0a"
BG_CARD = "#0d1a0d"
FG = "#33ff33"
FG_DIM = "#1a8c1a"
ACCENT = "#00ff41"
GREEN = "#00ff41"


class AnyTouchGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AnyTouch")
        self.root.geometry("400x425")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # 窗口标题栏图标
        import sys, os
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base, "AnyTouch.ico")
        if os.path.exists(ico_path):
            self.root.iconbitmap(ico_path)
        self.server = None

        self.ip = get_local_ip()
        self.http_port = get_free_port()
        self.ws_port = get_free_port()
        self.code = f"{random.randint(0, 999999):06d}"
        self.url = f"http://{self.ip}:{self.http_port}?code={self.code}"

        self._build_ui()
        self._start_server()
        self._register_callbacks()

    def _label(self, text, **kwargs):
        defaults = {"bg": BG, "fg": FG}
        defaults.update(kwargs)
        return tk.Label(self.root, text=text, **defaults)

    def _selectable(self, text, parent=None, **kwargs):
        """可选中复制的只读文本"""
        p = parent or self.root
        e = tk.Entry(p, readonlybackground=BG_CARD, relief="flat",
                     borderwidth=0, highlightthickness=0, justify="center",
                     selectbackground="#0f3d0f", selectforeground=ACCENT, **kwargs)
        e.insert(0, text)
        e.config(state="readonly")
        return e

    def _build_ui(self):
        # 标题
        self._label("AnyTouch", font=("Consolas", 18, "bold"), fg=ACCENT).pack(pady=(14, 0))
        self._label("远程触控板", font=("Microsoft YaHei UI", 9), fg=FG).pack(pady=(0, 4))

        # 卡片容器
        card = tk.Frame(self.root, bg=BG_CARD, highlightbackground="#0f3d0f", highlightthickness=1)
        card.pack(fill="x", padx=24, pady=(4, 0))

        # 方式一
        tk.Label(card, text="方式一：手机扫描二维码连接",
                 font=("Microsoft YaHei UI", 9, "bold"), fg=FG, bg=BG_CARD).pack(pady=(10, 4))

        # 二维码
        self.qr_label = tk.Label(card, bg=BG_CARD)
        self.qr_label.pack()
        self._show_qr()

        # 分隔线
        tk.Frame(card, bg="#0f3d0f", height=1).pack(fill="x", padx=16, pady=8)

        # 方式二
        tk.Label(card, text="方式二：手机访问地址，输入验证码连接",
                 font=("Microsoft YaHei UI", 9, "bold"), fg=FG, bg=BG_CARD).pack(pady=(0, 2))
        self._selectable(f"http://{self.ip}:{self.http_port}", parent=card,
                         font=("Consolas", 10), fg=ACCENT).pack(fill="x", padx=16, pady=(2, 0))
        self._selectable(self.code, parent=card,
                         font=("Consolas", 24, "bold"), fg=ACCENT).pack(fill="x", padx=16, pady=(4, 4))

        # 设备状态（卡片内，验证码下方）
        tk.Frame(card, bg="#0f3d0f", height=1).pack(fill="x", padx=16, pady=(4, 0))

        status_row = tk.Frame(card, bg=BG_CARD)
        status_row.pack(fill="x", padx=16, pady=(6, 8))

        self.status_dot = tk.Canvas(status_row, width=10, height=10, bg=BG_CARD, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        self._draw_dot("#555")

        self.device_label = tk.Label(status_row, text="暂无设备连接",
                                     font=("Microsoft YaHei UI", 9), fg=FG_DIM, bg=BG_CARD)
        self.device_label.pack(side="left")

    def _draw_dot(self, color):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill=color, outline=color)

    def _register_callbacks(self):
        def on_connect(device_name):
            def _update():
                self._draw_dot(GREEN)
                self.device_label.config(text=f"{device_name} 正在控制中", fg=GREEN)
            self.root.after(0, _update)

        def on_disconnect():
            def _update():
                self._draw_dot("#555")
                self.device_label.config(text="暂无设备连接", fg=FG_DIM)
            self.root.after(0, _update)

        anytouch.on_device_connect = on_connect
        anytouch.on_device_disconnect = on_disconnect

    def _start_server(self):
        Handler.ws_port = self.ws_port
        Handler.code = self.code
        anytouch.ws_code = self.code
        try:
            self.server = HTTPServer(("0.0.0.0", self.http_port), Handler)
        except OSError:
            return

        threading.Thread(target=run_ws, args=(self.ws_port,), daemon=True).start()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _show_qr(self):
        try:
            import qrcode
            from PIL import Image, ImageTk
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(self.url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#00ff41", back_color="#0d1a0d").resize((140, 140), Image.NEAREST)
            self._qr_photo = ImageTk.PhotoImage(img)
            self.qr_label.config(image=self._qr_photo)
        except ImportError:
            self.qr_label.config(text="pip install qrcode pillow\n即可显示二维码",
                                 font=("Microsoft YaHei UI", 9), fg=FG_DIM, bg=BG)


def main():
    # 单实例检查（Windows Mutex）
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "AnyTouch_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(0, "AnyTouch 已在运行中", "AnyTouch", 0x40)
        return

    root = tk.Tk()
    app = AnyTouchGUI(root)

    tray_icon = None

    def create_tray():
        nonlocal tray_icon
        from pystray import Icon, MenuItem, Menu
        from PIL import Image
        import sys, os

        # 兼容 pyinstaller 打包后的路径
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base, "AnyTouch.ico")
        img = Image.open(ico_path)

        def on_show(icon, item):
            icon.stop()
            root.after(0, root.deiconify)

        def on_quit(icon, item):
            icon.stop()
            root.after(0, _real_quit)

        tray_icon = Icon("AnyTouch", img, "AnyTouch",
                         menu=Menu(MenuItem("显示窗口", on_show, default=True),
                                   MenuItem("退出", on_quit)))
        tray_icon.run()

    def on_close():
        root.withdraw()
        threading.Thread(target=create_tray, daemon=True).start()

    def _real_quit():
        if app.server:
            app.server.shutdown()
            app.server.server_close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
