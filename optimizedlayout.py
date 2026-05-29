"""
CONTROL DECK — Low-latency WebSocket edition
Replaces per-keypress HTTP fetch with a single persistent WebSocket.
REQUIRES:
pip install pyautogui websockets pyperclip
"""
import asyncio
import http.server
import json
import socket
import socketserver
import threading
import time

import pyautogui
import pyperclip
import websockets

# ==========================================
# CONFIG
# ==========================================

pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0

PORT_HTTP = 8080
PORT_WS   = 8081

MODIFIER_STATE = {"ctrl": False, "alt": False, "shift": False}
mod_lock = threading.Lock()

# ==========================================
# COMMAND HANDLER  (runs in WS thread)
# ==========================================

def handle_command(ctype, cval):
    """Execute a command synchronously in the WS event thread."""
    try:
        if ctype == "KEY":
            with mod_lock:
                active = [k for k, v in MODIFIER_STATE.items() if v]
            if active:
                pyautogui.hotkey(*active, cval)
            else:
                pyautogui.press(cval)

        elif ctype == "TEXT":
            # Paste via clipboard — instant regardless of length
            pyperclip.copy(cval)
            pyautogui.hotkey("ctrl", "v")

        elif ctype == "MOD":
            with mod_lock:
                if not MODIFIER_STATE[cval]:
                    pyautogui.keyDown(cval)
                    MODIFIER_STATE[cval] = True
                else:
                    pyautogui.keyUp(cval)
                    MODIFIER_STATE[cval] = False

        elif ctype == "HOTKEY":
            if cval == "alt_tab":
                pyautogui.hotkey("alt", "tab")
            elif cval == "alt_hold":
                pyautogui.keyDown("alt")
                with mod_lock:
                    MODIFIER_STATE["alt"] = True
            elif cval == "alt_release":
                pyautogui.keyUp("alt")
                with mod_lock:
                    MODIFIER_STATE["alt"] = False
            elif cval == "release_all":
                for k in ("ctrl", "alt", "shift"):
                    pyautogui.keyUp(k)
                with mod_lock:
                    MODIFIER_STATE.update(ctrl=False, alt=False, shift=False)

        elif ctype == "MOUSE":
            if cval == "click_left":
                pyautogui.click(button="left")
            elif cval == "click_right":
                pyautogui.click(button="right")
            elif cval == "scroll_up":
                pyautogui.scroll(3)
            elif cval == "scroll_down":
                pyautogui.scroll(-3)

        elif ctype == "TRACKPAD":
            pyautogui.moveRel(cval.get("dx", 0), cval.get("dy", 0), duration=0)

    except Exception as e:
        print("CMD ERROR:", e)


# ==========================================
# WEBSOCKET SERVER
# ==========================================

connected_clients = set()

async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        async for raw in websocket:
            try:
                msg   = json.loads(raw)
                ctype = msg.get("type")
                cval  = msg.get("value")
                # Run blocking pyautogui call in thread pool so WS loop stays free
                await asyncio.get_event_loop().run_in_executor(
                    None, handle_command, ctype, cval
                )
                # Send modifier state back
                with mod_lock:
                    state = dict(MODIFIER_STATE)
                await websocket.send(json.dumps(state))
            except Exception as e:
                print("WS MSG ERROR:", e)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)


def start_ws():
    async def main():
        async with websockets.serve(ws_handler, "0.0.0.0", PORT_WS, ping_interval=20):
            print(f"WebSocket ready on :{PORT_WS}")
            await asyncio.Future()
    asyncio.run(main())


# ==========================================
# HTML  (injected with WS port)
# ==========================================

def build_html():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width,initial-scale=1,maximum-scale=1,
               user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#080808">
<title>CONTROL DECK</title>
<style>
:root{{
  --bg:#080808;--key:#181818;--key-border:#2a2a2a;
  --text:#e8e8e8;--dim:#555;--accent:#00e5a0;
  --shortcut-bg:#0d1525;--shortcut-border:#1a2a4a;--shortcut-text:#60a5fa;
  --mouse-bg:#1b1026;--mouse-border:#3c1e54;--mouse-text:#d946ef;
  --punct-bg:#1a1a0a;--punct-border:#3a3a1a;--punct-text:#e5c007;
}}
*{{box-sizing:border-box;margin:0;padding:0;
   -webkit-tap-highlight-color:transparent;}}
