# Alfred — Local Voice Assistant

A JARVIS-inspired voice assistant with a Batman-themed overlay UI, British butler voice, real-time web search, and dual wake words.

## Features

- Wake phrases: `"Good Evening Alfred"`, `"Hey there Alfred"`, `"Hello Alfred"`, `"Hi Alfred"`
- British butler voice via Piper TTS (`en_GB-alan-medium`)
- Groq Whisper `whisper-large-v3-turbo` for speech-to-text
- Groq-hosted LLM for conversational responses
- Real-time web search via DuckDuckGo
- Desktop application launching
- CPU, memory, and disk status reporting
- Transparent animated overlay with a Batman-inspired sigil
- Voice exit phrases such as `"bye bye"`, `"goodbye"`, `"good night"`, and `"shut down"`

## Project structure

```text
alfred-project/
├── alfred.py              # Main assistant: audio, STT, LLM, tools, conversation loop
├── alfred_ui.py           # PyQt6 animated overlay
├── config.example.py      # Safe configuration template
├── requirements.txt       # Python dependencies
├── .gitignore             # Prevents secrets, environments, models, and generated audio
├── LICENSE
├── README.md
├── voices/                # Piper voice model goes here (ignored by Git)
└── sounds/                # Runtime/generated sound assets (ignored by Git)
```

## Requirements

- Python 3.10+
- Linux (Debian/Ubuntu tested)
- Microphone and speakers
- A Groq API key
- Piper TTS available on your `PATH`
- `aplay` available on your `PATH`

### System packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
  portaudio19-dev ffmpeg alsa-utils \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
  libxcb-render-util0 libxcb-shape0 libgl1
```

## Setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd alfred-project
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your local configuration

Copy the safe template:

```bash
cp config.example.py config.py
```

Then edit `config.py` and add your own Groq API key:

```python
GROQ_API_KEY = "PASTE_YOUR_GROQ_API_KEY_HERE"
```

**Never commit `config.py` or your API key to GitHub.** The repository `.gitignore` already excludes it.

### 5. Download the Piper voice model

```bash
mkdir -p voices
cd voices

wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json

cd ..
```

The voice model files are intentionally excluded from Git because they are large binaries.

### 6. Check required executables

```bash
which piper
which aplay
```

## Run

```bash
python alfred.py
```

Alfred starts by greeting you and then waits for a wake phrase.

Example wake phrases:

- `Good Evening Alfred`
- `Hey there Alfred`
- `Hello Alfred`
- `Hi Alfred`

After the wake phrase, Alfred listens for your request, processes it with the configured Groq model, and speaks the response.

## Exit phrases

The following can end the active session:

- `bye bye`
- `bye-bye`
- `goodbye`
- `good night`
- `goodnight`
- `shut down`
- `shutdown`
- `stand down`
- `that's all`
- `exit alfred`
- `quit alfred`

Short utterances containing `thank you` or `thanks` can also trigger the soft-exit behavior.

## Configuration

The main settings are in `config.py`:

| Setting | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Your Groq API key |
| `WHISPER_MODEL` | Speech-to-text model |
| `LLM_MODEL` | Alfred's language model |
| `USER_NAME` | Name Alfred uses when addressing you |
| `PIPER_VOICE` | Relative path to the Piper voice model |
| `CONVERSATION_TIMEOUT_SEC` | Seconds before Alfred returns to sleep |

The tracked `config.example.py` contains safe placeholder values. Your real `config.py` stays local.

## Tuning

| Setting | File / function | Purpose |
| --- | --- | --- |
| `PIPER_LENGTH_SCALE` | `alfred.py` | Controls Piper speech speed |
| `silence_seconds` | `_record_until_silence()` | Controls how long Alfred waits for silence |
| `start_threshold` | `_record_until_silence()` | Microphone speech-start sensitivity |
| `keep_threshold` | `_record_until_silence()` | Microphone speech continuation sensitivity |
| `WAKE_PHRASES` | `alfred.py` | Wake phrases Alfred recognizes |
| `STRONG_EXIT_PHRASES` | `alfred.py` | Immediate exit phrases |
| `SOFT_EXIT_PHRASES` | `alfred.py` | Short polite exit phrases |
| `CONVERSATION_TIMEOUT_SEC` | `config.py` | Time before Alfred goes back to sleep |

## Security notes

- Keep your Groq API key in local `config.py`.
- Do not commit `config.py` to GitHub.
- Do not commit Piper voice binaries or generated audio.
- Audio is sent to Groq for transcription, so avoid using the assistant for sensitive/private recordings if that is a concern.
- Groq usage may be subject to account or service rate limits.

## GitHub checklist

Before pushing:

```bash
git status
git add .
git status
git commit -m "Initial Alfred assistant project"
git push -u origin main
```

Confirm that `config.py` does **not** appear in `git status` before committing.

## License

MIT.
