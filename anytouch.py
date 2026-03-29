"""
远程触摸板 - 手机访问 Web 页面，远程同步操作电脑鼠标
用法: python anytouch.py
然后手机浏览器访问 http://<电脑IP>:8866
"""

import json
import re
import socket
import platform
import asyncio
import threading
from datetime import datetime
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
    elif t == "mousedown":
        mouse_down()
    elif t == "mouseup":
        mouse_up()
    elif t == "rmousedown":
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    elif t == "rmouseup":
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
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
#pad::after{content:'';display:none}
#statusBar{position:absolute;top:6px;display:flex;flex-direction:column;align-items:center;gap:2px;pointer-events:auto}
#statusLine{display:flex;align-items:center;gap:5px}
#statusDot{width:7px;height:7px;border-radius:50%;background:#999;flex-shrink:0}
#statusDot.on{background:#4caf50}
#statusDot.off{background:#f44336}
#statusText{color:#aaa;font-size:.65em;text-shadow:0 1px 0 rgba(255,255,255,.5)}
#connText{color:#aaa;font-size:.6em;text-shadow:0 1px 0 rgba(255,255,255,.5)}
#disconnBtn{background:none;border:1px solid #aaa;color:#aaa;font-size:.55em;padding:1px 8px;
  border-radius:6px;cursor:pointer;margin-left:4px}
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
body.dark #statusText{color:#555;text-shadow:none}
body.dark #connText{color:#555;text-shadow:none}
body.dark #disconnBtn{border-color:#555;color:#555}
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
  <div id="pad" data-status="">
    <div id="statusBar">
      <div id="statusLine"><span id="statusDot"></span><span id="statusText">{{HOSTNAME}}</span></div>
      <div id="statusLine2"><span id="connText">连接中...</span><button id="disconnBtn">断开</button></div>
    </div>
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
const statusDot=document.getElementById('statusDot');
const statusText=document.getElementById('statusText');
const connText=document.getElementById('connText');
const disconnBtn=document.getElementById('disconnBtn');

/* dotState: 'on'=设备在线, 'off'=设备离线 */
function setStatus(device,conn,dotState){
  statusText.textContent=hostname+' - '+device;
  connText.textContent=conn;
  statusDot.className=dotState;
  if(dotState==='off'){disconnBtn.style.display='none';}
  else{disconnBtn.style.display='inline-block';disconnBtn.textContent=(conn==='已连接')?'断开':'连接';}
}

let manualDisconn=false;
function doDisconn(){
  manualDisconn=true;wsReady=false;
  if(ws)ws.close();
  setStatus('在线','已断开','on');
}
function doReconn(){
  manualDisconn=false;
  setStatus('在线','连接中...','on');
  connectWS();
}
disconnBtn.addEventListener('click',e=>{
  e.stopPropagation();
  if(wsReady)doDisconn();else if(!wsReady)doReconn();
});
disconnBtn.addEventListener('touchstart',e=>{e.stopPropagation();});
disconnBtn.addEventListener('touchend',e=>{
  e.stopPropagation();e.preventDefault();
  if(wsReady)doDisconn();else if(!wsReady)doReconn();
});

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
let ws=null,wsReady=false,deviceOnline=false,rejectedMask=null,dotTimer=null;

function startWaitDots(){
  if(dotTimer)return;
  let count=0;
  const span=rejectedMask&&rejectedMask.querySelector('.wait-dots');
  if(!span)return;
  dotTimer=setInterval(()=>{
    count=(count+1)%4;
    span.textContent='.'.repeat(count||1);
  },500);
}
function stopWaitDots(){
  if(dotTimer){clearInterval(dotTimer);dotTimer=null;}
}

function checkOnline(cb){
  const ctrl=new AbortController();
  const tm=setTimeout(()=>ctrl.abort(),2000);
  fetch('/ping',{signal:ctrl.signal})
    .then(r=>{clearTimeout(tm);deviceOnline=true;cb(true);})
    .catch(()=>{clearTimeout(tm);deviceOnline=false;cb(false);});
}

