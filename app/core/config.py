from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field, model_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    APP_PORT: int = 8000
    
    MYSQL_ROOT_PASSWORD: str = ""
    MYSQL_DATABASE: str = ""
    MYSQL_USER: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_HOST: str = "db"
    MYSQL_PORT: int = 3306
    
    CHROMA_HOST: str = "chroma"
    CHROMA_PORT: int = 3306
    
    @model_validator(mode="after")
    def check_required_field_are_set(self):
        missing_fields = []
        if not self.MYSQL_ROOT_PASSWORD:
            missing_fields.append("MYSQL_ROOT_PASSWORD")
        if not self.MYSQL_DATABASE:
            missing_fields.append("MYSQL_DATABASE")
        if not self.MYSQL_USER:
            missing_fields.append("MYSQL_USER")
        if not self.MYSQL_PASSWORD:
            missing_fields.append("MYSQL_PASSWORD")
    
        if missing_fields:
            raise ValueError(f"Missing required environment variables: {','.join(missing_fields)}")
        
        return self
            
    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@"
            f"{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )
        
    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@"
            f"{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )
        
settings = Settings()