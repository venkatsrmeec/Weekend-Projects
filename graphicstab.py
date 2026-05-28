"""
GRAPHICS TABLET with LIVE SCREEN MIRROR + ACCURATE ZOOM/PAN MAPPING
Samsung A7 2016 / any modern browser. Offline hotspot use.

REQUIRES:
pip install pyautogui websockets mss Pillow
"""

import http.server
import socketserver
import socket
import json
import threading
import queue
import time
import asyncio
import io

import pyautogui
import websockets
import mss
from PIL import Image

# =========================================================
# CONFIG
# =========================================================

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

PORT_HTTP = 9090
PORT_WS = 8765

JPEG_QUALITY = 40
CAPTURE_INTERVAL = 0.05

TOUCH_QUEUE = queue.Queue()

SCREEN_W, SCREEN_H = pyautogui.size()

# =========================================================
# STREAM BUFFER
# =========================================================

class StreamBuffer:
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()
        self.new_frame = False

    def set_frame(self, jpeg_bytes):
        with self.condition:
            self.frame = jpeg_bytes
            self.new_frame = True
            self.condition.notify_all()

    def get_frame(self):
        with self.condition:
            while not self.new_frame:
                self.condition.wait()

            self.new_frame = False
            return self.frame


stream_buffer = StreamBuffer()

# =========================================================
# SCREEN CAPTURE
# =========================================================

def screen_capture():

    with mss.mss() as sct:

        monitor = sct.monitors[1]

        while True:

            start = time.time()

            img = sct.grab(monitor)

            pil_img = Image.frombytes(
                "RGB",
                img.size,
                img.bgra,
                "raw",
                "BGRX"
            )

            buf = io.BytesIO()

            pil_img.save(
                buf,
                format="JPEG",
                quality=JPEG_QUALITY
            )

            stream_buffer.set_frame(buf.getvalue())

            elapsed = time.time() - start

            time.sleep(max(0, CAPTURE_INTERVAL - elapsed))


# =========================================================
# HTML PAGE
# =========================================================

