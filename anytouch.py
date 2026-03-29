"""
远程触摸板 - 手机访问 Web 页面，远程同步操作电脑鼠标
用法: python anytouch.py
然后手机浏览器访问 http://<电脑IP>:8866
"""

import json
import socket
import platform
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from ctypes import windll

# ── Windows 鼠标控制 (mouse_event API) ────────────────────────

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000

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


def mouse_hscroll(delta):
    user32.mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, int(delta), 0)


# ── 键盘输入 (剪贴板粘贴) ─────────────────────────────────────


def type_text(text):
    """通过剪贴板粘贴文本到当前焦点位置"""
    import win32clipboard
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
    win32clipboard.CloseClipboard()
    VK_CONTROL = 0x11
    VK_V = 0x56
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 2, 0)
    user32.keybd_event(VK_CONTROL, 0, 2, 0)


# ── 消息处理 ──────────────────────────────────────────────────

VK_MAP = {
    "backspace": 0x08, "enter": 0x0D, "esc": 0x1B, "tab": 0x09,
    "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "f1":0x70,"f2":0x71,"f3":0x72,"f4":0x73,"f5":0x74,"f6":0x75,
    "f7":0x76,"f8":0x77,"f9":0x78,"f10":0x79,"f11":0x7A,"f12":0x7B,
    "prtsc": 0x2C, "pause": 0x13, "scrolllock": 0x91, "numlock": 0x90,
}


def handle_msg(data):
    t = data.get("t")
    if t == "move":
        mouse_move(data["dx"], data["dy"])
    elif t == "click":
        mouse_click()
    elif t == "rclick":
        mouse_right_click()
    elif t == "scroll":
        mouse_scroll(data["d"])
    elif t == "hscroll":
        mouse_hscroll(data["d"])
    elif t == "dragstart":
        mouse_down()
    elif t == "dragend":
        mouse_up()
    elif t == "type":
        text = data.get("text", "")
        if text:
            mouse_click()
            import time; time.sleep(0.05)
            type_text(text)
    elif t == "key":
        key = data.get("key", "")
        mod_ctrl = data.get("ctrl", False)
        mod_alt = data.get("alt", False)
        mod_shift = data.get("shift", False)
        mod_win = data.get("win", False)
        vk = VK_MAP.get(key)
        if vk is not None:
            if mod_ctrl: user32.keybd_event(0x11, 0, 0, 0)
            if mod_alt:  user32.keybd_event(0x12, 0, 0, 0)
            if mod_shift:user32.keybd_event(0x10, 0, 0, 0)
            if mod_win:  user32.keybd_event(0x5B, 0, 0, 0)
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
            if mod_win:  user32.keybd_event(0x5B, 0, 2, 0)
            if mod_shift:user32.keybd_event(0x10, 0, 2, 0)
            if mod_alt:  user32.keybd_event(0x12, 0, 2, 0)
            if mod_ctrl: user32.keybd_event(0x11, 0, 2, 0)


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
#btns button.pressed{box-shadow:0 0 20px rgba(0,0,0,.5),inset 0 4px 12px rgba(0,0,0,.3);
  background:linear-gradient(180deg,#c0c0c0 0%,#b8b8b8 100%);transform:scale(.96)}
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
body.dark #btns button.pressed{box-shadow:0 0 20px rgba(0,0,0,.8),inset 0 4px 12px rgba(0,0,0,.5);
  background:linear-gradient(180deg,#1e1e1e 0%,#181818 100%);transform:scale(.96)}
</style>
</head>
<body>
<div id="main">
  <div id="pad" data-status="{{HOSTNAME}} - 连接中...">
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
const hostname='{{HOSTNAME}}';

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
</script>
<script>
/* ── WebSocket 连接 ── */
let ws=null,wsReady=false;
function setStatus(s){pad.dataset.status=hostname+' - '+s;}

function connectWS(){
  const proto=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(proto+'//'+location.hostname+':{{WS_PORT}}');
  ws.onopen=()=>{wsReady=true;setStatus('已连接');};
  ws.onclose=()=>{wsReady=false;setStatus('连接断开');setTimeout(connectWS,1500);};
  ws.onerror=()=>{ws.close();};
}
connectWS();

function send(data){
  if(wsReady&&ws.readyState===1) ws.send(JSON.stringify(data));
}
</script>
<script>
const SENSITIVITY=1.8;
const SCROLL_SENSITIVITY=2.0;
const DOUBLE_TAP_MS=180;
let lastX=0,lastY=0,touching=false,fingers=0;
let scrollLastY=0,scrollLastX=0,scrolling=false,scrollEndTime=0,scrollLastTime=0;
const SCROLL_GUARD_MS=300;
const SCROLL_SPEED_THRESHOLD=1.5; /* 速度阈值，超过才加速 */
let dragging=false,moved=false,maxFingers=0,totalDist=0;
const MOVE_THRESHOLD=6; /* 累计移动超过此值才算真正移动 */
let lastTapTime=0,waitingSecondTap=false;
let tapTimer=null,longPressTimer=null;
const LONG_PRESS_MS=500;

function startDrag(){
  dragging=true;pad.classList.add('dragging');
  send({t:'dragstart'});
  if(navigator.vibrate) navigator.vibrate(50);
}
function endDrag(){
  if(dragging){dragging=false;pad.classList.remove('dragging');send({t:'dragend'});}
}

pad.addEventListener('touchstart',e=>{
  e.preventDefault();
  fingers=e.touches.length;
  if(fingers>maxFingers) maxFingers=fingers;
  moved=false;totalDist=0;
  if(fingers===1){
    lastX=e.touches[0].clientX;lastY=e.touches[0].clientY;
    const now=Date.now();
    if(waitingSecondTap&&(now-lastTapTime)<DOUBLE_TAP_MS){
      waitingSecondTap=false;
      if(tapTimer){clearTimeout(tapTimer);tapTimer=null;}
      /* 双击：发送两次点击 */
      send({t:'click'});
      setTimeout(()=>send({t:'click'}),30);
    }
    /* 长按进入拖动 */
    longPressTimer=setTimeout(()=>{
      if(!moved&&!dragging){startDrag();}
    },LONG_PRESS_MS);
  }else if(fingers===2){
    if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null;}
    scrollLastY=(e.touches[0].clientY+e.touches[1].clientY)/2;
    scrollLastX=(e.touches[0].clientX+e.touches[1].clientX)/2;
    scrollLastTime=Date.now();
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
    totalDist+=Math.abs(dx)+Math.abs(dy);
    if(totalDist>MOVE_THRESHOLD){
      if(!moved){
        moved=true;
        if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null;}
      }
      if(dragging){send({t:'move',dx,dy});}
      else{send({t:'move',dx,dy});}
    }
  }else if(e.touches.length===2){
    const curY=(e.touches[0].clientY+e.touches[1].clientY)/2;
    const curX=(e.touches[0].clientX+e.touches[1].clientX)/2;
    const dy=(curY-scrollLastY)*SCROLL_SENSITIVITY;
    const dx=(curX-scrollLastX)*SCROLL_SENSITIVITY;
    const now=Date.now();
    const dt=Math.max(now-scrollLastTime,1);
    scrollLastY=curY;scrollLastX=curX;scrollLastTime=now;
    /* 速度=位移/时间，慢速匀速，快速拉动才加速 */
    const speedY=Math.abs(dy)/dt;
    const speedX=Math.abs(dx)/dt;
    const accelY=speedY>SCROLL_SPEED_THRESHOLD?1+Math.min((speedY-SCROLL_SPEED_THRESHOLD)*0.8,2):1;
    const accelX=speedX>SCROLL_SPEED_THRESHOLD?1+Math.min((speedX-SCROLL_SPEED_THRESHOLD)*0.8,2):1;
    if(Math.abs(dy)>1){scrolling=true;send({t:'scroll',d:dy*accelY*3});}
    if(Math.abs(dx)>1){scrolling=true;send({t:'hscroll',d:-dx*accelX*3});}
  }
},{passive:false});

