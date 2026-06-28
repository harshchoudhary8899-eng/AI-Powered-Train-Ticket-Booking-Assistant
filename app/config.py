import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def normalize_database_url(url: str) -> str:
    if url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+pymysql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'train_booking.db'}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TICKET_FOLDER = os.environ.get("TICKET_FOLDER", str(BASE_DIR / "tickets"))
    AUTO_INIT_DB = os.environ.get("AUTO_INIT_DB", "true").lower() in {"1", "true", "yes", "on"}