html{{width:100%;height:100%;overflow:hidden;
     overscroll-behavior:none;touch-action:manipulation;}}
body{{width:100vw;height:100dvh;overflow:hidden;background:var(--bg);
     color:var(--text);font-family:Consolas,monospace;
     display:flex;flex-direction:column;user-select:none;
     position:fixed;inset:0;}}
/* TAB BAR */
.tabbar{{display:flex;height:46px;flex-shrink:0;
         background:#0a0a0a;border-bottom:1px solid #1e1e1e;
         position:relative;}}
.tab{{flex:1;border:none;background:none;color:var(--dim);
      font:700 11px Consolas,monospace;letter-spacing:.5px;
      position:relative;cursor:pointer;}}
.tab.active{{color:var(--accent);}}
.tab.active::after{{content:'';position:absolute;left:0;right:0;
                    bottom:0;height:3px;background:var(--accent);}}
.fs-btn{{position:absolute;left:6px;top:50%;transform:translateY(-50%);
         background:none;border:1px solid #333;color:#ccc;font-size:16px;
         width:32px;height:32px;border-radius:4px;cursor:pointer;
         display:flex;align-items:center;justify-content:center;z-index:10;}}
/* STATUS DOT */
#ws-dot{{position:absolute;right:8px;top:50%;transform:translateY(-50%);
         width:8px;height:8px;border-radius:50%;background:#555;
         transition:background .3s;z-index:10;}}
#ws-dot.ok{{background:#00e5a0;}}
#ws-dot.err{{background:#f43f5e;}}
/* PANELS */
.panels{{flex:1;width:100%;overflow:hidden;position:relative;}}
.panel{{display:none;width:100%;height:100%;padding:6px;
        flex-direction:column;gap:6px;}}
.panel.active{{display:flex;}}
.row{{display:flex;gap:6px;width:100%;flex:1;min-height:0;}}
/* KEYS */
.key{{flex:1;border:1px solid var(--key-border);border-radius:6px;
      background:var(--key);color:var(--text);
      font:700 16px Consolas,monospace;
      display:flex;flex-direction:column;align-items:center;
      justify-content:center;text-align:center;cursor:pointer;
      position:relative;overflow:hidden;min-height:0;}}
.key::after{{content:'';position:absolute;inset:0;background:white;
             opacity:0;transition:opacity .08s;pointer-events:none;}}
