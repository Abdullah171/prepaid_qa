def get_stc_minimax_client() -> OpenAI:
    """MiniMax-M2.7 served from STC's internal, self-hosted vLLM endpoint.

    It exposes an OpenAI-compatible /v1 API and needs no API key (a placeholder
    is sent). The endpoint uses an internal corp TLS cert that isn't in the
    public trust store (curl needs -k), so SSL verification is disabled here too.
    """
    endpoint = (os.getenv("STC_MINIMAX_ENDPOINT") or DEFAULT_STC_MINIMAX_ENDPOINT).strip()
    # Accept either the base (…/v1) or the full …/v1/chat/completions URL; the
    # OpenAI client appends /chat/completions itself, so strip it if present.
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        endpoint = endpoint[: -len("/chat/completions")]
    api_key = os.getenv("STC_MINIMAX_API_KEY") or "not-needed"
    return OpenAI(base_url=endpoint, api_key=api_key, http_client=httpx.Client(verify=False))




from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()