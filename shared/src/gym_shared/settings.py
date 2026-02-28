from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://gym:gympass@localhost:5432/gymdb",
        description="Async SQLAlchemy database URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # MinIO / S3
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket_clips: str = Field(default="gym-clips")
    minio_secure: bool = Field(default=False)

    # Anthropic
    anthropic_api_key: str = Field(default="")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")

    # Guidance
    guidance_rate_limit_seconds: int = Field(default=30)
    llm_model: str = Field(default="claude-sonnet-4-6")
    llm_max_tokens: int = Field(default=1024)

    # Ingestion
    camera_ids: str = Field(default="cam-01")
    ingest_fps: int = Field(default=15)
    ingest_jpeg_quality: int = Field(default=85)
    frame_buffer_size: int = Field(default=225)

    # Perception
    yolo_model: str = Field(default="yolo11n-pose.pt")
    reid_model_path: str = Field(default="services/perception/models/osnet_x1_0.pth")

    # Logging
    log_format: str = Field(default="console")
    log_level: str = Field(default="INFO")

    # Environment
    environment: str = Field(default="development")

    @property
    def camera_id_list(self) -> list[str]:
        return [c.strip() for c in self.camera_ids.split(",") if c.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Module-level singleton — import and use directly
settings = Settings()