HTML_CONTENT = f"""
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width,
initial-scale=1.0,
maximum-scale=1.0,
user-scalable=no,
viewport-fit=cover">

<title>Graphics Tablet Mirror</title>

<style>

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;

    -webkit-tap-highlight-color: transparent;
    user-select: none;
}}

html, body {{
    width: 100%;
    height: 100%;
    overflow: hidden;

    background: #000;
    touch-action: none;
}}

#viewport {{
    position: fixed;
    inset: 0;

    overflow: hidden;
    background: #000;
}}

#screen-img {{
    position: absolute;
    left: 0;
    top: 0;

    width: 100vw;
    height: auto;

    transform-origin: top left;

    pointer-events: none;
}}

#indicator {{
    position: fixed;

    width: 16px;
    height: 16px;

    border-radius: 50%;

    background: rgba(0,255,200,0.7);

    transform: translate(-50%, -50%);

    pointer-events: none;

    display: none;

    z-index: 9999;
}}

#info {{
    position: fixed;

    top: 8px;
    left: 8px;

    background: rgba(0,0,0,0.65);

    color: #0f0;

    font: 12px monospace;

    padding: 5px 8px;

    border-radius: 5px;

    z-index: 99999;
}}

#fs {{
    position: fixed;

    top: 8px;
    right: 8px;

    width: 42px;
    height: 42px;

    border-radius: 8px;

    border: 1px solid #666;

    background: rgba(0,0,0,0.55);

    color: white;

    font-size: 22px;

    display: flex;
    align-items: center;
    justify-content: center;

    z-index: 99999;
}}

</style>

</head>

<body>

<div id="info">1.00x</div>
<div id="fs">⛶</div>

<div id="viewport">
    <img id="screen-img" src="/stream">
</div>

<div id="indicator"></div>

<script>

const SCREEN_W = {SCREEN_W};
const SCREEN_H = {SCREEN_H};

const viewport = document.getElementById("viewport");
const img = document.getElementById("screen-img");
const indicator = document.getElementById("indicator");
const info = document.getElementById("info");

const ws =
new WebSocket(`ws://${{location.hostname}}:{PORT_WS}`);

function send(action, x, y) {{

    if(ws.readyState !== 1) return;

    ws.send(JSON.stringify({{
        type: "touch",
        action,
        x,
        y
    }}));
}}

document.getElementById("fs").onclick = () => {{

    if(!document.fullscreenElement) {{
        document.documentElement
            .requestFullscreen()
            .catch(()=>{{}});
    }}
    else {{
        document.exitFullscreen();
    }}
}};

document.addEventListener("touchstart", () => {{

    if(!document.fullscreenElement) {{

        document.documentElement
            .requestFullscreen()
            .catch(()=>{{}});
    }}

}}, {{once:true}});


// =====================================================
// VIEW STATE
// =====================================================

let scale = 1;

let offsetX = 0;
let offsetY = 0;

function updateTransform() {{

    img.style.transform =
        `translate(${{offsetX}}px, ${{offsetY}}px)
         scale(${{scale}})`;

    info.textContent =
        scale.toFixed(2) + "x";
}}

updateTransform();


// =====================================================
// BASE IMAGE SIZE
// =====================================================

function getBaseImageSize() {{

    const aspect =
        SCREEN_W / SCREEN_H;

    let baseW =
        window.innerWidth;

    let baseH =
        baseW / aspect;

    if(baseH > window.innerHeight) {{

        baseH =
            window.innerHeight;

        baseW =
            baseH * aspect;
    }}

    return {{
        width: baseW,
        height: baseH
    }};
}}


// =====================================================
// ACCURATE MAPPING
// =====================================================

function clientToDesktop(clientX, clientY) {{

    const base = getBaseImageSize();

    const imageX =
        (clientX - offsetX) / scale;

    const imageY =
        (clientY - offsetY) / scale;

    const normX =
        imageX / base.width;

    const normY =
        imageY / base.height;

    const nx =
        Math.max(0, Math.min(1, normX));

    const ny =
        Math.max(0, Math.min(1, normY));

    return {{
        nx,
        ny
    }};
}}


// =====================================================
// TOUCH HANDLING
// =====================================================

let touches = {{}};

let mode = null;

let pinchStartDist = 0;
let pinchStartScale = 1;

let pinchMidX = 0;
let pinchMidY = 0;

viewport.addEventListener(
    "touchstart",
    e => {{

    e.preventDefault();

    for(let t of e.changedTouches) {{
        touches[t.identifier] = t;
    }}

    const count =
        Object.keys(touches).length;

    // =====================================
    // DRAW MODE
    // =====================================

    if(count === 1) {{

        mode = "draw";

        const t = e.touches[0];

        const p =
            clientToDesktop(
                t.clientX,
                t.clientY
            );

        send("down", p.nx, p.ny);

        indicator.style.display = "block";

        indicator.style.left =
            t.clientX + "px";

        indicator.style.top =
            t.clientY + "px";
    }}

    // =====================================
    // PAN / ZOOM MODE
    // =====================================

    else if(count === 2) {{

        mode = "zoom";

        send("up",0,0);

        const ids =
            Object.keys(touches);

        const t1 =
            touches[ids[0]];

        const t2 =
            touches[ids[1]];

        const dx =
            t1.clientX - t2.clientX;

        const dy =
            t1.clientY - t2.clientY;

        pinchStartDist =
            Math.hypot(dx, dy);

        pinchStartScale =
            scale;

        pinchMidX =
            (t1.clientX + t2.clientX) / 2;

        pinchMidY =
            (t1.clientY + t2.clientY) / 2;
    }}

}}, {{passive:false}});


viewport.addEventListener(
    "touchmove",
    e => {{

    e.preventDefault();

    for(let t of e.changedTouches) {{
        touches[t.identifier] = t;
    }}

    const count =
        Object.keys(touches).length;

    // =====================================
    // DRAWING
    // =====================================

    if(mode === "draw" && count === 1) {{

        const t = e.touches[0];

        const p =
            clientToDesktop(
                t.clientX,
                t.clientY
            );

        send("move", p.nx, p.ny);

        indicator.style.left =
            t.clientX + "px";

        indicator.style.top =
            t.clientY + "px";
    }}

    // =====================================
    // ZOOM / PAN
    // =====================================

    else if(mode === "zoom" && count === 2) {{

        const ids =
            Object.keys(touches);

        const t1 =
            touches[ids[0]];

        const t2 =
            touches[ids[1]];

        const dx =
            t1.clientX - t2.clientX;

        const dy =
            t1.clientY - t2.clientY;

        const dist =
            Math.hypot(dx, dy);

        let newScale =
            pinchStartScale *
            (dist / pinchStartDist);

        newScale =
            Math.max(1,
            Math.min(8, newScale));

        const midX =
            (t1.clientX + t2.clientX) / 2;

        const midY =
            (t1.clientY + t2.clientY) / 2;

        const scaleFactor =
            newScale / scale;

        offsetX =
            midX -
            (midX - offsetX)
            * scaleFactor;

        offsetY =
            midY -
            (midY - offsetY)
            * scaleFactor;

        offsetX +=
            (midX - pinchMidX);

        offsetY +=
            (midY - pinchMidY);

        pinchMidX = midX;
        pinchMidY = midY;

        scale = newScale;

        updateTransform();
    }}

}}, {{passive:false}});


viewport.addEventListener(
    "touchend",
    e => {{

    e.preventDefault();

    for(let t of e.changedTouches) {{
        delete touches[t.identifier];
    }}

    const count =
        Object.keys(touches).length;

    if(mode === "draw" && count === 0) {{

        send("up",0,0);

        indicator.style.display = "none";

        mode = null;
    }}

    if(mode === "zoom" && count < 2) {{

        mode = null;
    }}

}}, {{passive:false}});


viewport.addEventListener(
    "touchcancel",
    e => {{

    send("up",0,0);

    mode = null;

    touches = {{}};

}}, {{passive:false}});

</script>

</body>
</html>
"""

