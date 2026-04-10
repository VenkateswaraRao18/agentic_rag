from pathlib import Path

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env into os.environ so boto3 sees AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.
load_dotenv(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    app_name: str = "Ops Copilot"
    environment: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8000

    vector_index_path: str = "data/index/faiss.index"
    metadata_path: str = "data/index/metadata.json"
    docs_dir: str = "data/docs"
    # When false (default), FAISS always loads <repo>/data/index/* — ignores VECTOR_INDEX_PATH
    # in .env so a bad absolute path cannot point at a stale 1-vector index.
    use_env_vector_index_paths: bool = False

    aws_region: str = "us-east-1"
    s3_docs_bucket: str = "ops-copilot-docs"
    s3_artifacts_bucket: str = "ops-copilot-artifacts"

    # Comma-separated origins for the Next.js app (and local tools).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # AWS Bedrock — uses default credential chain (env, profile, IAM role). Never commit keys.
    use_bedrock: bool = True
    # Model IDs: https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html
    # Gemma 3 (us-east-1): google.gemma-3-12b-it ; Titan: amazon.titan-text-express-v1 ;
    # Llama / Mistral: meta.llama3-8b-instruct-v1:0 , mistral.mistral-7b-instruct-v0:2
    bedrock_model_id: str = "google.gemma-3-12b-it"
    # auto | anthropic | amazon_titan | meta_llama | mistral | google_gemma
    bedrock_provider: str = "auto"
    bedrock_max_tokens: int = 2048
    bedrock_temperature: float = 0.3
    bedrock_top_p: float = 0.9

    # DocuWeave PDF chunking (tiktoken model name for token counting).
    docuweave_max_tokens: int = 800
    docuweave_token_model: str = "gpt-4"

    default_top_k: int = 4
    max_context_chunks: int = 6
    confidence_threshold: float = 0.35
    # Ticket/tool answer style:
    # - deterministic: fastest, no LLM rewrite for ticket_lookup tool outputs
    # - llm_polish: keep tool facts authoritative, but let LLM present the final wording
    ticket_answer_mode: str = "llm_polish"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_paths_from_project_root(self) -> "Settings":
        """
        Interpret vector index, metadata, and docs paths relative to the repo root
        (the directory that contains the `app` package), not the process cwd.
        Otherwise `uvicorn` started from another folder loads the wrong or empty index.
        """
        for name in ("vector_index_path", "metadata_path", "docs_dir"):
            raw = getattr(self, name)
            p = Path(raw)
            if not p.is_absolute():
                setattr(self, name, str(_PROJECT_ROOT / p))
        return self


settings = Settings()


def _default_cors_origins() -> list[str]:
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


def get_cors_allow_origins() -> list[str]:
    """
    Origins for CORSMiddleware.
    Non-production: allow all origins (convenient for local dev).
    Production: use CORS_ORIGINS (comma-separated); ``*`` entries are ignored.
    """
    if settings.environment.lower() != "production":
        return ["*"]
    raw = (settings.cors_origins or "").strip()
    if raw == "*":
        return _default_cors_origins()
    parts = [x.strip() for x in raw.split(",") if x.strip() and x.strip() != "*"]
    if parts:
        return parts
    return _default_cors_origins()
