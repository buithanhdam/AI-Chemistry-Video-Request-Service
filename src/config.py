from pathlib import Path

from pydantic_settings import BaseSettings

from src.logger import get_formatted_logger

logger = get_formatted_logger("config")


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    MAX_RETRIES: int = 3
    TIMEOUT_SECONDS: int = 30
    OUTPUT_DIR: str = "outputs"
    LOG_DIR: str = "logs"
    LOG_LEVEL: str = "INFO"
    PROJECT_ENV: str = "dev"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def output_path(self) -> Path:
        return Path(self.OUTPUT_DIR).resolve()

    @property
    def log_path(self) -> Path:
        return Path(self.LOG_DIR).resolve()

    def ensure_dirs(self) -> None:
        """Tạo các thư mục runtime (outputs/, logs/) nếu chưa tồn tại."""
        for name, path in (("outputs", self.output_path), ("logs", self.log_path)):
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Directory ready: {path}")
            except OSError as exc:
                logger.error(f"Cannot create {name} dir {path}: {exc}")
                raise


settings = Settings()
settings.ensure_dirs()