# =========================================================
# TABLET WORKER
# =========================================================

def tablet_worker():

    mouse_down = False

    SMOOTH = 0.4

    smooth_x = 0.5
    smooth_y = 0.5

    while True:

        cmd = TOUCH_QUEUE.get()

        try:

            action = cmd[0]

            # =============================================
            # TOUCH DOWN
            # =============================================

            if action == 'TOUCH_DOWN':

                xr, yr = cmd[1], cmd[2]

                smooth_x = xr
                smooth_y = yr

                x = int(smooth_x * SCREEN_W)
                y = int(smooth_y * SCREEN_H)

                pyautogui.moveTo(x, y)

                if not mouse_down:
                    pyautogui.mouseDown(button='left')
                    mouse_down = True

            # =============================================
            # TOUCH MOVE
            # =============================================

            elif action == 'TOUCH_MOVE':

                xr, yr = cmd[1], cmd[2]

                smooth_x += SMOOTH * (xr - smooth_x)
                smooth_y += SMOOTH * (yr - smooth_y)

                x = int(smooth_x * SCREEN_W)
                y = int(smooth_y * SCREEN_H)

                pyautogui.moveTo(x, y)

            # =============================================
            # TOUCH UP
            # =============================================

            elif action == 'TOUCH_UP':

                if mouse_down:
                    pyautogui.mouseUp(button='left')
                    mouse_down = False

        except Exception as e:
            print("Worker error:", e)

        time.sleep(0.001)


# =========================================================
# WEBSOCKET SERVER
# =========================================================

async def ws_handler(websocket):

    async for message in websocket:

        try:

            data = json.loads(message)

            if data.get("type") == "touch":

                action = data["action"]

                x = data.get("x", 0)
                y = data.get("y", 0)

                TOUCH_QUEUE.put((
                    f"TOUCH_{action.upper()}",
                    x,
                    y
                ))

        except Exception as e:
            print("WS error:", e)


def start_ws_server():

    async def main():

        async with websockets.serve(
            ws_handler,
            "0.0.0.0",
            PORT_WS
        ):

            print(f"WebSocket ready on {PORT_WS}")

            await asyncio.Future()

    loop = asyncio.new_event_loop()

    asyncio.set_event_loop(loop)

    loop.run_until_complete(main())


# =========================================================
# HTTP SERVER
# =========================================================

class MJPEGHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):

        # =============================================
        # MAIN PAGE
        # =============================================

        if self.path == "/":

            self.send_response(200)

            self.send_header(
                "Content-type",
                "text/html; charset=utf-8"
            )

            self.send_header(
                "Cache-Control",
                "no-store"
            )

            self.end_headers()

            self.wfile.write(
                HTML_CONTENT.encode()
            )

        # =============================================
        # STREAM
        # =============================================

        elif self.path == "/stream":

            self.send_response(200)

            self.send_header(
                "Content-type",
                "multipart/x-mixed-replace; boundary=--jpgboundary"
            )

            self.end_headers()

            try:

                while True:

                    frame = stream_buffer.get_frame()

                    self.wfile.write(
                        b"--jpgboundary\r\n"
                    )

                    self.wfile.write(
                        b"Content-Type: image/jpeg\r\n"
                    )

                    self.wfile.write(
                        f"Content-Length: {len(frame)}\r\n\r\n".encode()
                    )

                    self.wfile.write(frame)

                    self.wfile.write(b"\r\n")

            except (
                BrokenPipeError,
                ConnectionResetError
            ):
                pass

        else:

            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


class ThreadedHTTPServer(
    socketserver.ThreadingMixIn,
    http.server.HTTPServer
):
    daemon_threads = True
    allow_reuse_address = True


# =========================================================
# GET LOCAL IP
# =========================================================

def get_local_ip():

    try:

        s = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        s.connect(("8.8.8.8", 80))

        ip = s.getsockname()[0]

        s.close()

        return ip

    except:
        return "YOUR_PC_IP"


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    threading.Thread(
        target=screen_capture,
        daemon=True
    ).start()

    threading.Thread(
        target=tablet_worker,
        daemon=True
    ).start()

    threading.Thread(
        target=start_ws_server,
        daemon=True
    ).start()

    time.sleep(0.5)

    server = ThreadedHTTPServer(
        ("0.0.0.0", PORT_HTTP),
        MJPEGHandler
    )

    ip = get_local_ip()

    print("\n╔══════════════════════════════════════╗")
    print("║ GRAPHICS TABLET + LIVE SCREEN MIRROR║")
    print("╚══════════════════════════════════════╝\n")

    print(f"Open on phone:")
    print(f"http://{ip}:{PORT_HTTP}\n")

    print("FEATURES:")
    print(f" • Resolution: {SCREEN_W}x{SCREEN_H}")
    print(" • Live screen mirror")
    print(" • Accurate zoom/pan mapping")
    print(" • Pinch-to-zoom")
    print(" • Two-finger pan")
    print(" • Single finger drawing")
    print(" • Fullscreen mode")
    print(" • Offline hotspot support\n")

    server.serve_forever()