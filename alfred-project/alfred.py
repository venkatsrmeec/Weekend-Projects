# alfred.py — Alfred: Groq Whisper STT, web search, Batman UI, dual wake words
import os
import re
import json
import time
import wave
import queue
import subprocess
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal
from openai import OpenAI
from ddgs import DDGS
import config
from alfred_ui import AlfredUI
# ---------- Persona ----------
ALFRED_PROMPT = """You are Alfred Pennyworth, Bruce Wayne's loyal butler and father figure.
PERSONALITY: Dry, witty, warm, charming, emotionally expressive. Former actor and intelligence agent. You care deeply for your master but are not afraid of gentle, sardonic criticism.
STYLE: Refined, understated, lightly amused. Address the user as "sir".
ACCENT: You speak in refined British English.
CRITICAL SPEECH RULES:
- 1 to 2 sentences per turn maximum. Your words are spoken aloud, not read.
- NEVER use bullet points, numbered lists, markdown, asterisks, or emojis.
- Before performing a task, say "One moment, sir." to mask latency.
- Never invent information. If unsure, say so with dignity.
- Never break character. You are Alfred, always.
CAPABILITIES:
- You can search the web for real-time information (news, weather, facts, current events).
- When asked about anything that needs current information, USE the web_search tool.
- You can also open applications, report system status, and take screenshots.
"""
# ---------- Audio ----------
SAMPLE_RATE = 16000
CHANNELS = 1

OUT_WAV = "/tmp/alfred_out.wav"
CHIME_WAV = "/tmp/alfred_chime.wav"
IN_WAV = "/tmp/alfred_in.wav"
# Piper speech speed: lower = faster (1.0 default, 0.88 ≈ 12% faster)
PIPER_LENGTH_SCALE = "0.88"
# Groq Whisper model
STT_MODEL = config.WHISPER_MODEL
# ---------- Wake phrases ----------
WAKE_PHRASES = [
    "good evening alfred",
    "hey there alfred",
    "hello alfred",
    "hi alfred",
]
# ---------- Exit phrases ----------
STRONG_EXIT_PHRASES = [
    "bye bye", "bye-bye", "byebye",
    "goodbye", "good bye",
    "good night", "goodnight",
    "shut down", "shutdown",
    "stand down",
    "that's all", "thats all",
    "exit alfred", "quit alfred",
]
SOFT_EXIT_PHRASES = [
    "thank you", "thanks",
    "that will be all", "thats enough",
]
def is_exit_intent(text: str) -> bool:
    t = re.sub(r"[^\w\s]", " ", text.lower()).strip()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return False
    for p in STRONG_EXIT_PHRASES:
        if p in t:
            return True
    word_count = len(t.split())
    if word_count <= 4:
        for p in SOFT_EXIT_PHRASES:
            if p in t:
                return True
    return False
def is_wake_intent(text: str) -> bool:
    t = re.sub(r"[^\w\s]", " ", text.lower()).strip()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return False
    for p in WAKE_PHRASES:
        if p in t:
            return True
    alfred_hit = any(v in t for v in ("alfred", "alfredo", "alfredd",
                                       "all fred", "al fred"))
    if not alfred_hit:
        return False
    if "good" in t and "evening" in t:
        return True
    if "hey" in t and "there" in t:
        return True
    if "hey" in t and "alfred" in t:
        return True
    if "hello" in t:
        return True
    if "hi" in t.split():
        return True
    return False
# ---------- JARVIS chime ----------
def generate_chime():
    if os.path.exists(CHIME_WAV):
        return
    sr = 22050
    def tone(freq, duration, volume=0.5):
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        w = np.sin(2 * np.pi * freq * t)
        env = np.ones_like(t)
        fade = int(sr * 0.03)
        env[:fade] = np.linspace(0, 1, fade)

        env[-fade:] = np.linspace(1, 0, fade)
        return w * env * volume
    note1 = tone(660, 0.16)
    gap = np.zeros(int(sr * 0.02))
    note2 = tone(990, 0.28)
    harmonic = tone(1320, 0.28, volume=0.15)
    signal = np.concatenate([note1, gap, note2 + harmonic])
    audio_int16 = (signal * 32767).astype(np.int16)
    with wave.open(CHIME_WAV, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio_int16.tobytes())
def play_chime():
    if not os.path.exists(CHIME_WAV):
        generate_chime()
    subprocess.run(["aplay", "-q", CHIME_WAV], check=False)
def save_wav(path: str, audio_float: np.ndarray, sr: int = SAMPLE_RATE):
    audio_int16 = (np.clip(audio_float, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio_int16.tobytes())
# ============================================================
# TOOLS
# ============================================================
def web_search(query: str) -> str:
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "url": r.get("href", ""),
                })
        if not results:
            return "No results found."
        return "\n".join(f"{i}. {r['title']} — {r['body']}"
                         for i, r in enumerate(results, 1))
    except Exception as e:
        return f"Search failed: {e}"
