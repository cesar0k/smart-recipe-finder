from app.core.config import Settings

class TestSettings(Settings):
    DB_ROOT_PASSWORD: str = "root_password"
    TEST_DB_NAME: str = "recipes_test_db"
    CHROMA_COLLECTION_NAME: str = "recipes_test"
    
    @property
    def SYNC_TEST_DATABASE_ADMIN_URL(self) -> str:
        if self.DB_TYPE == "postgres":
            return (
                f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@"
                f"{self.DB_HOST}:{self.DB_INTERNAL_PORT}/{self.TEST_DB_NAME}"
            )
        return (
            f"mysql+pymysql://root:{self.DB_ROOT_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_INTERNAL_PORT}/{self.TEST_DB_NAME}"
        )
        
    @property
    def ASYNC_TEST_DATABASE_ADMIN_URL(self) -> str:
        if self.DB_TYPE == "postgres":
            return (
                f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@"
                f"{self.DB_HOST}:{self.DB_INTERNAL_PORT}/{self.TEST_DB_NAME}"
            )
        return (
            f"mysql+asyncmy://root:{self.DB_ROOT_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_INTERNAL_PORT}/{self.TEST_DB_NAME}"
        )
        
test_settings = TestSettings()