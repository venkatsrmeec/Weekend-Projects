# config.py
# ------------------------------------------------------------
# Fill in your own Groq API key below.
# Get one free at https://console.groq.com/keys
# Never commit this file to git. Add it to .gitignore.
# ------------------------------------------------------------
GROQ_API_KEY = "PASTE_YOUR_GROQ_API_KEY_HERE"
# Speech-to-Text model (Groq cloud Whisper)
WHISPER_MODEL = "whisper-large-v3-turbo"
# LLM model for Alfred's brain (Groq hosted)
LLM_MODEL = "openai/gpt-oss-120b"
# How Alfred addresses the user
USER_NAME = "sir"
# Piper voice model path (relative to project root)
PIPER_VOICE = "voices/en_GB-alan-medium.onnx"
# Time (seconds) Alfred stays awake waiting for follow-ups before sleeping
CONVERSATION_TIMEOUT_SEC = 20