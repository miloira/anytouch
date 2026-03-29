"""
远程触摸板 - 手机访问 Web 页面，远程同步操作电脑鼠标
用法: python remote_mouse.py
然后手机浏览器访问 http://<电脑IP>:8866
"""

import json
import socket
import platform
from http.server import HTTPServer, BaseHTTPRequestHandler
from ctypes import windll

# ── Windows 鼠标控制 (mouse_event API) ────────────────────────

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800

user32 = windll.user32
screen_w = user32.GetSystemMetrics(0)
screen_h = user32.GetSystemMetrics(1)


def mouse_move(dx, dy):
    user32.mouse_event(MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)


def mouse_click():
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def mouse_right_click():
    user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)


def mouse_down():
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)


def mouse_up():
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def mouse_scroll(delta):
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(delta), 0)


# ── 键盘输入 (剪贴板粘贴) ─────────────────────────────────────


def type_text(text):
    """通过剪贴板粘贴文本到当前焦点位置"""
    import win32clipboard
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
    win32clipboard.CloseClipboard()
    # 模拟 Ctrl+V
    VK_CONTROL = 0x11
    VK_V = 0x56
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 2, 0)       # KEYEVENTF_KEYUP
    user32.keybd_event(VK_CONTROL, 0, 2, 0)  # KEYEVENTF_KEYUP


# ── HTML 页面 ─────────────────────────────────────────────────

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>远程触摸板</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none;user-select:none}
body{background:#bdbdbd;color:#333;font-family:system-ui;display:flex;flex-direction:column;
  height:100vh;height:100dvh;overflow:hidden;touch-action:none;padding:0}
#main{flex:1;display:flex;flex-direction:column;gap:0;overflow:hidden;min-height:0;
  background:linear-gradient(145deg,#d0d0d0,#b8b8b8);border-bottom:2px solid #a0a0a0}
#pad{flex:1;background:linear-gradient(180deg,#dcdcdc 0%,#c8c8c8 100%);
  display:flex;align-items:center;justify-content:center;position:relative;
  box-shadow:inset 0 2px 10px rgba(0,0,0,.1),inset 0 -1px 4px rgba(255,255,255,.3);
  min-height:0;border-bottom:2px solid #888}
#pad::after{content:attr(data-status);color:#aaa;font-size:.7em;pointer-events:none;
  position:absolute;top:8px;text-shadow:0 1px 0 rgba(255,255,255,.5)}
#pad.dragging{background:linear-gradient(180deg,#d0d0d0 0%,#bebebe 100%);
  box-shadow:inset 0 3px 14px rgba(0,0,0,.2)}
#btns{display:flex;height:80px}
#btns button{flex:1;border:none;font-size:1em;font-weight:500;letter-spacing:.5px;
  background:linear-gradient(180deg,#dcdcdc 0%,#c8c8c8 100%);color:#444;
  cursor:pointer;transition:all .12s ease;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 1px 2px rgba(0,0,0,.1)}
#btns button:first-child{border-right:2px solid #888}
#btns button:active{box-shadow:0 0 12px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.25)}
#themeBtn{position:absolute;top:6px;right:8px;background:none;border:none;font-size:1.2em;
  cursor:pointer;opacity:.5;z-index:1;line-height:1}
#themeBtn:active{opacity:.8}
body.dark{background:#1a1a1a}
body.dark #main{background:linear-gradient(145deg,#2a2a2a,#1e1e1e);border-bottom-color:#111}
body.dark #pad{background:linear-gradient(180deg,#2c2c2c 0%,#222 100%);
  box-shadow:inset 0 2px 10px rgba(0,0,0,.4),inset 0 -1px 4px rgba(255,255,255,.05);
  border-bottom-color:#111}
body.dark #pad::after{color:#555;text-shadow:none}
body.dark #pad.dragging{background:linear-gradient(180deg,#262626 0%,#1e1e1e 100%);
  box-shadow:inset 0 3px 14px rgba(0,0,0,.5)}
body.dark #btns button{background:linear-gradient(180deg,#2c2c2c 0%,#222 100%);color:#888;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 1px 2px rgba(0,0,0,.3)}
body.dark #btns button:first-child{border-right-color:#111}
body.dark #btns button:active{box-shadow:0 0 12px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.05)}
</style>
</head>
<body>
<div id="main">
  <div id="pad" data-status="{{HOSTNAME}} - 已连接">
    <button id="themeBtn">🌙</button>
  </div>
  <div id="btns">
    <button id="btnL"></button>
    <button id="btnR"></button>
  </div>