pad.addEventListener('touchend',e=>{
  e.preventDefault();
  if(dragging){if(e.touches.length===0) endDrag();}
  else if(maxFingers===1&&fingers===1&&touching&&!moved){
    const now=Date.now();lastTapTime=now;waitingSecondTap=true;
    if(tapTimer) clearTimeout(tapTimer);
    tapTimer=setTimeout(()=>{waitingSecondTap=false;send({t:'click'});},DOUBLE_TAP_MS);
  }
  if(e.touches.length===0){
    if(scrolling){scrolling=false;scrollEndTime=Date.now();}
    touching=false;fingers=0;maxFingers=0;
    if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null;}}
},{passive:false});

function btnGuard(){return scrolling||Date.now()-scrollEndTime<SCROLL_GUARD_MS;}
btnL.addEventListener('touchstart',e=>{e.preventDefault();e.stopPropagation();if(btnGuard())return;btnL.classList.add('pressed');send({t:'click'});if(navigator.vibrate)navigator.vibrate(30);});
btnR.addEventListener('touchstart',e=>{e.preventDefault();e.stopPropagation();if(btnGuard())return;btnR.classList.add('pressed');send({t:'rclick'});if(navigator.vibrate)navigator.vibrate(30);});
btnL.addEventListener('touchend',()=>btnL.classList.remove('pressed'));
btnL.addEventListener('touchcancel',()=>btnL.classList.remove('pressed'));
btnR.addEventListener('touchend',()=>btnR.classList.remove('pressed'));
btnR.addEventListener('touchcancel',()=>btnR.classList.remove('pressed'));
btnL.addEventListener('click',()=>send({t:'click'}));
btnR.addEventListener('click',()=>send({t:'rclick'}));
</script>
</body>
</html>"""


# ── HTTP 服务 (仅提供页面) ────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    ws_port = 8867

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        page = HTML_PAGE.replace('{{HOSTNAME}}', platform.node())
        page = page.replace('{{WS_PORT}}', str(self.ws_port))
        self.wfile.write(page.encode())


# ── WebSocket 服务 ────────────────────────────────────────────

async def ws_handler(websocket):
    async for message in websocket:
        try:
            data = json.loads(message)
            handle_msg(data)
        except Exception:
            pass


async def start_ws_server(port):
    import websockets
    async with websockets.serve(ws_handler, "0.0.0.0", port):
        await asyncio.Future()  # 永远运行


def run_ws(port):
    asyncio.run(start_ws_server(port))


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


def main(http_port=8866, ws_port=8867):
    ip = get_local_ip()
    Handler.ws_port = ws_port
    url = f"http://{ip}:{http_port}"

    # 启动 WebSocket 服务 (后台线程)
    ws_thread = threading.Thread(target=run_ws, args=(ws_port,), daemon=True)
    ws_thread.start()

    # 启动 HTTP 服务
    server = HTTPServer(("0.0.0.0", http_port), Handler)
    print(f"远程触摸板已启动")
    print(f"  本机访问: http://127.0.0.1:{http_port}")
    print(f"  手机访问: {url}")
    print(f"  WebSocket: ws://{ip}:{ws_port}")
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