function connectWS(){
  if(manualDisconn)return;
  checkOnline(online=>{
    if(!online){setStatus('离线','','off');setTimeout(connectWS,3000);return;}
    setStatus('在线','连接中...','on');
    const proto=location.protocol==='https:'?'wss:':'ws:';
    ws=new WebSocket(proto+'//'+location.hostname+':{{WS_PORT}}'+location.search);
    ws.onopen=()=>{
      ws.send(JSON.stringify({t:'hello',ua:navigator.userAgent}));
    };
    ws.onmessage=e=>{
      try{
        const d=JSON.parse(e.data);
        if(d.t==='accepted'){
          wsReady=true;setStatus('在线','已连接','on');
          if(rejectedMask){rejectedMask.remove();rejectedMask=null;stopWaitDots();}
          return;
        }
        if(d.t==='rejected'){
          wsReady=false;setStatus('在线','已被占用','on');
          if(!rejectedMask){
            rejectedMask=document.createElement('div');
            rejectedMask.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:99';
            rejectedMask.innerHTML='<div style="background:#fff;color:#333;padding:24px 28px;border-radius:12px;text-align:center;max-width:80%;font-size:1em;line-height:1.6">'+d.msg+'<br><span style="font-size:.8em;color:#888;margin-top:8px;display:block">等待设备空闲后自动连接<span class="wait-dots">.</span></span></div>';
            document.body.appendChild(rejectedMask);
            startWaitDots();
          }
          return;}
      }catch(ex){}
    };
    ws.onclose=()=>{wsReady=false;if(!manualDisconn){
      if(!rejectedMask)setStatus('离线','连接断开','off');
      setTimeout(connectWS,1000);
    }};
    ws.onerror=()=>{ws.close();};
  });
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
let tapTimer=null,longPressTimer=null,pendingDblTap=false;
const LONG_PRESS_MS=500;
const DBL_TAP_HOLD_MS=200; /* 双击第二下按住超过此时间进入press down */

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
  const t=e.targetTouches;
  fingers=t.length;
  if(fingers>maxFingers) maxFingers=fingers;
  moved=false;totalDist=0;
  if(fingers===1){
    lastX=t[0].clientX;lastY=t[0].clientY;
    const now=Date.now();
    if(waitingSecondTap&&(now-lastTapTime)<DOUBLE_TAP_MS){
      waitingSecondTap=false;
      if(tapTimer){clearTimeout(tapTimer);tapTimer=null;}
      /* 双击第二下按住：等一小段时间判断是双击还是press down */
      pendingDblTap=true;
      longPressTimer=setTimeout(()=>{
        if(pendingDblTap&&!moved&&!dragging){pendingDblTap=false;startDrag();}
      },DBL_TAP_HOLD_MS);
    } else {
      longPressTimer=setTimeout(()=>{
        if(!moved&&!dragging){startDrag();}
      },LONG_PRESS_MS);
    }
  }else if(fingers===2){
    if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null;}
    scrollLastY=(t[0].clientY+t[1].clientY)/2;
    scrollLastX=(t[0].clientX+t[1].clientX)/2;
    scrollLastTime=Date.now();
  }
  touching=true;
},{passive:false});

pad.addEventListener('touchmove',e=>{
  e.preventDefault();
  if(!touching)return;
  const t=e.targetTouches;
  if(t.length===1&&fingers===1&&!scrolling&&maxFingers===1){
    const dx=(t[0].clientX-lastX)*SENSITIVITY;
    const dy=(t[0].clientY-lastY)*SENSITIVITY;
    lastX=t[0].clientX;lastY=t[0].clientY;
    totalDist+=Math.abs(dx)+Math.abs(dy);
    if(totalDist>MOVE_THRESHOLD){
      if(!moved){
        moved=true;
        if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null;}
        if(pendingDblTap&&!dragging){pendingDblTap=false;startDrag();}
      }
      send({t:'move',dx,dy});
    }
  }else if(t.length===2){
    const curY=(t[0].clientY+t[1].clientY)/2;
    const curX=(t[0].clientX+t[1].clientX)/2;
    const dy=(curY-scrollLastY)*SCROLL_SENSITIVITY;
    const dx=(curX-scrollLastX)*SCROLL_SENSITIVITY;
    const now=Date.now();
    const dt=Math.max(now-scrollLastTime,1);
    scrollLastY=curY;scrollLastX=curX;scrollLastTime=now;
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
  if(dragging){if(e.targetTouches.length===0) endDrag();}
  else if(pendingDblTap&&!moved){
    /* 双击第二下快速松手 = 双击 */
    pendingDblTap=false;
    if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null;}
    send({t:'click'});
    setTimeout(()=>send({t:'click'}),30);
  }
  else if(maxFingers===2&&!scrolling&&!moved&&touching){
    /* 双指轻点 = 右键 */
    send({t:'rclick'});
  }
  else if(maxFingers===1&&fingers===1&&touching&&!moved){
    const now=Date.now();lastTapTime=now;waitingSecondTap=true;
    if(tapTimer) clearTimeout(tapTimer);
    tapTimer=setTimeout(()=>{waitingSecondTap=false;send({t:'click'});},DOUBLE_TAP_MS);
  }
  if(e.targetTouches.length===0){
    if(scrolling){scrolling=false;scrollEndTime=Date.now();}
    touching=false;fingers=0;maxFingers=0;pendingDblTap=false;
    if(longPressTimer){clearTimeout(longPressTimer);longPressTimer=null;}}
},{passive:false});

