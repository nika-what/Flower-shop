from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ensure `.env` is loaded from the `Backend/` directory regardless of
    # where uvicorn is started from (current working directory).
    _env_path = Path(__file__).resolve().parents[2] / '.env'
    model_config = SettingsConfigDict(env_file=str(_env_path), env_file_encoding='utf-8', extra='ignore')

    PROJECT_NAME: str = 'Florist Shop API'
    API_V1_STR: str = '/api/v1'

    POSTGRES_USER: str = 'postgres'
    POSTGRES_PASSWORD: str = 'postgres'
    POSTGRES_DB: str = 'florist'
    POSTGRES_HOST: str = 'db'
    POSTGRES_PORT: int = 5432

    DATABASE_URL: str | None = None

    SECRET_KEY: str = Field(default='change-me-super-secret-key', min_length=16)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = 'HS256'

    BACKEND_CORS_ORIGINS: list[str] = [
        'http://localhost:3000',
        'http://localhost:5173',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:5173',
    ]

    REDIS_URL: str = 'redis://redis:6379/0'
    RATE_LIMIT: str = '100/minute'

    FIRST_SUPERUSER_EMAIL: str = 'admin@example.com'
    FIRST_SUPERUSER_PASSWORD: str = 'admin12345'

    # AI bouquet images
    # openai — только OpenAI Images (DALL·E), нужен OPENAI_API_KEY
    # gigachat — GigaChat уточняет промпт + генерация картинок через встроенный text2image (Kandinsky), нужны GIGACHAT_*; OpenAI не используется
    AI_IMAGE_PROVIDER: str = 'openai'
    OPENAI_API_KEY: str | None = None
    OPENAI_IMAGE_MODEL: str = 'dall-e-3'

    # GigaChat API (Сбер): в Studio → Настройки API скопируйте «Ключ авторизации»
    # (это строка для заголовка Authorization: Basic …) или задайте пару CLIENT_ID + CLIENT_SECRET ниже.
    GIGACHAT_AUTHORIZATION_KEY: str | None = None
    GIGACHAT_CLIENT_ID: str | None = None
    GIGACHAT_CLIENT_SECRET: str | None = None
    GIGACHAT_SCOPE: str = 'GIGACHAT_API_PERS'
    # Для text2image (Kandinsky) в личном кабинете может понадобиться модель вроде GigaChat-Pro — см. developers.sber.ru
    GIGACHAT_MODEL: str = 'GigaChat'
    GIGACHAT_OAUTH_URL: str = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
    GIGACHAT_API_URL: str = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'
    # На некоторых ПК сертификат Сбера не доверяется — можно временно выключить проверку SSL (только для отладки)
    GIGACHAT_SSL_VERIFY: bool = True

    AI_IMAGES_COUNT: int = 3
    AI_IMAGES_TTL_HOURS: int = 24
    AI_IMAGES_RATE_LIMIT_PER_USER: str = '5/day'

    # Email codes (email verification & password reset)
    EMAIL_CODE_EXPIRE_MINUTES: int = 15
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = 'no-reply@florist.local'

    # If SMTP isn't configured, backend will include the code in response
    # for local/dev testing (so frontend can still proceed).
    EMAIL_DEBUG_RETURN_CODE: bool = False

    # Геокодер Яндекса (https://developer.tech.yandex.ru/) — если задан, адрес проверяется через него;
    # иначе используется публичный Nominatim (OpenStreetMap), с фильтром по Новосибирску.
    YANDEX_GEOCODER_API_KEY: str | None = None

    # Which SMTP provider to use (when generic SMTP_* vars aren't set).
    # Supported: gmail, yandex, mailru
    EMAIL_SMTP_PROVIDER: str = 'gmail'

    SMTP_GMAIL_HOST: str = 'smtp.gmail.com'
    SMTP_GMAIL_PORT: int = 587
    SMTP_GMAIL_USER: str | None = None
    SMTP_GMAIL_PASSWORD: str | None = None
    SMTP_GMAIL_FROM: str = 'no-reply@florist.local'

    SMTP_YANDEX_HOST: str = 'smtp.yandex.ru'
    SMTP_YANDEX_PORT: int = 587
    SMTP_YANDEX_USER: str | None = None
    SMTP_YANDEX_PASSWORD: str | None = None
    SMTP_YANDEX_FROM: str = 'no-reply@florist.local'

    SMTP_MAILRU_HOST: str = 'smtp.mail.ru'
    SMTP_MAILRU_PORT: int = 587
    SMTP_MAILRU_USER: str | None = None
    SMTP_MAILRU_PASSWORD: str | None = None
    SMTP_MAILRU_FROM: str = 'no-reply@florist.local'

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL.strip()
            # Важно: sqlite с относительным путём привязать к каталогу Backend/, иначе при запуске
            # uvicorn из другой папки создаётся второй florist.db — JWT выдан по одной БД,
            # а /users/me и /ai/* читают другую → 401 «Could not validate credentials».
            if url.startswith('sqlite+aiosqlite:///'):
                tail = url.split('sqlite+aiosqlite:///', 1)[1].lstrip('/')
                if tail.startswith('./'):
                    tail = tail[2:]
                candidate = Path(tail)
                if candidate.is_absolute():
                    return url
                backend_root = Path(__file__).resolve().parents[2]
                abs_path = (backend_root / tail).resolve()
                return f'sqlite+aiosqlite:///{abs_path.as_posix()}'
            return url
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        url = self.async_database_url
        if url.startswith('postgresql+psycopg://'):
            return url
        if url.startswith('sqlite+aiosqlite://'):
            return url.replace('sqlite+aiosqlite://', 'sqlite://')
        return url.replace('postgresql+asyncpg://', 'postgresql+psycopg://')


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