</div>
<script>
const pad=document.getElementById('pad');
const btnL=document.getElementById('btnL');
const btnR=document.getElementById('btnR');
const themeBtn=document.getElementById('themeBtn');

if(localStorage.getItem('dark')==='1'){document.body.classList.add('dark');themeBtn.textContent='☀️';}
themeBtn.addEventListener('click',e=>{
  e.stopPropagation();
  const dark=document.body.classList.toggle('dark');
  themeBtn.textContent=dark?'☀️':'🌙';
  localStorage.setItem('dark',dark?'1':'0');
});
themeBtn.addEventListener('touchstart',e=>{e.stopPropagation();});
themeBtn.addEventListener('touchend',e=>{
  e.stopPropagation();e.preventDefault();
  const dark=document.body.classList.toggle('dark');
  themeBtn.textContent=dark?'☀️':'🌙';
  localStorage.setItem('dark',dark?'1':'0');
});

const SENSITIVITY=1.8;
const SCROLL_SENSITIVITY=2.0;
const DOUBLE_TAP_MS=300;
const DRAG_THRESHOLD=6;
let lastX=0,lastY=0,touching=false,fingers=0;
let scrollLastY=0;
let dragging=false,moved=false;
let lastTapTime=0,waitingSecondTap=false;
let tapTimer=null;

function send(data){
  fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(data)}).catch(()=>{});
}

function startDrag(){
  dragging=true;
  pad.classList.add('dragging');
  send({t:'dragstart'});
  if(navigator.vibrate) navigator.vibrate(50);
}

function endDrag(){
  if(dragging){
    dragging=false;
    pad.classList.remove('dragging');
    send({t:'dragend'});
  }
}

pad.addEventListener('touchstart',e=>{
  e.preventDefault();
  fingers=e.touches.length;
  moved=false;
  if(fingers===1){
    lastX=e.touches[0].clientX;lastY=e.touches[0].clientY;
    const now=Date.now();
    if(waitingSecondTap&&(now-lastTapTime)<DOUBLE_TAP_MS){
      /* 双击第二下落下，准备拖动 */
      waitingSecondTap=false;
      if(tapTimer){clearTimeout(tapTimer);tapTimer=null;}
      startDrag();
    }
  }else if(fingers===2){
    scrollLastY=(e.touches[0].clientY+e.touches[1].clientY)/2;
  }
  touching=true;
},{passive:false});

pad.addEventListener('touchmove',e=>{
  e.preventDefault();
  if(!touching)return;
  if(e.touches.length===1&&fingers===1){
    const dx=(e.touches[0].clientX-lastX)*SENSITIVITY;
    const dy=(e.touches[0].clientY-lastY)*SENSITIVITY;
    lastX=e.touches[0].clientX;lastY=e.touches[0].clientY;
    if(Math.abs(dx)>0.5||Math.abs(dy)>0.5){
      moved=true;
      send({t:'move',dx:dx,dy:dy});
    }
  }else if(e.touches.length===2){
    const curY=(e.touches[0].clientY+e.touches[1].clientY)/2;
    const dy=(curY-scrollLastY)*SCROLL_SENSITIVITY;
    scrollLastY=curY;
    if(Math.abs(dy)>1) send({t:'scroll',d:dy*3});
  }
},{passive:false});

pad.addEventListener('touchend',e=>{
  e.preventDefault();
  if(dragging){
    if(e.touches.length===0) endDrag();
  }else if(fingers===1&&touching&&!moved){
    /* 轻点抬起：记录时间，延迟发送单击（等看是否有第二次点击） */
    const now=Date.now();
    lastTapTime=now;
    waitingSecondTap=true;
    if(tapTimer) clearTimeout(tapTimer);
    tapTimer=setTimeout(()=>{
      /* 超时没有第二次点击，发送普通单击 */
      waitingSecondTap=false;
      send({t:'click'});
    },DOUBLE_TAP_MS);
  }
  if(e.touches.length===0){touching=false;fingers=0;}
},{passive:false});

