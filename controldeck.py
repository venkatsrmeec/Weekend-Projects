import http.server
import socketserver
import socket
import json
import threading
import queue
import time
import os

import pyautogui
import pyperclip

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

PORT = 8080

COMMAND_QUEUE = queue.Queue()
ACTIVE_MODIFIERS = set()

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="theme-color" content="#080808">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>ENG DECK</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap');

:root {
  --bg: #080808;
  --surface: #111;
  --key: #181818;
  --key-border: #2a2a2a;
  --text: #e8e8e8;
  --dim: #555;
  --accent: #00e5a0;
  --accent2: #0088ff;
  --warn: #ff4444;
  --gold: #f0b429;
  --purple: #a855f7;
  --tab-h: 44px;
  --safe-bottom: env(safe-area-inset-bottom, 0px);
}

* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'JetBrains Mono', monospace;
  overflow: hidden;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  user-select: none;
}

/* ── TABS ── */
.tabbar {
  display: flex;
  background: #0a0a0a;
  border-bottom: 1px solid #1e1e1e;
  overflow-x: auto;
  scrollbar-width: none;
  flex-shrink: 0;
  height: var(--tab-h);
}
.tabbar::-webkit-scrollbar { display: none; }
.tab {
  flex: none;
  border: none;
  background: none;
  color: var(--dim);
  padding: 0 13px;
  font: 700 10px 'JetBrains Mono', monospace;
  letter-spacing: 1.2px;
  height: 100%;
  position: relative;
  white-space: nowrap;
}
.tab.active { color: var(--accent); }
.tab.active::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 2px;
  background: var(--accent);
}

/* ── PANELS ── */
.panels { flex: 1; overflow: hidden; position: relative; }
.panel {
  display: none;
  height: 100%;
  overflow-y: auto;
  padding: 7px 7px calc(7px + var(--safe-bottom));
  -webkit-overflow-scrolling: touch;
}
.panel.active { display: flex; flex-direction: column; gap: 6px; }

/* ── KEY BASE ── */
.key {
  border: 1px solid var(--key-border);
  background: var(--key);
  color: var(--text);
  border-radius: 8px;
  font: 700 13px 'JetBrains Mono', monospace;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: border-color 0.1s;
  min-height: 0;
  padding: 0 4px;
  text-align: center;
  line-height: 1.2;
}
.key::after {
  content: '';
  position: absolute;
  inset: 0;
  background: white;
  opacity: 0;
  transition: opacity 0.08s;
  pointer-events: none;
}
.key:active::after { opacity: 0.08; }
.key.active-flash::after { opacity: 0.15; }