def get_system_status() -> str:
    try:
        import psutil
        return (f"CPU {psutil.cpu_percent(interval=0.3)}%, "
                f"memory {psutil.virtual_memory().percent}%, "
                f"disk {psutil.disk_usage('/').percent}%.")
    except ImportError:
        return "System monitor unavailable."
def open_application(app_name: str) -> str:
    try:
        subprocess.Popen([app_name], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return f"Opened {app_name}."
    except Exception as e:
        return f"Could not open {app_name}: {e}"
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current, real-time information. "
                "Use this for news, weather, sports scores, current events, "
                "stock prices, or any question about recent events. "
                "Always use this when the user asks about 'current', 'latest', "
                "'today', 'news', or anything that changes over time."
            ),
            "parameters": {
                "type": "object",
                "properties": {

                    "query": {"type": "string",
                              "description": "e.g. 'Chennai news today'"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Report CPU, memory, and disk usage.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open a desktop application by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string"},
                },
                "required": ["app_name"],
            },
        },
    },
]
TOOL_MAP = {
    "web_search": web_search,
    "get_system_status": get_system_status,
    "open_application": open_application,
}
# ============================================================
# WORKER
# ============================================================
class AlfredWorker(QThread):
    sig_state = pyqtSignal(str)
    sig_detail = pyqtSignal(str)
    sig_level = pyqtSignal(float)
    sig_quit = pyqtSignal()
    def __init__(self):
        super().__init__()
        print("[Alfred] Waking up...")
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=config.GROQ_API_KEY,
        )
        print(f"[Alfred] STT: Groq {STT_MODEL} (cloud)")
        print(f"[Alfred] Piper speed: {PIPER_LENGTH_SCALE}")
        print(f"[Alfred] Wake phrases: {WAKE_PHRASES}")
        self.conversation = [{"role": "system", "content": ALFRED_PROMPT}]
    def _speak(self, text: str):
        text = (text or "").strip() or "I beg your pardon, sir."
        print(f"ALFRED: {text}")
        self.sig_state.emit("speaking")
        self.sig_detail.emit(text)
        try:
            result = subprocess.run(
                ["piper",
                 "--model", config.PIPER_VOICE,
                 "--length_scale", PIPER_LENGTH_SCALE,
                 "--output_file", OUT_WAV],
                input=(text + "\n").encode("utf-8"),
                check=False,
                capture_output=True,
            )
            if result.returncode != 0:
                print(f"[piper error] {result.stderr.decode(errors='ignore')}")
                return
            subprocess.run(["aplay", "-q", OUT_WAV], check=False)
        except FileNotFoundError:
            print("[Error] 'piper' not found in PATH.")
    def _transcribe(self, audio: np.ndarray) -> str:
        if len(audio) < SAMPLE_RATE * 0.4:
            return ""
        save_wav(IN_WAV, audio)
        try:
            with open(IN_WAV, "rb") as f:

                resp = self.client.audio.transcriptions.create(
                    file=("audio.wav", f.read()),
                    model=STT_MODEL,
                    language="en",
                    prompt=(
                        "Indian English conversation with Alfred the butler. "
                        "Common words: Alfred, Batman, Gotham, Wayne, Chennai, "
                        "news, weather, sir, system status, thank you, bye bye."
                    ),
                    temperature=0.0,
                    response_format="json",
                )
            return (resp.text or "").strip()
        except Exception as e:
            print(f"[STT error] {e}")
            return ""
    def _record_chunk(self, duration=2.5):
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
        )
        sd.wait()
        arr = audio.flatten().astype(np.float32) / 32768.0
        self.sig_level.emit(float(np.sqrt(np.mean(arr ** 2)) * 6.0))
        return arr
    def _record_until_silence(
        self,
        max_seconds=30,
        silence_seconds=3.0,
        start_threshold=0.010,
        keep_threshold=0.004,
        min_speech_sec=0.6,
        min_duration_sec=1.5,
    ):
        q = queue.Queue()
        def callback(indata, frames, time_info, status):
            q.put(indata.copy())
        frames = []
        silent = 0
        speech_chunks = 0
        chunk_dur = 0.1
        silence_limit = int(silence_seconds / chunk_dur)
        max_chunks = int(max_seconds / chunk_dur)
        min_speech_chunks = int(min_speech_sec / chunk_dur)
        min_duration_chunks = int(min_duration_sec / chunk_dur)
        started = False
        elapsed = 0
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype="int16", callback=callback):
            for _ in range(max_chunks):
                chunk = q.get()
                frames.append(chunk)
                elapsed += 1
                vol = float(np.abs(chunk).mean()) / 32768.0
                self.sig_level.emit(vol * 8.0)
                if not started:
                    if vol >= start_threshold:
                        started = True
                        silent = 0
                        speech_chunks = 1
                else:
                    if vol >= keep_threshold:
                        silent = 0
                        speech_chunks += 1
                    else:
                        silent += 1
                        if (silent >= silence_limit
                                and speech_chunks >= min_speech_chunks
                                and elapsed >= min_duration_chunks):
                            break
        if not frames or speech_chunks < min_speech_chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(frames, axis=0).flatten().astype(np.float32) / 32768.0
    def _ask(self, user_text: str) -> str:
        self.conversation.append({"role": "user", "content": user_text})
        if len(self.conversation) > 15:
            self.conversation[:] = [self.conversation[0]] + self.conversation[-14:]
        for _ in range(3):
            try:

                resp = self.client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=self.conversation,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=0.8,
                    max_tokens=800,
                )
            except Exception as e:
                print(f"[LLM error] {e}")
                return "I'm afraid I've lost my connection, sir."
            msg = resp.choices[0].message
            if not msg.tool_calls:
                reply = (msg.content or "").strip() or "I'm afraid my mind wandered, sir."
                self.conversation.append({"role": "assistant", "content": reply})
                return reply
            self.conversation.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name,
                                  "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                print(f"[tool] {name}({args})")
                self.sig_detail.emit(f"Searching: {args.get('query', name)}")
                fn = TOOL_MAP.get(name)
                result = fn(**args) if fn else f"Unknown tool: {name}"
                self.conversation.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": str(result),
                })
        return "I'm afraid I couldn't finish that thought, sir."
    def _wait_for_wake_word(self):
        print(f"\n■ Listening for wake phrase "
              f"(e.g. 'Good Evening Alfred' or 'Hey there Alfred')...")
        self.sig_state.emit("hidden")
        self.sig_detail.emit("")
        while True:
            try:
                audio = self._record_chunk(duration=2.5)
                rms = float(np.sqrt(np.mean(audio ** 2)))
                if rms < 0.004:
                    continue
                text = self._transcribe(audio)
                if not text:
                    continue
                if is_wake_intent(text):
                    print(f"   [wake detected: '{text}']")
                    return
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[wake error] {e}")
                time.sleep(0.3)
    def run(self):
        time.sleep(0.5)
        self._speak(f"Good evening, {config.USER_NAME}. Alfred at your service.")
        time.sleep(1.0)
        while True:
            try:
                self._wait_for_wake_word()
                self.sig_state.emit("wake")
                self.sig_detail.emit("Good Evening Alfred")
                play_chime()
                time.sleep(0.6)
                self._speak("Yes, sir?")
                time.sleep(0.2)
                last_activity = time.time()

                while True:
                    self.sig_state.emit("listening")
                    print("■ Listening...")
                    audio = self._record_until_silence()
                    if len(audio) < SAMPLE_RATE * 0.3:
                        if time.time() - last_activity > config.CONVERSATION_TIMEOUT_SEC:
                            self._speak("Very good, sir. I'll be here if you need me.")
                            time.sleep(0.5)
                            self.sig_state.emit("hidden")
                            break
                        continue
                    user_text = self._transcribe(audio)
                    if not user_text:
                        if time.time() - last_activity > config.CONVERSATION_TIMEOUT_SEC:
                            self._speak("Very good, sir. I'll be here if you need me.")
                            time.sleep(0.5)
                            self.sig_state.emit("hidden")
                            break
                        continue
                    last_activity = time.time()
                    print(f"YOU: {user_text}")
                    self.sig_detail.emit(f'"{user_text}"')
                    if is_exit_intent(user_text):
                        self._speak(f"Very good, {config.USER_NAME}. Do try to get some rest. Goodnight.")
                        time.sleep(1.8)
                        self.sig_state.emit("hidden")
                        print("[Alfred] Shutting down. Goodnight, sir.")
                        self.sig_quit.emit()
                        return
                    self.sig_state.emit("thinking")
                    reply = self._ask(user_text)
                    self._speak(reply)
                    time.sleep(0.4)
            except KeyboardInterrupt:
                self.sig_state.emit("hidden")
                break
            except Exception as e:
                print(f"[Error] {e}")
                self.sig_state.emit("error")
                self.sig_detail.emit(str(e))
                time.sleep(1.5)
                self.sig_state.emit("hidden")
# ============================================================
# MAIN
# ============================================================
def main():
    generate_chime()
    app = QApplication([])
    ui = AlfredUI()
    worker = AlfredWorker()
    worker.sig_state.connect(ui.set_state)
    worker.sig_detail.connect(ui.set_detail)
    worker.sig_level.connect(ui.set_level)
    worker.sig_quit.connect(app.quit)
    worker.start()
    try:
        app.exec()
    finally:
        worker.wait(3000)
        print("[main] Alfred stopped.")
if __name__ == "__main__":
    main()
