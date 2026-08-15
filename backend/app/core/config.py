from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://ludora:ludorapassword@localhost:5432/ludoradb"
    
    class Config:
        env_file = ".env"

settings = Settings()
