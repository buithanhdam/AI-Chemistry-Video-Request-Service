"""
Formatted Logger for Scraper
- Console + File logging
- Colorized output
- Compatible with LOGGING_CONFIG

Prod mode (PROJECT_ENV=prod): chi ghi ra file, KHONG in ra console/stderr
Dev mode  (PROJECT_ENV=dev) : ghi ra file + in ra console co mau
"""
import dotenv
dotenv.load_dotenv()
import os
import logging
import logging.config
from pathlib import Path
from datetime import datetime
import sys

# =========================
# COLOR FORMATTER
# =========================

class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG":    "\033[36m",  # Cyan
        "INFO":     "\033[32m",  # Green
        "WARNING":  "\033[33m",  # Yellow
        "ERROR":    "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        return f"{color}{super().format(record)}{self.RESET}"


# =========================
# LOGGER SETUP
# =========================

_IS_PROD = os.environ.get("PROJECT_ENV", "prod").lower() == "prod"

_FMT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(funcName)s | %(message)s"
)
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_formatted_logger(
    name: str = "scraper",
    log_dir: Path | None = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """
    Create formatted logger.

    Prod (PROJECT_ENV=prod) → file only, no stdout/stderr output.
    Dev  (PROJECT_ENV=dev)  → file + colorized console.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        return logger  # tranh add handler trung

    # ── File handler (luon ghi, ca prod lan dev) ──────────────────
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    logger.addHandler(file_handler)

    # ── Console handler (chi dev) ─────────────────────────────────
    if not _IS_PROD:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(ColorFormatter(_FMT, datefmt=_DATEFMT))
        logger.addHandler(console_handler)

    logger.debug("Logger initialized")
    logger.debug(f"Log file: {log_file}")
    logger.debug(f"Mode: {'prod (file only)' if _IS_PROD else 'dev (file + console)'}")

    return logger


# =========================
# QUICK TEST
# =========================

if __name__ == "__main__":
    logger = get_formatted_logger("scraper")

    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")