function btnGuard(){return scrolling||Date.now()-scrollEndTime<SCROLL_GUARD_MS;}
let btnLPressed=false,btnLLastX=0,btnLLastY=0;
btnL.addEventListener('touchstart',e=>{
  e.preventDefault();e.stopPropagation();
  if(btnGuard())return;
  btnLPressed=true;
  btnLLastX=e.touches[0].clientX;btnLLastY=e.touches[0].clientY;
  btnL.classList.add('pressed');
  send({t:'mousedown'});
  if(navigator.vibrate)navigator.vibrate(30);
});
btnL.addEventListener('touchmove',e=>{
  e.preventDefault();
  if(!btnLPressed)return;
  const dx=(e.touches[0].clientX-btnLLastX)*SENSITIVITY;
  const dy=(e.touches[0].clientY-btnLLastY)*SENSITIVITY;
  btnLLastX=e.touches[0].clientX;btnLLastY=e.touches[0].clientY;
  if(Math.abs(dx)>0.5||Math.abs(dy)>0.5) send({t:'move',dx,dy});
});
btnL.addEventListener('touchend',e=>{
  e.preventDefault();
  if(btnLPressed){btnLPressed=false;btnL.classList.remove('pressed');send({t:'mouseup'});}
});
btnL.addEventListener('touchcancel',e=>{
  if(btnLPressed){btnLPressed=false;btnL.classList.remove('pressed');send({t:'mouseup'});}
});
let btnRPressed=false,btnRLastX=0,btnRLastY=0;
btnR.addEventListener('touchstart',e=>{
  e.preventDefault();e.stopPropagation();
  if(btnGuard())return;
  btnRPressed=true;
  btnRLastX=e.touches[0].clientX;btnRLastY=e.touches[0].clientY;
  btnR.classList.add('pressed');
  send({t:'rmousedown'});
  if(navigator.vibrate)navigator.vibrate(30);
});
btnR.addEventListener('touchmove',e=>{
  e.preventDefault();
  if(!btnRPressed)return;
  const dx=(e.touches[0].clientX-btnRLastX)*SENSITIVITY;
  const dy=(e.touches[0].clientY-btnRLastY)*SENSITIVITY;
  btnRLastX=e.touches[0].clientX;btnRLastY=e.touches[0].clientY;
  if(Math.abs(dx)>0.5||Math.abs(dy)>0.5) send({t:'move',dx,dy});
});
btnR.addEventListener('touchend',e=>{
  e.preventDefault();
  if(btnRPressed){btnRPressed=false;btnR.classList.remove('pressed');send({t:'rmouseup'});}
});
btnR.addEventListener('touchcancel',e=>{
  if(btnRPressed){btnRPressed=false;btnR.classList.remove('pressed');send({t:'rmouseup'});}
});
btnL.addEventListener('click',()=>send({t:'mousedown'}));
btnR.addEventListener('click',()=>send({t:'rmousedown'}));
</script>
</body>
</html>"""


# ── 验证码输入页面 ────────────────────────────────────────────

TOKEN_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>验证码</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a1a;color:#eee;font-family:system-ui;display:flex;
  align-items:center;justify-content:center;height:100vh;height:100dvh}
.card{background:#2a2a2a;border-radius:16px;padding:36px 28px;text-align:center;
  width:320px;box-shadow:0 8px 30px rgba(0,0,0,.4)}
h2{font-size:1.2em;margin-bottom:6px}
p{font-size:.85em;color:#888;margin-bottom:20px}
.digits{display:flex;gap:8px;justify-content:center}
.digits input{width:40px;height:50px;font-size:1.5em;text-align:center;
  border:2px solid #444;border-radius:10px;background:#1a1a1a;color:#eee;
  outline:none;transition:border-color .2s;caret-color:transparent}
.digits input:focus{border-color:#fff}
.digits input.err{border-color:#f44336;animation:shake .3s}
.digits input.filled{border-color:#fff}
@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-6px)}75%{transform:translateX(6px)}}
.tip{font-size:.75em;color:#f44336;margin-top:10px;min-height:1.2em}
</style>
</head>
<body>
<div class="card">
  <h2>🔒 请输入验证码</h2>
  <p>请查看AnyTouch上显示的六位验证码</p>
  <div class="digits" id="digits"></div>
  <div class="tip" id="tip"></div>
</div>
<script>
const box=document.getElementById('digits'),tip=document.getElementById('tip');
const inputs=[];
for(let i=0;i<6;i++){
  const inp=document.createElement('input');
  inp.type='tel';inp.maxLength=1;inp.inputMode='numeric';inp.autocomplete='off';
  box.appendChild(inp);inputs.push(inp);
}
inputs[0].focus();

function getCode(){return inputs.map(i=>i.value).join('');}
function submit(){
  const code=getCode();
  if(code.length===6) location.href='/?token='+code;
}
function clearErr(){inputs.forEach(i=>i.classList.remove('err'));tip.textContent='';}

inputs.forEach((inp,idx)=>{
  inp.addEventListener('input',()=>{
    clearErr();
    inp.value=inp.value.replace(/\\D/g,'').slice(-1);
    if(inp.value&&idx<5) inputs[idx+1].focus();
    if(inp.value) inp.classList.add('filled'); else inp.classList.remove('filled');
    submit();
  });
  inp.addEventListener('keydown',e=>{
    if(e.key==='Backspace'&&!inp.value&&idx>0){
      inputs[idx-1].focus();inputs[idx-1].value='';
      inputs[idx-1].classList.remove('filled');
    }
  });
  inp.addEventListener('paste',e=>{
    e.preventDefault();
    const text=(e.clipboardData.getData('text')||'').replace(/\\D/g,'').slice(0,6);
    for(let j=0;j<6;j++){
      inputs[j].value=text[j]||'';
      if(text[j]) inputs[j].classList.add('filled'); else inputs[j].classList.remove('filled');
    }
    if(text.length>0) inputs[Math.min(text.length,5)].focus();
    submit();
  });
});

if(location.search.includes('token=')){
  inputs.forEach(i=>i.classList.add('err'));
  tip.textContent='验证码错误，请重新输入';
  inputs[0].focus();
}
const locked={{LOCKED}};
if(locked>0){
  inputs.forEach(i=>{i.disabled=true;i.classList.add('err');});
  let rem=locked;
  function tick(){
    const m=Math.floor(rem/60),s=rem%60;
    tip.textContent='错误次数过多，请等待 '+m+'分'+s+'秒';
    if(rem<=0){
      inputs.forEach(i=>{i.disabled=false;i.classList.remove('err');i.value='';});
      tip.textContent='';inputs[0].focus();return;
    }
    rem--;setTimeout(tick,1000);
  }
  tick();
}
</script>
</body>
</html>"""