btnL.addEventListener('click',()=>send({t:'click'}));
btnR.addEventListener('click',()=>send({t:'rclick'}));

const hostname=pad.dataset.status.split(' - ')[0];
function checkConn(){
  const ctrl=new AbortController();
  const tm=setTimeout(()=>ctrl.abort(),2000);
  fetch('/ping',{signal:ctrl.signal})
    .then(r=>{clearTimeout(tm);pad.dataset.status=hostname+(r.ok?' - 已连接':' - 连接断开')})
    .catch(()=>{clearTimeout(tm);pad.dataset.status=hostname+' - 连接断开'});
}
setInterval(checkConn,2000);
</script>
</body>
</html>"""


# ── HTTP 服务 ─────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静默日志

    def do_GET(self):
        if self.path == "/ping":
            self._json_resp({"ok": True})
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.replace('{{HOSTNAME}}', platform.node()).encode())

    def do_POST(self):
        if self.path != "/api":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length))
        t = data.get("t")
        if t == "move":
            mouse_move(data["dx"], data["dy"])
        elif t == "click":
            mouse_click()
            print("[点击] 左键")
        elif t == "rclick":
            mouse_right_click()
            print("[点击] 右键")
        elif t == "scroll":
            mouse_scroll(data["d"])
        elif t == "dragstart":
            mouse_down()
            print("[拖动] 开始")
        elif t == "dragend":
            mouse_up()
            print("[拖动] 结束")
        elif t == "type":
            text = data.get("text", "")
            if text:
                mouse_click()  # 先点击当前鼠标位置获取焦点
                import time; time.sleep(0.05)
                type_text(text)
                print(f"[输入] {text}")
        elif t == "key":
            key = data.get("key", "")
            mod_ctrl = data.get("ctrl", False)
            mod_alt = data.get("alt", False)
            mod_shift = data.get("shift", False)
            mod_win = data.get("win", False)
            VK_MAP = {
                "backspace": 0x08, "enter": 0x0D, "esc": 0x1B, "tab": 0x09,
                "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E,
                "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
                "f1":0x70,"f2":0x71,"f3":0x72,"f4":0x73,"f5":0x74,"f6":0x75,
                "f7":0x76,"f8":0x77,"f9":0x78,"f10":0x79,"f11":0x7A,"f12":0x7B,
                "prtsc": 0x2C, "pause": 0x13, "scrolllock": 0x91, "numlock": 0x90,
            }
            vk = VK_MAP.get(key)
            if vk is not None:
                # 按下修饰键
                if mod_ctrl: user32.keybd_event(0x11, 0, 0, 0)
                if mod_alt:  user32.keybd_event(0x12, 0, 0, 0)
                if mod_shift:user32.keybd_event(0x10, 0, 0, 0)
                if mod_win:  user32.keybd_event(0x5B, 0, 0, 0)
                user32.keybd_event(vk, 0, 0, 0)
                user32.keybd_event(vk, 0, 2, 0)
                # 释放修饰键
                if mod_win:  user32.keybd_event(0x5B, 0, 2, 0)
                if mod_shift:user32.keybd_event(0x10, 0, 2, 0)
                if mod_alt:  user32.keybd_event(0x12, 0, 2, 0)
                if mod_ctrl: user32.keybd_event(0x11, 0, 2, 0)
                mods = [m for m, v in [("Ctrl",mod_ctrl),("Alt",mod_alt),("Shift",mod_shift),("Win",mod_win)] if v]
                prefix = "+".join(mods) + "+" if mods else ""
                print(f"[按键] {prefix}{key}")
        self._json_resp({"ok": True})

    def _json_resp(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def get_local_ip():
    """获取局域网 IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def print_qr(url):
    """在终端打印二维码"""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        print("  (安装 qrcode 可显示二维码: pip install qrcode)")


def main(port=8866):
    ip = get_local_ip()
    server = HTTPServer(("0.0.0.0", port), Handler)
    url = f"http://{ip}:{port}"
    print(f"远程触摸板已启动")
    print(f"  本机访问: http://127.0.0.1:{port}")
    print(f"  手机访问: {url}")
    print(f"  屏幕分辨率: {screen_w}x{screen_h}")
    print()
    print("扫码连接:")
    print_qr(url)
    print()
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main() 

