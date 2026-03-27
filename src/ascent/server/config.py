from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost:5432/ascent"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:4200"]
    debug: bool = False

    model_config = {"env_prefix": "ASCENT_"}


settings = Settings()
