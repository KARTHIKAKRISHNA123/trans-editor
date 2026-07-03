import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY: str | None = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY: str | None = os.environ.get("OPENROUTER_API_KEY")


# GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY")
# GROQ_API_KEY:   str | None = os.environ.get("GROQ_API_KEY")


GEMINI_MODEL: str = "gemini/gemini-2.5-flash"
GROQ_MODEL: str = "groq/llama-3.3-70b-versatile"
OPENROUTER_JUDGE_MODEL: str = "openrouter/openai/gpt-oss-120b:free"



TEMPERATURE: float = 0.1

MAX_TOKENS: int = 1024

SOURCE_LANGUAGE: str = "English"

TARGET_LANGUAGE: str = "Tamil"



MIN_TEXT_LENGTH: int = 3

OUTPUT_SUFFIX: str = "_tamil"
QUALITY_THRESHOLD: int = 75
