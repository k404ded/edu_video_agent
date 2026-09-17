"""
Central configuration for the Educational Video Script & Storyboard Generator.

Loads settings from environment variables (via a local .env file if present).
Keep all tunables here so nothing is hardcoded deep inside agent modules.
"""
import os
from dotenv import load_dotenv

load_dotenv()

def get_api_key() -> str:
    """Dynamically resolves GEMINI_API_KEY from environment or Streamlit Cloud secrets."""
    val = os.getenv("GEMINI_API_KEY", "")
    if not val:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                val = str(st.secrets["GEMINI_API_KEY"]).strip().strip('"').strip("'")
        except Exception:
            pass
    return val

def _get_secret(key: str, default: str = "") -> str:
    val = os.getenv(key, "")
    if not val:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and key in st.secrets:
                val = str(st.secrets[key]).strip().strip('"').strip("'")
        except Exception:
            pass
    return val or default

# --- LLM configuration -------------------------------------------------
GEMINI_API_KEY = get_api_key()
MODEL_NAME = _get_secret("MODEL_NAME", "gemini-3.5-flash-lite")
MAX_TOKENS_PER_CALL = int(os.getenv("MAX_TOKENS_PER_CALL", "4096"))
CONCURRENT_WORKERS = int(os.getenv("CONCURRENT_WORKERS", "2"))

# --- Pipeline configuration ---------------------------------------------
# Words-per-minute assumption used to estimate voice-over duration.
NARRATION_WPM = 140

# Max characters of a single section sent to the LLM in one call.
# Extremely long slides/pages get truncated with a flag rather than
# silently dropped or blown past context limits.
MAX_SECTION_CHARS = 6000

SUPPORTED_EXTENSIONS = {".pptx", ".pdf", ".txt"}

# --- Media Generation configuration ------------------------------------
# Neural voice for edge-tts (e.g. en-US-ChristopherNeural, en-US-JennyNeural, en-US-GuyNeural)
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")
MEDIA_OUTPUT_DIR = os.getenv("MEDIA_OUTPUT_DIR", "output/generated")
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1920"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1080"))
