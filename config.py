"""
config.py — MindOS central configuration.
All paths, model names, and constants are defined here.
No other file should hardcode paths or model names.
"""
import os

# ── Paths ───────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Vault directories — the project root IS the Obsidian vault
VAULT_DIR      = BASE_DIR
TASKS_FILE     = os.path.join(VAULT_DIR, "02_Tasks",     "tasks.md")
IDEAS_FILE     = os.path.join(VAULT_DIR, "05_Ideas",     "ideas.md")
MEMORY_FILE    = os.path.join(VAULT_DIR, "07_Memory",    "memory.md")
REMINDERS_FILE = os.path.join(VAULT_DIR, "08_Reminders", "reminders.md")
GEMINI_MEMORY_FILE = os.path.join(VAULT_DIR, "10_Gemini_Memory", "gemini_memory.md")

# ── API Keys ─────────────────────────────────────────────────────────────────────
# Set your Gemini API key as an environment variable:
#   Windows (PowerShell): $env:GEMINI_API_KEY = "your_key_here"
#   Linux/macOS:          export GEMINI_API_KEY="your_key_here"
# Alternatively, create a .env file (see .env.example) — it is gitignored.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ChromaDB persistent store
CHROMA_DIR   = os.path.join(BASE_DIR, "chroma_db")
MTIMES_FILE  = os.path.join(CHROMA_DIR, "mtimes.json")

# ── Ollama ───────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"

# Models confirmed installed and working on this machine:
#   gemma:2b     — fastest at ~12s, used as primary
#   gemma4:e2b   — 38s, fallback
#   qwen3:4b     — very slow (60s+ timeout), not used
# Neither Gemma model natively supports Ollama tool-calling schema,
# so ai_engine.py uses prompt-engineering based tool extraction instead.
OLLAMA_MODEL    = "gemma:2b"    # primary
OLLAMA_FALLBACK = "gemma4:e2b"  # fallback

# ── AI behaviour ─────────────────────────────────────────────────────────────────
MAX_HISTORY_TURNS = 10   # Rolling context window (N user+assistant pairs)
RAG_TOP_K         = 5    # ChromaDB results injected into each prompt
