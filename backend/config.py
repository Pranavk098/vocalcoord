# backend/config.py
import os

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("1", "true", "yes")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

MAX_WEBHOOK_BODY_BYTES = 64_000
SESSION_TTL_SECONDS = 3600
REPLY_CACHE_TTL_SECONDS = 3600
QUEUE_TTL_SECONDS = 1800

SYNTHESIS_MODEL = os.getenv("SYNTHESIS_MODEL", "claude-haiku-4-5-20251001")
SYNTHESIS_TIMEOUT_SECONDS = 4.0
SYNTHESIS_MAX_TOKENS = 120
# Retry budget around LLM synthesis (template-first path never touches this).
# Total LLM attempts = 1 (synthesize) + SYNTHESIS_MAX_RETRIES (synthesize_retry).
SYNTHESIS_MAX_RETRIES = int(os.getenv("SYNTHESIS_MAX_RETRIES", "1"))

# HYBRID ownership flags (see docs/adr/0005-hybrid-owned-stt-llm.md).
#   PROVIDER_LLM=local     -> Ollama qwen2.5:3b first, Anthropic fallback on failure.
#   PROVIDER_LLM=anthropic -> Anthropic directly (default; preserves CI/demo behavior).
PROVIDER_LLM = os.getenv("PROVIDER_LLM", "anthropic").lower()
#   PROVIDER_TTS=elevenlabs -> ElevenLabs Conversational AI (default; unchanged path).
#   PROVIDER_TTS=piper      -> owned Piper TTS (endpoint stub; ElevenLabs path intact).
PROVIDER_TTS = os.getenv("PROVIDER_TTS", "elevenlabs").lower()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "15.0"))

# Owned STT path: Faster-Whisper model + 16 kHz contract.
STT_MODEL = os.getenv("STT_MODEL", "small.en")
STT_SAMPLE_RATE = 16000
STT_MAX_WAV_BYTES = int(os.getenv("STT_MAX_WAV_BYTES", str(5 * 1024 * 1024)))
