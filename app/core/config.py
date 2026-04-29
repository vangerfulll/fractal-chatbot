from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    MOCK_EXTERNAL_APIS: bool = True

    JIVO_API_URL: str = "https://bot.jivosite.com"
    JIVO_PROVIDER_ID: str = ""
    JIVO_BOT_TOKEN: str = ""

    HOLLIHOP_DOMAIN: str = ""
    HOLLIHOP_API_URL: str = "https://api.hollihop.ru/v2/"
    HOLLIHOP_API_KEY: str = ""
    RASA_URL: str = "http://localhost:5005"
    REDIS_URL: str = "redis://localhost:6379/0"

    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "bot@example.com"
    ADMIN_EMAIL: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
