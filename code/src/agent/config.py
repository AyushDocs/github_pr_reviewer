import os
import threading
from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings

load_dotenv()

AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "google/gemma-2-2b-it")
AI_EMBEDDING_MODEL = os.getenv("AI_EMBEDDING_MODEL", "nvidia/nv-embed-v1")
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.2"))
AI_TOP_P = float(os.getenv("AI_TOP_P", "0.7"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1024"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not AI_API_KEY:
    raise ValueError("AI_API_KEY not set")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not set")

AI_FALLBACK_API_KEY = os.getenv("AI_FALLBACK_API_KEY")
AI_FALLBACK_MODEL = os.getenv("AI_FALLBACK_MODEL", "google/gemma-2-2b-it")

MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM", "5"))
MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "15000"))

NVIDIA_PRICE_PER_1M_INPUT = 0.10
NVIDIA_PRICE_PER_1M_OUTPUT = 0.10

llm_semaphore = threading.Semaphore(MAX_CONCURRENT_LLM)

llm = ChatNVIDIA(
    model=AI_MODEL,
    api_key=AI_API_KEY,
    temperature=AI_TEMPERATURE,
    top_p=AI_TOP_P,
    max_completion_tokens=AI_MAX_TOKENS,
)

fallback_llm = ChatNVIDIA(
    model=AI_FALLBACK_MODEL,
    api_key=AI_FALLBACK_API_KEY,
    temperature=AI_TEMPERATURE,
    top_p=AI_TOP_P,
    max_completion_tokens=AI_MAX_TOKENS,
) if AI_FALLBACK_API_KEY else None

embeddings = NVIDIAEmbeddings(
    model=AI_EMBEDDING_MODEL,
    api_key=AI_API_KEY,
)

_token_lock = threading.Lock()
_token_accumulator = {"prompt": 0, "completion": 0}


def record_tokens(prompt_tokens: int, completion_tokens: int):
    with _token_lock:
        _token_accumulator["prompt"] += prompt_tokens
        _token_accumulator["completion"] += completion_tokens


def drain_tokens():
    with _token_lock:
        val = dict(_token_accumulator)
        _token_accumulator["prompt"] = 0
        _token_accumulator["completion"] = 0
    return val


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens / 1_000_000 * NVIDIA_PRICE_PER_1M_INPUT
        + completion_tokens / 1_000_000 * NVIDIA_PRICE_PER_1M_OUTPUT
    )
