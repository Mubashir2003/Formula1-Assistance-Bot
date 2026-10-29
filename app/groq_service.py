import os
from groq import AsyncGroq

_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    """Create the Groq client lazily so startup can provide a useful config error."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Add it to your .env file and restart the server."
            )
        _client = AsyncGroq(api_key=api_key)
    return _client
