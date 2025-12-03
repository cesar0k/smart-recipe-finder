from app.core.config import Settings

class TestSettings(Settings):
    DB_ROOT_PASSWORD: str = "root_password"
    TEST_DB_NAME: str = "recipes_test_db"
    
    @property
    def SYNC_TEST_DATABASE_ADMIN_URL(self) -> str:
        return (
            f"mysql+pymysql://root:{self.DB_ROOT_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_INTERNAL_PORT}/{self.TEST_DB_NAME}"
        )
    @property
    def ASYNC_TEST_DATABASE_ADMIN_URL(self):
        return (
            f"mysql+asyncmy://root:{self.DB_ROOT_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_INTERNAL_PORT}/{self.TEST_DB_NAME}"
        )
        
test_settings = TestSettings()