.key.active-flash::after{{opacity:.15;}}
.key.locked{{background:#b45309!important;
             border-color:#f59e0b!important;color:white!important;}}
.key.k-shortcut{{background:var(--shortcut-bg);
                 border-color:var(--shortcut-border);
                 color:var(--shortcut-text);}}
.key.k-mouse{{background:var(--mouse-bg);
              border-color:var(--mouse-border);
              color:var(--mouse-text);}}
.key.k-punct{{background:var(--punct-bg);
              border-color:var(--punct-border);
              color:var(--punct-text);font-size:20px;}}
.sub{{font-size:9px;color:var(--dim);margin-top:2px;}}
.s2{{flex:2!important;}}
/* TEXT PANEL */
.text-input-area{{flex:1;width:100%;background:#111;
                  border:2px solid #2a2a2a;border-radius:8px;
                  padding:12px;color:var(--text);
                  font:700 14px Consolas,monospace;
                  resize:none;outline:none;margin-bottom:6px;}}
.text-input-area:focus{{border-color:var(--accent);}}
.send-text-btn{{width:100%;height:48px;border:none;border-radius:6px;
                background:var(--accent);color:#000;
                font:700 16px Consolas,monospace;cursor:pointer;
                flex-shrink:0;}}
.send-text-btn:active{{opacity:.8;}}
.char-counter{{text-align:center;color:var(--dim);font-size:11px;
               margin-top:4px;flex-shrink:0;}}
/* TRACKPAD */
.trackpad{{flex:1;width:100%;background:#120b18;
           border:2px dashed var(--mouse-border);border-radius:8px;
           display:flex;align-items:center;justify-content:center;
           text-align:center;color:#a21caf;font-size:12px;font-weight:bold;}}
@media(max-height:450px){{
  .tabbar{{height:36px;}} .tab{{font-size:10px;}}
  .panel{{gap:4px;padding:4px;}} .row{{gap:4px;}}
  .key{{font-size:13px;border-radius:5px;}}
  .key.k-punct{{font-size:16px;}} .sub{{display:none;}}
  .text-input-area{{font-size:12px;padding:8px;}}
  .send-text-btn{{height:40px;font-size:14px;}}
}}
</style>
</head>
<body>

<div class="tabbar">
  <button class="fs-btn" onclick="toggleFullscreen()">⛶</button>
  <button class="tab active" onclick="switchTab(this,'alpha')">A-Z</button>
  <button class="tab" onclick="switchTab(this,'numbers')">123</button>
  <button class="tab" onclick="switchTab(this,'punctuation')">,.</button>
  <button class="tab" onclick="switchTab(this,'shortcuts')">SHORTCUTS</button>
  <button class="tab" onclick="switchTab(this,'mouse')">MOUSE</button>
  <button class="tab" onclick="switchTab(this,'keyboard')">⌨</button>
  <div id="ws-dot" title="WebSocket status"></div>
</div>

<div class="panels">

<!-- ALPHABET -->
<div id="alpha" class="panel active">
  <div id="alphakeys" style="display:flex;flex-direction:column;gap:inherit;flex:1;min-height:0;"></div>
  <div class="row" style="flex:0 0 auto;height:48px;">
    <div class="key" data-key="backspace">⌫</div>
    <div class="key s2" data-key="space">SPACE</div>
    <div class="key" data-key="enter">↵</div>
  </div>
</div>

<!-- NUMBERS -->
<div id="numbers" class="panel">
  <div class="row">
    <div class="key" data-key="1">1</div>
    <div class="key" data-key="2">2</div>
    <div class="key" data-key="3">3</div>
  </div>
  <div class="row">
    <div class="key" data-key="4">4</div>
    <div class="key" data-key="5">5</div>
    <div class="key" data-key="6">6</div>
  </div>
  <div class="row">
    <div class="key" data-key="7">7</div>
    <div class="key" data-key="8">8</div>
    <div class="key" data-key="9">9</div>
  </div>
  <div class="row" style="flex:0 0 auto;height:48px;">
    <div class="key" data-key="backspace">⌫</div>
    <div class="key" data-key="0">0</div>
    <div class="key s2" data-key="space">SPACE</div>
  </div>
</div>

<!-- PUNCTUATION -->
<div id="punctuation" class="panel">
  <div class="row">
    <div class="key k-punct" data-key=".">.</div>
    <div class="key k-punct" data-key=",">,</div>
    <div class="key k-punct" data-key="!">!</div>
    <div class="key k-punct" data-key="?">?</div>
  </div>
  <div class="row">
    <div class="key k-punct" data-key=":">:</div>
    <div class="key k-punct" data-key=";">;</div>
    <div class="key k-punct" data-key="'">'</div>
    <div class="key k-punct" data-key='"'>"</div>
  </div>
  <div class="row">
    <div class="key k-punct" data-key="(">(</div>
    <div class="key k-punct" data-key=")">)</div>
    <div class="key k-punct" data-key="[">[</div>
    <div class="key k-punct" data-key="]">]</div>
  </div>
  <div class="row">
    <div class="key k-punct" data-key="@">@</div>
    <div class="key k-punct" data-key="#">#</div>
    <div class="key k-punct" data-key="$">$</div>
    <div class="key k-punct" data-key="%">%</div>
  </div>
  <div class="row">
    <div class="key k-punct" data-key="&">&amp;</div>
    <div class="key k-punct" data-key="*">*</div>
    <div class="key k-punct" data-key="-">-</div>
    <div class="key k-punct" data-key="_">_</div>
  </div>
  <div class="row">
    <div class="key k-punct" data-key="=">=</div>
    <div class="key k-punct" data-key="+">+</div>
    <div class="key k-punct" data-key="/">/</div>
    <div class="key k-punct" data-key="\\">\\</div>
  </div>
  <div class="row">
    <div class="key k-punct" data-key="<">&lt;</div>
    <div class="key k-punct" data-key=">">&gt;</div>
    <div class="key k-punct" data-key="|">|</div>
    <div class="key k-punct" data-key="~">~</div>
  </div>
  <div class="row" style="flex:0 0 auto;height:48px;">
    <div class="key" data-key="backspace">⌫</div>
    <div class="key s2" data-key="space">SPACE</div>
    <div class="key" data-key="enter">↵</div>
  </div>
</div>

<!-- SHORTCUTS -->
<div id="shortcuts" class="panel">
  <div class="row">
    <div class="key k-shortcut" data-mod="ctrl" id="btn-ctrl">CTRL</div>
    <div class="key k-shortcut" data-mod="alt"  id="btn-alt">ALT</div>
    <div class="key k-shortcut" data-mod="shift" id="btn-shift">SHIFT</div>
  </div>
  <div class="row">
    <div class="key k-shortcut" data-hotkey="alt_tab">ALT TAB</div>
    <div class="key k-shortcut" data-key="tab">TAB</div>
  </div>
  <div class="row">
    <div class="key k-shortcut" data-hotkey="alt_hold">ALT HOLD</div>
    <div class="key k-shortcut" data-hotkey="alt_release">ALT RELEASE</div>
  </div>
  <div class="row">
    <div class="key k-shortcut" data-key="c">COPY</div>
    <div class="key k-shortcut" data-key="v">PASTE</div>
    <div class="key k-shortcut" data-key="x">CUT</div>
  </div>
  <div class="row">
    <div class="key k-shortcut" data-key="a">ALL</div>
    <div class="key k-shortcut" data-key="z">UNDO</div>
    <div class="key k-shortcut" data-key="y">REDO</div>
  </div>
  <div class="row">
    <div class="key k-shortcut" data-key="esc">ESC</div>
    <div class="key k-shortcut" data-key="enter">ENTER</div>
    <div class="key k-shortcut" data-key="s">SAVE</div>
  </div>
  <div class="row" style="flex:0 0 auto;height:48px;">
    <div class="key k-shortcut s2" data-hotkey="release_all">RELEASE ALL</div>
    <div class="key" data-key="backspace">⌫</div>
  </div>
</div>

<!-- MOUSE -->
<div id="mouse" class="panel">
  <div class="row" style="flex:0 0 auto;height:48px;">
    <div class="key k-mouse" data-mouse="click_left">L</div>
    <div class="key k-mouse" data-mouse="scroll_up">▲</div>
    <div class="key k-mouse" data-mouse="scroll_down">▼</div>
    <div class="key k-mouse" data-mouse="click_right">R</div>
  </div>
  <div id="pad" class="trackpad">DRAG TO MOVE MOUSE</div>
  <div class="row" style="flex:0 0 auto;height:48px;">
    <div class="key" data-key="space">SPACE</div>
    <div class="key" data-key="backspace">⌫</div>
  </div>
</div>

<!-- KEYBOARD INPUT -->
<div id="keyboard" class="panel">
  <textarea id="textInput" class="text-input-area"
    placeholder="Type here using your device keyboard...&#10;&#10;Press SEND to type it on your PC"
    autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
  </textarea>
  <button class="send-text-btn" onclick="sendText()">SEND TEXT TO PC</button>
  <div class="char-counter" id="charCount">0 characters</div>
  <div class="row" style="flex:0 0 auto;height:48px;margin-top:6px;">
    <div class="key" data-key="enter">↵ ENTER</div>
    <div class="key" data-key="tab">TAB</div>
    <div class="key" data-key="backspace">⌫ BKSP</div>
  </div>
</div>

</div><!-- /panels -->

<script>
/* ==========================================
   WEBSOCKET  — single persistent connection
   All commands go through this; no HTTP per keypress.
========================================== */
const WS_PORT = {PORT_WS};
const dot = document.getElementById('ws-dot');
let ws;
let wsReady = false;
const pendingQueue = [];   // buffer while reconnecting

function wsConnect() {{
  ws = new WebSocket(`ws://${{location.hostname}}:${{WS_PORT}}`);

  ws.onopen = () => {{
    wsReady = true;
    dot.className = 'ok';
    // drain any queued messages
    while (pendingQueue.length) {{
      ws.send(pendingQueue.shift());
    }}
  }};

  ws.onclose = () => {{
    wsReady = false;
    dot.className = 'err';
    setTimeout(wsConnect, 1500);   // auto-reconnect
  }};

  ws.onerror = () => {{
    dot.className = 'err';
  }};

  ws.onmessage = (e) => {{
    try {{
      updateModifierVisuals(JSON.parse(e.data));
    }} catch(_) {{}}
  }};
}}

wsConnect();

function send(type, value) {{
  const msg = JSON.stringify({{ type, value }});
  if (wsReady) {{
    ws.send(msg);
  }} else {{
    pendingQueue.push(msg);
  }}
}}

/* ==========================================
   FULLSCREEN
========================================== */
function toggleFullscreen() {{
  if (!document.fullscreenElement)
    document.documentElement.requestFullscreen().catch(()=>{{}});
  else
    document.exitFullscreen();
}}
document.body.addEventListener('touchstart', () => {{
  if (!document.fullscreenElement)
    document.documentElement.requestFullscreen().catch(()=>{{}});
}}, {{ once: true }});

/* ==========================================
   TEXT INPUT
========================================== */
const textInput = document.getElementById('textInput');
const charCount = document.getElementById('charCount');
textInput.addEventListener('input', () => {{
  charCount.textContent = textInput.value.length + ' characters';
}});

function sendText() {{
  const text = textInput.value.trim();
  if (!text) return;
  send('TEXT', text);
  const btn = document.querySelector('.send-text-btn');
  btn.style.opacity = '0.6';
  setTimeout(() => {{ btn.style.opacity = '1'; }}, 150);
  textInput.value = '';
  charCount.textContent = '0 characters';
}}

textInput.addEventListener('keydown', (e) => {{
  if (e.key === 'Enter' && !e.shiftKey) {{
    e.preventDefault();
    sendText();
  }}
}});

/* ==========================================
   MODIFIER VISUALS
========================================== */
function updateModifierVisuals(state) {{
  if (!state) return;
  document.getElementById('btn-ctrl').classList.toggle('locked', state.ctrl);
  document.getElementById('btn-alt').classList.toggle('locked', state.alt);
  document.getElementById('btn-shift').classList.toggle('locked', state.shift);
}}

/* ==========================================
   TABS
========================================== */
function switchTab(btn, id) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
  if (id === 'keyboard')
    setTimeout(() => document.getElementById('textInput').focus(), 100);
}}

/* ==========================================
   FLASH
========================================== */
function flash(el) {{
  el.classList.add('active-flash');
  setTimeout(() => el.classList.remove('active-flash'), 120);
}}

/* ==========================================
   HOLD REPEAT
========================================== */
function holdRepeat(el, fn, initialDelay=250, repeatDelay=60) {{
  let timeoutIv, intervalIv;
  const start = () => {{
    fn();
    timeoutIv = setTimeout(() => {{
      intervalIv = setInterval(fn, repeatDelay);
    }}, initialDelay);
  }};
  const stop = () => {{
    clearTimeout(timeoutIv);
    clearInterval(intervalIv);
  }};
  el.addEventListener('touchstart', e => {{ e.preventDefault(); start(); }},
                      {{ passive: false }});
  el.addEventListener('touchend',   stop);
  el.addEventListener('touchcancel',stop);
  el.addEventListener('mousedown',  e => {{ e.preventDefault(); start(); }});
  el.addEventListener('mouseup',    stop);
  el.addEventListener('mouseleave', stop);
}}

/* ==========================================
   BUILD ALPHABET
========================================== */
(function buildAlpha() {{
  const rows = ['qwertyuiop','asdfghjkl','zxcvbnm'];
  const container = document.getElementById('alphakeys');
  rows.forEach(row => {{
    const div = document.createElement('div');
    div.className = 'row';
    row.split('').forEach(ch => {{
      const b = document.createElement('div');
      b.className = 'key';
      b.textContent = ch.toUpperCase();
      holdRepeat(b, () => {{ send('KEY', ch); flash(b); }});
      div.appendChild(b);
    }});
    container.appendChild(div);
  }});
}})();

/* ==========================================
   NORMAL KEYS
========================================== */
document.querySelectorAll('[data-key]').forEach(el => {{
  holdRepeat(el, () => {{ send('KEY', el.dataset.key); flash(el); }});
}});

/* ==========================================
   MODIFIERS
========================================== */
document.querySelectorAll('[data-mod]').forEach(el => {{
  el.addEventListener('click', () => {{
    send('MOD', el.dataset.mod);
    flash(el);
  }});
}});

/* ==========================================
   HOTKEYS
========================================== */
document.querySelectorAll('[data-hotkey]').forEach(el => {{
  holdRepeat(el, () => {{ send('HOTKEY', el.dataset.hotkey); flash(el); }},
             300, 180);
}});

/* ==========================================
   MOUSE BUTTONS
========================================== */
document.querySelectorAll('[data-mouse]').forEach(el => {{
  const isScroll = el.dataset.mouse.includes('scroll');
  holdRepeat(el, () => {{ send('MOUSE', el.dataset.mouse); flash(el); }},
             200, isScroll ? 40 : 150);
}});

/* ==========================================
   TRACKPAD
   Batches rapid moves — sends at most once per animation frame.
   This cuts WS message rate ~4-5x without any feel change.
========================================== */
const pad = document.getElementById('pad');
let lastX = 0, lastY = 0;
let pendingDx = 0, pendingDy = 0;
let rafPending = false;

function flushTrackpad() {{
  if (pendingDx !== 0 || pendingDy !== 0) {{
    send('TRACKPAD', {{ dx: pendingDx, dy: pendingDy }});
    pendingDx = 0;
    pendingDy = 0;
  }}
  rafPending = false;
}}

pad.addEventListener('touchstart', e => {{
  if (e.touches.length === 1) {{
    lastX = e.touches[0].clientX;
    lastY = e.touches[0].clientY;
  }}
}}, {{ passive: true }});

pad.addEventListener('touchmove', e => {{
  if (e.touches.length === 1) {{
    const curX = e.touches[0].clientX;
    const curY = e.touches[0].clientY;
    pendingDx += Math.round((curX - lastX) * 2.2);
    pendingDy += Math.round((curY - lastY) * 2.2);
    lastX = curX;
    lastY = curY;
    if (!rafPending) {{
      rafPending = true;
      requestAnimationFrame(flushTrackpad);
    }}
  }}
}}, {{ passive: true }});
</script>
</body>
</html>"""


# ==========================================
# HTTP SERVER  (serves the page only)
# ==========================================

class Handler(http.server.BaseHTTPRequestHandler):
    _html = None

    def do_GET(self):
        if self.path == "/":
            if Handler._html is None:
                Handler._html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(Handler._html)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads    = True
    allow_reuse_address = True


# ==========================================
# HELPERS
# ==========================================

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "YOUR_PC_IP"


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    threading.Thread(target=start_ws, daemon=True).start()
    time.sleep(0.4)

    server = ThreadedHTTPServer(("0.0.0.0", PORT_HTTP), Handler)
    ip = get_local_ip()

    print("\n╔══════════════════════════════════╗")
    print("║        CONTROL DECK (WS)         ║")
    print("╚══════════════════════════════════╝\n")
    print(f"OPEN ON PHONE:  http://{ip}:{PORT_HTTP}\n")
    print("FEATURES:")
    print(" • WebSocket — zero per-keypress HTTP overhead")
    print(" • Clipboard paste for instant text sending")
    print(" • Trackpad RAF-batching (4-5x fewer messages)")
    print(" • Auto-reconnect on drop")
    print(" • WS status dot (green = connected)\n")
    server.serve_forever()
