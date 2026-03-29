"""
AnyTouch GUI - 基于 tkinter 的交互界面
打开即启动服务，显示二维码、连接信息和日志
"""

import tkinter as tk
from tkinter import ttk
import threading
import random

import anytouch
from anytouch import Handler, run_ws, get_local_ip
from http.server import HTTPServer

HTTP_PORT = 8866
WS_PORT = 8867


class AnyTouchGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AnyTouch 远程触摸板")
        self.root.geometry("380x360")
        self.root.resizable(False, False)
        self.server = None

        self.ip = get_local_ip()
        self.token = f"{random.randint(0, 999999):06d}"
        self.url = f"http://{self.ip}:{HTTP_PORT}?token={self.token}"

        self._build_ui()
        self._start_server()
        self._register_callbacks()

    def _build_ui(self):
        # 标题
        tk.Label(self.root, text="AnyTouch", font=("Microsoft YaHei UI", 15, "bold")).pack(pady=(14, 2))
        tk.Label(self.root, text="手机扫码，远程控制电脑鼠标", font=("Microsoft YaHei UI", 9), fg="#888").pack()

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=20, pady=10)

        # 二维码
        self.qr_label = tk.Label(self.root)
        self.qr_label.pack()
        self._show_qr()

        # 验证码显示
        tk.Label(self.root, text="验证码", font=("Microsoft YaHei UI", 9), fg="#888").pack(pady=(6, 0))
        tk.Label(self.root, text=self.token, font=("Consolas", 22, "bold"), fg="#1565C0").pack()

        # 设备状态标签（二维码下方）
        self.device_label = tk.Label(self.root, text="", font=("Microsoft YaHei UI", 10), fg="#4CAF50")
        self.device_label.pack(pady=(4, 0))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=20, pady=10)

        # 连接地址
        tk.Label(self.root, text=self.url, font=("Consolas", 11), fg="#1565C0").pack(pady=(0, 10))

    def _register_callbacks(self):
        def on_connect(device_name):
            self.root.after(0, lambda: self.device_label.config(text=f"设备：{device_name} 正在控制中", fg="#4CAF50"))

        def on_disconnect():
            self.root.after(0, lambda: self.device_label.config(text=""))

        anytouch.on_device_connect = on_connect
        anytouch.on_device_disconnect = on_disconnect

    def _start_server(self):
        Handler.ws_port = WS_PORT
        Handler.token = self.token
        anytouch.ws_token = self.token
        try:
            self.server = HTTPServer(("0.0.0.0", HTTP_PORT), Handler)
        except OSError:
            return

        threading.Thread(target=run_ws, args=(WS_PORT,), daemon=True).start()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _show_qr(self):
        try:
            import qrcode
            from PIL import Image, ImageTk
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(self.url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").resize((140, 140), Image.NEAREST)
            self._qr_photo = ImageTk.PhotoImage(img)
            self.qr_label.config(image=self._qr_photo)
        except ImportError:
            self.qr_label.config(text="pip install qrcode pillow\n即可显示二维码", font=("Microsoft YaHei UI", 9), fg="#aaa")


def main():
    root = tk.Tk()
    app = AnyTouchGUI(root)

    tray_icon = None

    def create_tray():
        nonlocal tray_icon
        from pystray import Icon, MenuItem, Menu
        from PIL import Image, ImageDraw

        # 生成一个简单的托盘图标
        img = Image.new("RGB", (64, 64), "#1565C0")
        d = ImageDraw.Draw(img)
        d.rectangle([8, 8, 56, 56], fill="#fff")
        d.rectangle([12, 12, 52, 52], fill="#1565C0")
        d.text((18, 16), "AT", fill="#fff")

        def on_show(icon, item):
            icon.stop()
            root.after(0, root.deiconify)

        def on_quit(icon, item):
            icon.stop()
            root.after(0, _real_quit)

        tray_icon = Icon("AnyTouch", img, "AnyTouch 远程触摸板",
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