# ── HTTP 服务 (仅提供页面) ────────────────────────────────────

import time as _time

# 按 IP 记录验证码错误次数: {ip: [fail_count, lock_until_timestamp]}
_token_fails = {}
_TOKEN_MAX_FAILS = 3
_TOKEN_LOCK_SECONDS = 600  # 10 分钟

class Handler(BaseHTTPRequestHandler):
    ws_port = 8867
    token = None  # 设置后，访问页面需要 ?token=xxx

    def log_message(self, fmt, *args):
        pass

    def _get_client_ip(self):
        return self.client_address[0]

    def do_GET(self):
        if self.path == "/ping":
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # token 校验
        if self.token:
            from urllib.parse import urlparse, parse_qs
            client_ip = self._get_client_ip()
            rec = _token_fails.get(client_ip, [0, 0])

            # 检查是否被锁定
            if rec[0] >= _TOKEN_MAX_FAILS and _time.time() < rec[1]:
                remain = int(rec[1] - _time.time())
                page = TOKEN_PAGE.replace('{{LOCKED}}', str(remain))
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(page.encode())
                return

            # 锁定已过期，重置
            if rec[0] >= _TOKEN_MAX_FAILS and _time.time() >= rec[1]:
                rec = [0, 0]
                _token_fails[client_ip] = rec

            qs = parse_qs(urlparse(self.path).query)
            provided = qs.get("token", [None])[0]

            if provided is None:
                # 首次访问，无 token，显示输入页
                page = TOKEN_PAGE.replace('{{LOCKED}}', '0')
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(page.encode())
                return

            if provided != self.token:
                # 验证码错误
                rec[0] += 1
                if rec[0] >= _TOKEN_MAX_FAILS:
                    rec[1] = _time.time() + _TOKEN_LOCK_SECONDS
                _token_fails[client_ip] = rec

                if rec[0] >= _TOKEN_MAX_FAILS:
                    remain = int(rec[1] - _time.time())
                    page = TOKEN_PAGE.replace('{{LOCKED}}', str(remain))
                else:
                    page = TOKEN_PAGE.replace('{{LOCKED}}', '0')

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(page.encode())
                return

            # 验证成功，清除错误记录
            _token_fails.pop(client_ip, None)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        page = HTML_PAGE.replace('{{HOSTNAME}}', platform.node())
        page = page.replace('{{WS_PORT}}', str(self.ws_port))
        self.wfile.write(page.encode())


