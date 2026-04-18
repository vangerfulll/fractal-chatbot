from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    HOLLIHOP_API_URL: str = "https://api.hollihop.ru/v2/"
    HOLLIHOP_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
