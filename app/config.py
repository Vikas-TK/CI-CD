import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


class BaseConfig:
    """Base configuration settings shared across all environments."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-fallback-secret-key-replace-in-production-12345")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get("PERMANENT_SESSION_LIFETIME", 3600))
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # CSRF settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    
    db_user = os.environ.get("DB_USER", "hms_user")
    db_pass = os.environ.get("DB_PASSWORD", "hms_password")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "3306")
    db_name = os.environ.get("DB_NAME", "hospital_management_db")
    
    # Check if a direct DATABASE_URL is provided, else assemble MySQL URL or fallback to SQLite for local ease
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    )


class TestingConfig(BaseConfig):
    """Testing configuration using in-memory or isolated SQLite for lightning-fast pytest runs."""
    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False  # Disable CSRF in tests for simpler form testing
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
    SERVER_NAME = "localhost.localdomain"


class StagingConfig(BaseConfig):
    """Staging environment configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    
    db_user = os.environ.get("DB_USER", "hms_user")
    db_pass = os.environ.get("DB_PASSWORD", "")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "3306")
    db_name = os.environ.get("DB_NAME", "hospital_staging_db")
    
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    )


class ProductionConfig(BaseConfig):
    """Production environment configuration with hardened security settings."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    
    db_user = os.environ.get("DB_USER")
    db_pass = os.environ.get("DB_PASSWORD")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "3306")
    db_name = os.environ.get("DB_NAME", "hospital_management_db")
    
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    )


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "staging": StagingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