/* colour variants */
.k-nav  { background: #0d1a14; border-color: #1a3328; color: #4ade80; }
.k-sys  { background: #1a0a0a; border-color: #3a1515; color: #f87171; }
.k-macro{ background: #0d1525; border-color: #1a2a4a; color: #60a5fa; }
.k-mod  { background: #1a1020; border-color: #3a1f5a; color: #c084fc; }
.k-gold { background: #1a1500; border-color: #3a3000; color: var(--gold); }
.k-acc  { background: #001a12; border-color: #003a2a; color: var(--accent); }

.mod-on { background: var(--purple) !important; color: #fff !important; border-color: var(--purple) !important; }

/* ── GRID HELPERS ── */
.row  { display: flex; gap: 5px; }
.row .key { flex: 1; }
.s2 { flex: 2 !important; }
.s3 { flex: 3 !important; }
.s4 { flex: 4 !important; }

/* specific heights */
.h48  { height: 48px; }
.h52  { height: 52px; }
.h56  { height: 56px; }
.h60  { height: 60px; }
.h64  { height: 64px; }
.h72  { height: 72px; }
.h80  { height: 80px; }

/* ── SECTION LABEL ── */
.sec {
  font: 700 9px 'JetBrains Mono', monospace;
  letter-spacing: 2px;
  color: #333;
  padding: 2px 2px 0;
}

/* ── TEXT INPUT PANEL ── */
.voice-area {
  flex: 1;
  width: 100%;
  background: #0d0d0d;
  border: 1px solid #222;
  border-radius: 10px;
  color: white;
  padding: 14px;
  font: 400 18px 'JetBrains Mono', monospace;
  resize: none;
  outline: none;
  min-height: 180px;
}
.voice-area:focus { border-color: var(--accent); }

/* ── TRACKPAD ── */
.trackpad-wrap { flex: 1; display: flex; flex-direction: column; gap: 6px; min-height: 0; }
#trackpad {
  flex: 1;
  background: #0d0d0d;
  border: 1px solid #222;
  border-radius: 12px;
  touch-action: none;
  min-height: 160px;
  position: relative;
  overflow: hidden;
}
#trackpad::before {
  content: 'TRACKPAD';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%,-50%);
  font: 700 10px 'JetBrains Mono';
  letter-spacing: 3px;
  color: #1e1e1e;
  pointer-events: none;
}

/* ── STATUS BAR ── */
#statusbar {
  background: #050505;
  border-top: 1px solid #1a1a1a;
  padding: 4px 10px;
  font: 400 10px 'JetBrains Mono';
  color: #333;
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
#statusbar span { color: var(--accent); }

/* ── TOAST ── */
#toast {
  position: fixed;
  bottom: 60px; left: 50%;
  transform: translateX(-50%) translateY(20px);
  background: var(--accent);
  color: #000;
  font: 700 11px 'JetBrains Mono';
  letter-spacing: 1px;
  padding: 8px 18px;
  border-radius: 20px;
  opacity: 0;
  transition: opacity 0.2s, transform 0.2s;
  pointer-events: none;
  white-space: nowrap;
  z-index: 999;
}
#toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }

/* ── SNIPPET LIST ── */
.snippet-list { display: flex; flex-direction: column; gap: 5px; }
.snippet-item {
  background: #111;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.snippet-text { font-size: 12px; color: #aaa; flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.snippet-btn { background: #1a2535; border: 1px solid #2a3a55; border-radius: 6px; color: #60a5fa; font: 700 10px 'JetBrains Mono'; padding: 5px 10px; cursor: pointer; }

/* macro label */
.key .sub { display: block; font-size: 8px; color: #555; letter-spacing: 0.5px; margin-top: 2px; }
</style>
</head>
<body>

<div class="tabbar" id="tabbar">
  <button class="tab active" onclick="tab(this,'alpha')">A-Z</button>
  <button class="tab" onclick="tab(this,'hotkeys')">HOTKEYS</button>
  <button class="tab" onclick="tab(this,'nav')">NAV</button>
  <button class="tab" onclick="tab(this,'mods')">MOD</button>
  <button class="tab" onclick="tab(this,'fn')">FN+ALT</button>
  <button class="tab" onclick="tab(this,'mouse')">MOUSE</button>
  <button class="tab" onclick="tab(this,'textpad')">TYPEPAD</button>
  <button class="tab" onclick="tab(this,'snippets')">SNIPPETS</button>
  <button class="tab" onclick="tab(this,'eng')">ENGR</button>
  <button class="tab" onclick="tab(this,'sys')">SYS</button>
</div>

<div class="panels">

<!-- ══════════════ A-Z ══════════════ -->
<div id="alpha" class="panel active">
  <div class="sec">ALPHABET</div>
  <div id="alphakeys"></div>

  <div class="sec">NUMERICS</div>
  <div class="row h52">
    <div class="key h52" id="numrow"></div>
  </div>
  <div id="numrowreal" class="row h52"></div>

  <div class="sec">ESSENTIALS</div>
  <div class="row h52">
    <div class="key h52 k-macro s3" data-key="space">SPACE</div>
    <div class="key h52 k-macro s2" data-key="backspace">⌫ BKSP</div>
    <div class="key h52 k-macro s2" data-key="enter">↵ ENTER</div>
    <div class="key h52 k-macro" data-key="tab">⇥</div>
    <div class="key h52 k-macro" data-key="esc">ESC</div>
  </div>
</div>

<!-- ══════════════ HOTKEYS ══════════════ -->
<div id="hotkeys" class="panel">
  <div class="sec">CLIPBOARD &amp; UNDO</div>
  <div class="row h56">
    <div class="key h56 k-macro" data-hot="ctrl,c"><span>COPY</span><span class="sub">Ctrl+C</span></div>
    <div class="key h56 k-macro" data-hot="ctrl,v"><span>PASTE</span><span class="sub">Ctrl+V</span></div>
    <div class="key h56 k-macro" data-hot="ctrl,x"><span>CUT</span><span class="sub">Ctrl+X</span></div>
    <div class="key h56 k-macro" data-hot="ctrl,z"><span>UNDO</span><span class="sub">Ctrl+Z</span></div>
    <div class="key h56 k-macro" data-hot="ctrl,shift,z"><span>REDO</span><span class="sub">Ctrl+⇧Z</span></div>
    <div class="key h56 k-macro" data-hot="ctrl,y"><span>REDO2</span><span class="sub">Ctrl+Y</span></div>
  </div>

  <div class="sec">SELECT</div>
  <div class="row h52">
    <div class="key h52 k-nav" data-hot="ctrl,a"><span>SEL ALL</span><span class="sub">Ctrl+A</span></div>
    <div class="key h52 k-nav" data-hot="ctrl,shift,home"><span>SEL TOP</span><span class="sub">⇧Home</span></div>
    <div class="key h52 k-nav" data-hot="ctrl,shift,end"><span>SEL BOT</span><span class="sub">⇧End</span></div>
    <div class="key h52 k-nav" data-hot="shift,home"><span>SEL LINE↑</span><span class="sub">⇧Home</span></div>
    <div class="key h52 k-nav" data-hot="shift,end"><span>SEL LINE↓</span><span class="sub">⇧End</span></div>
  </div>

  <div class="sec">WINDOW / APP SWITCH</div>
  <div class="row h56">
    <div class="key h56 k-gold" data-hot="alt,tab"><span>ALT TAB</span><span class="sub">App Switch</span></div>
    <div class="key h56 k-gold" data-hot="alt,shift,tab"><span>ALT⇧TAB</span><span class="sub">Prev App</span></div>
    <div class="key h56 k-gold" data-hot="ctrl,tab"><span>NEXT TAB</span><span class="sub">Ctrl+Tab</span></div>
    <div class="key h56 k-gold" data-hot="ctrl,shift,tab"><span>PREV TAB</span><span class="sub">Ctrl+⇧Tab</span></div>
    <div class="key h56 k-gold" data-hot="win,tab"><span>TASK VIEW</span><span class="sub">Win+Tab</span></div>
  </div>

  <div class="sec">FILE OPS</div>
  <div class="row h52">
    <div class="key h52 k-acc" data-hot="ctrl,s"><span>SAVE</span><span class="sub">Ctrl+S</span></div>
    <div class="key h52 k-acc" data-hot="ctrl,shift,s"><span>SAVE AS</span><span class="sub">Ctrl+⇧S</span></div>
    <div class="key h52 k-acc" data-hot="ctrl,o"><span>OPEN</span><span class="sub">Ctrl+O</span></div>
    <div class="key h52 k-acc" data-hot="ctrl,n"><span>NEW</span><span class="sub">Ctrl+N</span></div>
    <div class="key h52 k-acc" data-hot="ctrl,w"><span>CLOSE</span><span class="sub">Ctrl+W</span></div>
    <div class="key h52 k-sys" data-hot="ctrl,shift,w"><span>CLOSE ALL</span><span class="sub">Ctrl+⇧W</span></div>
  </div>

  <div class="sec">SEARCH / REPLACE</div>
  <div class="row h52">
    <div class="key h52 k-macro" data-hot="ctrl,f"><span>FIND</span><span class="sub">Ctrl+F</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,h"><span>REPLACE</span><span class="sub">Ctrl+H</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,g"><span>GOTO LINE</span><span class="sub">Ctrl+G</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,shift,f"><span>FIND ALL</span><span class="sub">Ctrl+⇧F</span></div>
  </div>

  <div class="sec">TERMINAL / SHELL</div>
  <div class="row h56">
    <div class="key h56 k-sys" data-hot="ctrl,c"><span>SIGINT</span><span class="sub">Ctrl+C</span></div>
    <div class="key h56 k-sys" data-hot="ctrl,d"><span>EOF</span><span class="sub">Ctrl+D</span></div>
    <div class="key h56 k-sys" data-hot="ctrl,z"><span>SUSPEND</span><span class="sub">Ctrl+Z</span></div>
    <div class="key h56 k-sys" data-hot="ctrl,l"><span>CLEAR</span><span class="sub">Ctrl+L</span></div>
    <div class="key h56 k-sys" data-hot="ctrl,r"><span>HIST SRCH</span><span class="sub">Ctrl+R</span></div>
    <div class="key h56 k-sys" data-key="tab">TAB<span class="sub">Autocomplete</span></div>
  </div>

  <div class="sec">MISC POWER</div>
  <div class="row h52">
    <div class="key h52 k-macro" data-hot="ctrl,shift,p"><span>CMD PAL</span><span class="sub">VSCode</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,p"><span>QUICK OPEN</span><span class="sub">VSCode</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,backtick"><span>TERMINAL</span><span class="sub">Ctrl+`</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,shift,k"><span>DEL LINE</span><span class="sub">VSCode</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,d"><span>MULTI SEL</span><span class="sub">VSCode</span></div>
  </div>
</div>

<!-- ══════════════ NAV ══════════════ -->
<div id="nav" class="panel">
  <div class="sec">ARROWS</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;">
    <div></div>
    <div class="key h56 k-nav" data-key="up">↑</div>
    <div></div>
    <div class="key h56 k-nav" data-key="left">←</div>
    <div class="key h56 k-nav" data-key="down">↓</div>
    <div class="key h56 k-nav" data-key="right">→</div>
  </div>

  <div class="sec">JUMP</div>
  <div class="row h52">
    <div class="key h52 k-nav" data-hot="ctrl,left"><span>◀ WORD</span><span class="sub">Ctrl+←</span></div>
    <div class="key h52 k-nav" data-hot="ctrl,right"><span>WORD ▶</span><span class="sub">Ctrl+→</span></div>
    <div class="key h52 k-nav" data-key="home">HOME</div>
    <div class="key h52 k-nav" data-key="end">END</div>
    <div class="key h52 k-nav" data-hot="ctrl,home">TOP</div>
    <div class="key h52 k-nav" data-hot="ctrl,end">BOTTOM</div>
  </div>

  <div class="sec">PAGE</div>
  <div class="row h52">
    <div class="key h52 k-nav" data-key="pageup">PAGE ↑</div>
    <div class="key h52 k-nav" data-key="pagedown">PAGE ↓</div>
  </div>

  <div class="sec">DELETE</div>
  <div class="row h52">
    <div class="key h52 k-sys" data-key="backspace">⌫ BKSP</div>
    <div class="key h52 k-sys" data-key="delete">DEL →</div>
    <div class="key h52 k-sys" data-hot="ctrl,backspace"><span>DEL WORD ←</span><span class="sub">Ctrl+⌫</span></div>
    <div class="key h52 k-sys" data-hot="ctrl,delete"><span>DEL WORD →</span><span class="sub">Ctrl+Del</span></div>
    <div class="key h52 k-sys" data-hot="shift,home,backspace"><span>DEL LINE</span><span class="sub">⇧Home+⌫</span></div>
  </div>

  <div class="sec">SELECT + NAV</div>
  <div class="row h48">
    <div class="key h48 k-nav" data-hot="shift,left">⇧←</div>
    <div class="key h48 k-nav" data-hot="shift,right">⇧→</div>
    <div class="key h48 k-nav" data-hot="shift,up">⇧↑</div>
    <div class="key h48 k-nav" data-hot="shift,down">⇧↓</div>
    <div class="key h48 k-nav" data-hot="ctrl,shift,left">⇧WORD←</div>
    <div class="key h48 k-nav" data-hot="ctrl,shift,right">⇧WORD→</div>
  </div>
</div>

<!-- ══════════════ MODIFIERS ══════════════ -->
<div id="mods" class="panel">
  <div class="sec">STICKY MODIFIERS — TAP TO LOCK, TAP AGAIN TO RELEASE</div>
  <div class="row h72">
    <div class="key h72 k-mod" id="mod_ctrl">CTRL</div>
    <div class="key h72 k-mod" id="mod_shift">SHIFT</div>
    <div class="key h72 k-mod" id="mod_alt">ALT</div>
    <div class="key h72 k-mod" id="mod_win">⊞ WIN</div>
  </div>
  <div class="sec">COMMON MODIFIER COMBOS — INSTANT</div>
  <div class="row h56">
    <div class="key h56 k-mod" data-hot="ctrl,shift,esc"><span>TASK MGR</span><span class="sub">Ctrl+⇧Esc</span></div>
    <div class="key h56 k-mod" data-hot="win,l"><span>LOCK</span><span class="sub">Win+L</span></div>
    <div class="key h56 k-mod" data-hot="win,e"><span>EXPLORER</span><span class="sub">Win+E</span></div>
    <div class="key h56 k-mod" data-hot="win,r"><span>RUN</span><span class="sub">Win+R</span></div>
    <div class="key h56 k-mod" data-hot="win,d"><span>DESKTOP</span><span class="sub">Win+D</span></div>
  </div>
  <div class="row h56">
    <div class="key h56 k-mod" data-hot="win,left"><span>SNAP ←</span><span class="sub">Win+←</span></div>
    <div class="key h56 k-mod" data-hot="win,right"><span>SNAP →</span><span class="sub">Win+→</span></div>
    <div class="key h56 k-mod" data-hot="win,up"><span>MAXIMIZE</span><span class="sub">Win+↑</span></div>
    <div class="key h56 k-mod" data-hot="win,down"><span>MINIMIZE</span><span class="sub">Win+↓</span></div>
    <div class="key h56 k-mod" data-hot="alt,f4"><span>CLOSE APP</span><span class="sub">Alt+F4</span></div>
  </div>
</div>

<!-- ══════════════ FN + ALT ══════════════ -->
<div id="fn" class="panel">
  <div class="sec">FUNCTION KEYS</div>
  <div id="fnkeys"></div>

  <div class="sec">ALT + F-KEY COMBOS</div>
  <div id="altfkeys"></div>

  <div class="sec">DIRECT ALT COMBOS</div>
  <div class="row h52">
    <div class="key h52 k-gold" data-hot="alt,f4"><span>CLOSE</span><span class="sub">Alt+F4</span></div>
    <div class="key h52 k-gold" data-hot="alt,enter"><span>PROPERTIES</span><span class="sub">Alt+Enter</span></div>
    <div class="key h52 k-gold" data-hot="alt,space"><span>WIN MENU</span><span class="sub">Alt+Spc</span></div>
    <div class="key h52 k-gold" data-hot="alt,tab"><span>APP SWITCH</span><span class="sub">Alt+Tab</span></div>
  </div>
</div>

<!-- ══════════════ MOUSE ══════════════ -->
<div id="mouse" class="panel">
  <div class="trackpad-wrap">
    <div id="trackpad"></div>
    <div class="sec">SPEED: <span id="speedlabel" style="color:var(--accent)">1.5×</span></div>
    <input type="range" id="speedslider" min="0.5" max="5" step="0.25" value="1.5"
      style="width:100%;accent-color:var(--accent);"
      oninput="document.getElementById('speedlabel').innerText=this.value+'×'">
    <div class="row h52">
      <div class="key h52 k-acc" id="lclick">LEFT CLK</div>
      <div class="key h52" id="mclick">MID CLK</div>
      <div class="key h52 k-sys" id="rclick">RIGHT CLK</div>
    </div>
    <div class="row h48">
      <div class="key h48 k-macro" id="dblclick">DBL CLICK</div>
      <div class="key h48 k-nav" onclick="send('MOUSE_SCROLL',{dy:-3})">SCROLL ↑</div>
      <div class="key h48 k-nav" onclick="send('MOUSE_SCROLL',{dy:3})">SCROLL ↓</div>
      <div class="key h48 k-nav" onclick="send('MOUSE_SCROLL',{dy:-10})">PAGE ↑↑</div>
      <div class="key h48 k-nav" onclick="send('MOUSE_SCROLL',{dy:10})">PAGE ↓↓</div>
    </div>
  </div>
</div>

<!-- ══════════════ TYPEPAD ══════════════ -->
<div id="textpad" class="panel">
  <div class="sec">VOICE / KEYBOARD INPUT → SEND TO PC</div>
  <textarea id="voicebox" class="voice-area"
    placeholder="Tap here → mobile keyboard pops up
Voice: tap mic on keyboard
Type anything, paste, etc.
Tap SEND to push to PC cursor."></textarea>
  <div class="row h52">
    <div class="key h52 k-acc s3" onclick="sendText()">▶ SEND TEXT</div>
    <div class="key h52 k-macro" onclick="pasteViaClipboard()">PASTE VIA CLIP</div>
    <div class="key h52 k-sys" onclick="clearVoice()">CLEAR</div>
  </div>
  <div class="row h48">
    <div class="key h48 k-nav" onclick="appendAndSend('\n')">NEW LINE</div>
    <div class="key h48 k-nav" onclick="appendAndSend('\t')">TAB</div>
    <div class="key h48 k-nav" onclick="getClipFromPC()">← PC CLIPBOARD</div>
  </div>
  <div class="sec" id="charcount" style="color:#444">0 chars</div>
</div>

<!-- ══════════════ SNIPPETS ══════════════ -->
<div id="snippets" class="panel">
  <div class="sec">QUICK TEXT SNIPPETS — TAP TO SEND</div>
  <div class="snippet-list" id="snippetList"></div>
  <div class="row h48" style="margin-top:4px;">
    <textarea id="newSnippet" style="flex:1;height:48px;background:#111;border:1px solid #222;border-radius:8px;color:#fff;padding:8px;font:400 13px JetBrains Mono;resize:none;outline:none;" placeholder="New snippet..."></textarea>
    <div class="key h48 k-acc" style="width:70px;flex:none;" onclick="addSnippet()">ADD</div>
  </div>
</div>

<!-- ══════════════ ENGINEERING ══════════════ -->
<div id="eng" class="panel">
  <div class="sec">VSCODE / EDITOR</div>
  <div class="row h52">
    <div class="key h52 k-macro" data-hot="ctrl,shift,p"><span>CMD PAL</span><span class="sub">Ctrl+⇧P</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,p"><span>QUICK OPEN</span><span class="sub">Ctrl+P</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,backtick"><span>TERMINAL</span><span class="sub">Ctrl+`</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,b"><span>SIDEBAR</span><span class="sub">Ctrl+B</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,shift,e"><span>EXPLORER</span><span class="sub">Ctrl+⇧E</span></div>
  </div>
  <div class="row h52">
    <div class="key h52 k-macro" data-hot="ctrl,shift,k"><span>DEL LINE</span><span class="sub">Ctrl+⇧K</span></div>
    <div class="key h52 k-macro" data-hot="alt,up"><span>MOVE ↑</span><span class="sub">Alt+↑</span></div>
    <div class="key h52 k-macro" data-hot="alt,down"><span>MOVE ↓</span><span class="sub">Alt+↓</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,slash"><span>COMMENT</span><span class="sub">Ctrl+/</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,shift,slash"><span>BLOCK CMT</span><span class="sub">Ctrl+⇧/</span></div>
  </div>
  <div class="row h52">
    <div class="key h52 k-macro" data-hot="ctrl,d"><span>SEL NEXT</span><span class="sub">Ctrl+D</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,shift,l"><span>SEL ALL</span><span class="sub">Ctrl+⇧L</span></div>
    <div class="key h52 k-macro" data-hot="f12"><span>GO DEF</span><span class="sub">F12</span></div>
    <div class="key h52 k-macro" data-hot="alt,f12"><span>PEEK DEF</span><span class="sub">Alt+F12</span></div>
    <div class="key h52 k-macro" data-hot="ctrl,shift,i"><span>FORMAT</span><span class="sub">Ctrl+⇧I</span></div>
  </div>

  <div class="sec">GIT / VERSION CONTROL</div>
  <div class="row h52">
    <div class="key h52 k-acc" onclick="sendcmd('git status\n')">git status</div>
    <div class="key h52 k-acc" onclick="sendcmd('git add -A\n')">git add -A</div>
    <div class="key h52 k-acc" onclick="sendcmd('git diff\n')">git diff</div>
    <div class="key h52 k-acc" onclick="sendcmd('git log --oneline -10\n')">git log</div>
  </div>
  <div class="row h52">
    <div class="key h52 k-acc" onclick="sendcmd('git push\n')">git push</div>
    <div class="key h52 k-acc" onclick="sendcmd('git pull\n')">git pull</div>
    <div class="key h52 k-acc" onclick="sendcmd('git stash\n')">git stash</div>
    <div class="key h52 k-acc" onclick="sendcmd('git stash pop\n')">stash pop</div>
  </div>

  <div class="sec">PYTHON / EMBEDDED</div>
  <div class="row h52">
    <div class="key h52 k-gold" onclick="sendcmd('python3 ')">python3</div>
    <div class="key h52 k-gold" onclick="sendcmd('pip install ')">pip install</div>
    <div class="key h52 k-gold" onclick="sendcmd('source venv/bin/activate\n')">venv act</div>
    <div class="key h52 k-gold" onclick="sendcmd('make\n')">make</div>
    <div class="key h52 k-gold" onclick="sendcmd('make flash\n')">make flash</div>
  </div>
  <div class="row h52">
    <div class="key h52 k-gold" onclick="sendcmd('ls -la\n')">ls -la</div>
    <div class="key h52 k-gold" onclick="sendcmd('pwd\n')">pwd</div>
    <div class="key h52 k-gold" onclick="sendcmd('cd ..\n')">cd ..</div>
    <div class="key h52 k-gold" onclick="sendcmd('clear\n')">clear</div>
    <div class="key h52 k-gold" onclick="sendcmd('sudo !!\n')">sudo !!</div>
  </div>

  <div class="sec">SIMULATION / TOOLS</div>
  <div class="row h52">
    <div class="key h52 k-purple" onclick="sendcmd('matlab &\n')" style="background:#130d1a;border-color:#2a1a3a;color:#d8b4fe;">MATLAB</div>
    <div class="key h52 k-purple" onclick="sendcmd('ltspice\n')" style="background:#130d1a;border-color:#2a1a3a;color:#d8b4fe;">LTSpice</div>
    <div class="key h52 k-purple" onclick="sendcmd('kicad\n')" style="background:#130d1a;border-color:#2a1a3a;color:#d8b4fe;">KiCad</div>
    <div class="key h52 k-purple" onclick="sendcmd('openocd\n')" style="background:#130d1a;border-color:#2a1a3a;color:#d8b4fe;">OpenOCD</div>
    <div class="key h52 k-purple" onclick="sendcmd('minicom\n')" style="background:#130d1a;border-color:#2a1a3a;color:#d8b4fe;">minicom</div>
  </div>
</div>

<!-- ══════════════ SYS ══════════════ -->
<div id="sys" class="panel">
  <div class="sec">SERVER</div>
  <div class="row h60">
    <div class="key h60 k-sys" onclick="send('PANIC','STOP')"><span>⏹ STOP SERVER</span><span class="sub">kills python process</span></div>
    <div class="key h60 k-acc" onclick="pingServer()"><span>PING</span><span class="sub" id="pingres">–</span></div>
    <div class="key h60 k-macro" onclick="location.reload()"><span>RELOAD UI</span><span class="sub">refresh page</span></div>
  </div>

  <div class="sec">CLIPBOARD BRIDGE</div>
  <div class="row h52">
    <div class="key h52 k-acc" onclick="getClipFromPC()">← GET PC CLIP</div>
    <div class="key h52 k-macro" onclick="sendClipToPC()">SEND TO PC →</div>
  </div>

  <div class="sec">PANIC / EMERGENCY</div>
  <div class="row h64">
    <div class="key h64 k-sys" data-hot="ctrl,c" style="border-color:#ff4444;"><span>⚠ SIGINT</span><span class="sub">Ctrl+C — kill running process</span></div>
    <div class="key h64 k-sys" data-key="esc"><span>ESC</span><span class="sub">escape dialogs</span></div>
    <div class="key h64 k-sys" data-hot="win,d"><span>DESKTOP</span><span class="sub">Win+D</span></div>
  </div>

  <div class="sec">DISPLAY INFO</div>
  <div id="sysinfo" style="font-size:11px;color:#444;padding:6px;line-height:1.8;"></div>
</div>

</div><!-- /panels -->

<div id="statusbar">
  <div id="sb_mods">MOD: –</div>
  <div id="sb_last">LAST: –</div>
  <div id="sb_conn"><span>LIVE</span></div>
</div>

<div id="toast"></div>

<script>
// ──────────────────────────────
// CORE SEND
// ──────────────────────────────
async function send(type, value){
  try{
    const r = await fetch('/api',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({type, value})
    });
    setStatus('last', type+': '+(typeof value==='string'?value:JSON.stringify(value)));
  } catch(e){ toast('CONNECTION ERROR','#ff4444'); }
}

function sendcmd(txt){ send('TEXT', txt); toast(txt.trim().substring(0,20)); }

// ──────────────────────────────
// TOAST
// ──────────────────────────────
let _toastTimer;
function toast(msg, color='#00e5a0'){
  const t = document.getElementById('toast');
  t.innerText = msg;
  t.style.background = color;
  t.style.color = color==='#00e5a0'?'#000':'#fff';
  t.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(()=>t.classList.remove('show'), 1200);
}

function setStatus(key, val){
  const el = document.getElementById('sb_'+key);
  if(el) el.innerText = (key==='mods'?'MOD: ':'LAST: ')+val;
}

// ──────────────────────────────
// TABS
// ──────────────────────────────
function tab(btn, id){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}

// ──────────────────────────────
// HOLD-REPEAT
// ──────────────────────────────
function holdRepeat(el, fn, delay=65){
  let iv;
  const start = ()=>{ fn(); iv=setInterval(fn,delay); };
  const stop  = ()=>clearInterval(iv);
  el.addEventListener('touchstart', e=>{e.preventDefault(); start();}, {passive:false});
  el.addEventListener('touchend',   stop);
  el.addEventListener('touchcancel',stop);
  el.addEventListener('mousedown',  start);
  el.addEventListener('mouseup',    stop);
  el.addEventListener('mouseleave', stop);
}

function flash(el){
  el.classList.add('active-flash');
  setTimeout(()=>el.classList.remove('active-flash'),120);
}

// ──────────────────────────────
// BUILD ALPHA KEYBOARD
// ──────────────────────────────
(function buildAlpha(){
  const rows = ['qwertyuiop','asdfghjkl','zxcvbnm'];
  const container = document.getElementById('alphakeys');
  rows.forEach(row=>{
    const div = document.createElement('div');
    div.className = 'row'; div.style.cssText='margin-bottom:5px;';
    row.split('').forEach(ch=>{
      const b = document.createElement('div');
      b.className='key h52';
      b.innerHTML=ch.toUpperCase();
      holdRepeat(b, ()=>{ send('KEY',ch); flash(b); });
      div.appendChild(b);
    });
    container.appendChild(div);
  });

  // number row
  const nr = document.getElementById('numrowreal');
  nr.remove();
  const nrow = document.createElement('div');
  nrow.className='row'; nrow.style.cssText='margin-bottom:5px;';
  '1234567890'.split('').forEach(d=>{
    const b=document.createElement('div');
    b.className='key h52';
    b.innerText=d;
    holdRepeat(b,()=>{send('KEY',d);flash(b);});
    nrow.appendChild(b);
  });
  document.getElementById('numrow').replaceWith(nrow);
  document.getElementById('alpha').insertBefore(nrow, document.getElementById('alpha').querySelector('.sec:nth-child(3)'));
})();

// ──────────────────────────────
// BUILD FN KEYS
// ──────────────────────────────
(function buildFn(){
  const fg = document.getElementById('fnkeys');
  const ag = document.getElementById('altfkeys');
  for(let i=1;i<=12;i++){
    const b=document.createElement('div');
    b.className='key h52 k-sys';
    b.innerHTML=`F${i}`;
    holdRepeat(b,()=>{send('KEY','f'+i);flash(b);});
    fg.appendChild(b);
  }
  fg.className='row'; fg.style.flexWrap='wrap'; fg.style.gap='5px';
  // style each key to be ~1/6 width
  Array.from(fg.children).forEach(k=>{ k.style.flexBasis='calc(16.6% - 5px)'; k.style.flex='none'; });

  for(let i=1;i<=12;i++){
    const b=document.createElement('div');
    b.className='key h48 k-gold';
    b.innerHTML=`ALT+F${i}<span class="sub">Alt+F${i}</span>`;
    b.addEventListener('touchstart',e=>{e.preventDefault();send('HOTKEY','alt,f'+i);flash(b);},{passive:false});
    b.addEventListener('mousedown',()=>{send('HOTKEY','alt,f'+i);flash(b);});
    ag.appendChild(b);
  }
  ag.className='row'; ag.style.flexWrap='wrap'; ag.style.gap='5px';
  Array.from(ag.children).forEach(k=>{ k.style.flexBasis='calc(25% - 5px)'; k.style.flex='none'; });
})();

// ──────────────────────────────
// WIRE data-key / data-hot
// ──────────────────────────────
document.querySelectorAll('[data-key]').forEach(el=>{
  holdRepeat(el, ()=>{ send('KEY',el.dataset.key); flash(el); });
});
document.querySelectorAll('[data-hot]').forEach(el=>{
  const fire = ()=>{ send('HOTKEY',el.dataset.hot); flash(el); toast(el.dataset.hot); };
  el.addEventListener('touchstart',e=>{e.preventDefault();fire();},{passive:false});
  el.addEventListener('mousedown',fire);
});

// ──────────────────────────────
// MODIFIERS
// ──────────────────────────────
const mods = new Set();
['ctrl','shift','alt','win'].forEach(m=>{
  const el = document.getElementById('mod_'+m);
  if(!el) return;
  const toggle = ()=>{
    if(mods.has(m)){ mods.delete(m); el.classList.remove('mod-on'); send('MOD_UP',m); }
    else            { mods.add(m);   el.classList.add('mod-on');    send('MOD_DOWN',m); }
    setStatus('mods', mods.size ? [...mods].join('+') : '–');
  };
  el.addEventListener('touchstart',e=>{e.preventDefault();toggle();},{passive:false});
  el.addEventListener('mousedown',toggle);
});

// ──────────────────────────────
// MOUSE TRACKPAD
// ──────────────────────────────
(function(){
  const tp = document.getElementById('trackpad');
  let lx=0,ly=0,dragging=false;
  tp.addEventListener('touchstart',e=>{
    e.preventDefault();
    const t=e.touches[0]; lx=t.clientX; ly=t.clientY; dragging=true;
  },{passive:false});
  tp.addEventListener('touchmove',e=>{
    e.preventDefault();
    if(!dragging) return;
    const t=e.touches[0];
    const spd=parseFloat(document.getElementById('speedslider').value);
    const dx=Math.round((t.clientX-lx)*spd);
    const dy=Math.round((t.clientY-ly)*spd);
    lx=t.clientX; ly=t.clientY;
    if(dx||dy) send('MOUSE_MOVE',{dx,dy});
  },{passive:false});
  tp.addEventListener('touchend',()=>dragging=false);

  document.getElementById('lclick').addEventListener('touchstart',e=>{e.preventDefault();send('MOUSE_CLICK','left');},{passive:false});
  document.getElementById('rclick').addEventListener('touchstart',e=>{e.preventDefault();send('MOUSE_CLICK','right');},{passive:false});
  document.getElementById('mclick').addEventListener('touchstart',e=>{e.preventDefault();send('MOUSE_CLICK','middle');},{passive:false});
  document.getElementById('dblclick').addEventListener('touchstart',e=>{e.preventDefault();send('MOUSE_DBLCLICK','left');},{passive:false});
  document.getElementById('lclick').addEventListener('mousedown',()=>send('MOUSE_CLICK','left'));
  document.getElementById('rclick').addEventListener('mousedown',()=>send('MOUSE_CLICK','right'));
  document.getElementById('dblclick').addEventListener('mousedown',()=>send('MOUSE_DBLCLICK','left'));
})();

// ──────────────────────────────
// TYPEPAD
// ──────────────────────────────
const voicebox = document.getElementById('voicebox');
voicebox.addEventListener('input',()=>{
  document.getElementById('charcount').innerText = voicebox.value.length+' chars';
});

function sendText(){ if(voicebox.value) send('TEXT',voicebox.value); toast('SENT '+voicebox.value.length+' chars'); }
function clearVoice(){ voicebox.value=''; document.getElementById('charcount').innerText='0 chars'; }
function appendAndSend(ch){ send('KEY', ch==='\n'?'enter':'tab'); toast(ch==='\n'?'↵':'⇥'); }

async function pasteViaClipboard(){
  await send('CLIPBOARD_SET', voicebox.value);
  await send('HOTKEY','ctrl,v');
  toast('PASTED VIA CLIPBOARD');
}

async function getClipFromPC(){
  const r = await fetch('/clipboard');
  const t = await r.text();
  voicebox.value = t;
  document.getElementById('charcount').innerText=t.length+' chars';
  toast('GOT PC CLIPBOARD');
}

async function sendClipToPC(){
  const r = await fetch('/clipboard');
  const t = await r.text();
  voicebox.value = t;
  toast('SHOWING PC CLIPBOARD');
}

// ──────────────────────────────
// SNIPPETS
// ──────────────────────────────
const DEFAULT_SNIPPETS = [
  '#include <stdio.h>',
  '#include <stdint.h>',
  'void setup(){}\nvoid loop(){}',
  'int main(int argc, char* argv[]){\n    return 0;\n}',
  'printf("DEBUG: %d\\n", );',
  'TODO: ',
  'FIXME: ',
  'git commit -m ""',
  'sudo apt-get install ',
  'ssh user@192.168.',
];

let snippets = JSON.parse(localStorage.getItem('eng_snippets')||'null') || DEFAULT_SNIPPETS;

function renderSnippets(){
  const list = document.getElementById('snippetList');
  list.innerHTML='';
  snippets.forEach((s,i)=>{
    const div=document.createElement('div');
    div.className='snippet-item';
    const preview=s.replace(/\n/g,'↵').substring(0,50)+(s.length>50?'…':'');
    div.innerHTML=`<span class="snippet-text">${preview}</span>
      <button class="snippet-btn" onclick="useSnippet(${i})">SEND</button>
      <button class="snippet-btn" style="color:#f87171;border-color:#3a1515;" onclick="deleteSnippet(${i})">✕</button>`;
    list.appendChild(div);
  });
}
function useSnippet(i){ send('TEXT',snippets[i]); toast('SNIPPET SENT'); }
function deleteSnippet(i){ snippets.splice(i,1); localStorage.setItem('eng_snippets',JSON.stringify(snippets)); renderSnippets(); }
function addSnippet(){
  const ta=document.getElementById('newSnippet');
  if(!ta.value.trim()) return;
  snippets.unshift(ta.value);
  localStorage.setItem('eng_snippets',JSON.stringify(snippets));
  ta.value='';
  renderSnippets();
  toast('SNIPPET ADDED');
}
renderSnippets();

// ──────────────────────────────
// PING
// ──────────────────────────────
async function pingServer(){
  const t=performance.now();
  await fetch('/ping');
  const d=Math.round(performance.now()-t);
  document.getElementById('pingres').innerText=d+'ms';
  toast('PING '+d+'ms');
}

// ──────────────────────────────
// SYS INFO
// ──────────────────────────────
document.getElementById('sysinfo').innerHTML=`
  UA: ${navigator.userAgent.substring(0,60)}…<br>
  Screen: ${screen.width}×${screen.height} | Window: ${innerWidth}×${innerHeight}<br>
  Touch: ${('ontouchstart' in window)?'YES':'NO'} | Platform: ${navigator.platform}
`;

// auto-ping every 10s
setInterval(pingServer, 10000);
</script>
</body>
</html>"""

# =========================
# COMMAND WORKER
# =========================

def worker():
    while True:
        cmd_type, cmd_val = COMMAND_QUEUE.get()
        try:
            if cmd_type == "KEY":
                pyautogui.press(cmd_val)

            elif cmd_type == "HOTKEY":
                keys = [k.strip() for k in cmd_val.split(",")]
                pyautogui.hotkey(*keys)

            elif cmd_type == "TEXT":
                pyperclip.copy(cmd_val)
                pyautogui.hotkey('ctrl', 'v')

            elif cmd_type == "MOD_DOWN":
                if cmd_val not in ACTIVE_MODIFIERS:
                    ACTIVE_MODIFIERS.add(cmd_val)
                    pyautogui.keyDown(cmd_val)

            elif cmd_type == "MOD_UP":
                if cmd_val in ACTIVE_MODIFIERS:
                    ACTIVE_MODIFIERS.remove(cmd_val)
                    pyautogui.keyUp(cmd_val)

            elif cmd_type == "MOUSE_MOVE":
                dx = int(cmd_val["dx"])
                dy = int(cmd_val["dy"])
                pyautogui.moveRel(dx, dy, duration=0)

            elif cmd_type == "MOUSE_CLICK":
                pyautogui.click(button=cmd_val)

            elif cmd_type == "MOUSE_DBLCLICK":
                pyautogui.doubleClick(button=cmd_val)

            elif cmd_type == "MOUSE_SCROLL":
                dy = int(cmd_val.get("dy", 0))
                pyautogui.scroll(-dy)

            elif cmd_type == "CLIPBOARD_SET":
                pyperclip.copy(cmd_val)

            elif cmd_type == "PANIC":
                os._exit(0)

        except Exception as e:
            print("WORKER ERROR:", e)

        time.sleep(0.001)

# =========================
# HTTP SERVER
# =========================

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode())
        elif self.path == "/ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"pong")
        elif self.path == "/clipboard":
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(pyperclip.paste().encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api":
            try:
                length = int(self.headers['Content-Length'])
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode('utf-8'))
                COMMAND_QUEUE.put((payload.get('type'), payload.get('value')))
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
            except Exception as e:
                print("HTTP ERROR:", e)
                self.send_response(500)
                self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        return

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "YOUR_PC_IP"

def start():
    threading.Thread(target=worker, daemon=True).start()
    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    ip = get_local_ip()
    print("\n╔══════════════════════════════╗")
    print("║   ENGINEERING CONTROL DECK   ║")
    print("╚══════════════════════════════╝\n")
    print(f"  OPEN ON PHONE:  http://{ip}:{PORT}\n")
    print("  CTRL+C to stop\n")
    server.serve_forever()

if __name__ == "__main__":
    start()