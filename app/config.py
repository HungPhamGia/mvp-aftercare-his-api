from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str

    # Question generation (optional — falls back to a template draft if unset)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Smartbot BFF (optional — BFF returns a stub reply if unset)
    SMARTBOT_URL: str = "https://assistant-stream.vnpt.vn/v1/conversation"
    BOT_ID: str = ""
    SMARTBOT_ACCESS_TOKEN: str = ""
    SMARTBOT_TOKEN_ID: str = ""
    SMARTBOT_TOKEN_KEY: str = ""

    @property
    def smartbot_configured(self) -> bool:
        return bool(self.BOT_ID and self.SMARTBOT_ACCESS_TOKEN
                    and self.SMARTBOT_TOKEN_ID and self.SMARTBOT_TOKEN_KEY)


settings = Settings()
