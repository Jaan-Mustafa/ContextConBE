from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    crustdata_api_key: str
    crustdata_base_url: str = "https://api.crustdata.com"
    llm_base_url: str = "https://clear-llm-proxy.internal.cleartax.co/v1"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    cors_origins: str = "http://localhost:5173"
    app_env: str = "development"

    model_config = {"env_file": ".env"}


settings = Settings()