# ── WebSocket 服务 ────────────────────────────────────────────

active_ws = None
ws_token = None  # WebSocket 连接也需要校验的 token

# GUI 回调：连接/断开时通知界面
on_device_connect = None    # callback(device_name)
on_device_disconnect = None # callback()


def _parse_device(ua):
    """从 User-Agent 提取设备名称"""
    # iPhone
    m = re.search(r'(iPhone)', ua)
    if m:
        return m.group(1)
    # iPad
    m = re.search(r'(iPad)', ua)
    if m:
        return m.group(1)
    # Android 设备型号: "Build/xxx" 前面的部分
    m = re.search(r';\s*([^;)]+?)\s*Build/', ua)
    if m:
        return m.group(1).strip()
    # Android 通用
    if 'Android' in ua:
        return 'Android'
    # 桌面浏览器
    for name in ['Chrome', 'Firefox', 'Safari', 'Edge']:
        if name in ua:
            return f'浏览器 ({name})'
    return None


async def ws_handler(websocket):
    global active_ws
    # token 校验
    if ws_token:
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(websocket.request.path).query)
        if qs.get("token", [None])[0] != ws_token:
            await websocket.close(4003, "无效的访问令牌")
            return
    if active_ws is not None:
        try:
            pong = await active_ws.ping()
            await asyncio.wait_for(pong, timeout=1)
        except Exception:
            active_ws = None
    if active_ws is not None:
        await websocket.send(json.dumps({"t": "rejected", "msg": "请先断开已连接设备！"}))
        await websocket.close()
        return
    active_ws = websocket
    client_ip = websocket.remote_address[0] if websocket.remote_address else "未知"
    device_name = client_ip
    connect_time = datetime.now()
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("t") == "hello":
                    ua = data.get("ua", "")
                    device_name = _parse_device(ua) or client_ip
                    print(f"[连接] {device_name} ({client_ip}) 已连接 - {connect_time.strftime('%H:%M:%S')}")
                    if on_device_connect:
                        on_device_connect(device_name)
                    await websocket.send(json.dumps({"t": "accepted"}))
                    continue
                handle_msg(data)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        if active_ws is websocket:
            active_ws = None
            duration = datetime.now() - connect_time
            mins, secs = divmod(int(duration.total_seconds()), 60)
            hours, mins = divmod(mins, 60)
            dur_str = f"{hours}h{mins}m{secs}s" if hours else f"{mins}m{secs}s"
            print(f"[断开] {device_name} ({client_ip}) 已断开 - 连接时长 {dur_str}")
            if on_device_disconnect:
                on_device_disconnect()


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
