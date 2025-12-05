from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field, model_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8")
    
    APP_PORT: int = 8000
    
    DB_ROOT_PASSWORD: str = ""
    DB_NAME: str = ""
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_HOST: str = "db"
    DB_INTERNAL_PORT: int = 3306
    
    CHROMA_HOST: str = "chroma"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = ""
    
    HF_TOKEN: str = ""
    
    @model_validator(mode="after")
    def check_required_field_are_set(self):
        missing_fields = []
        if not self.DB_ROOT_PASSWORD:
            missing_fields.append("DB_ROOT_PASSWORD")
        if not self.DB_NAME:
            missing_fields.append("DB_NAME")
        if not self.DB_USER:
            missing_fields.append("DB_USER")
        if not self.DB_PASSWORD:
            missing_fields.append("DB_PASSWORD")
        if not self.CHROMA_COLLECTION_NAME:
            missing_fields.append("CHROMA_COLLECTION_NAME")
    
        if missing_fields:
            raise ValueError(f"Missing required environment variables: {','.join(missing_fields)}")
        
        return self
            
    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return (
            f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_INTERNAL_PORT}/{self.DB_NAME}"
        )
        
    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_INTERNAL_PORT}/{self.DB_NAME}"
        )
        
settings = Settings()