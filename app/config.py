import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )

    github_app_id: str = Field(..., env="GITHUB_APP_ID")
    github_app_private_key: str = Field(..., env="GITHUB_APP_PRIVATE_KEY")
    github_webhook_secret: str = Field(..., env="GITHUB_WEBHOOK_SECRET")

    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")  
    openai_base_url: str = Field(default="https://openrouter.ai/api/v1/chat/completions", env="OPENAI_BASE_URL")  

    max_iterations: int = Field(default=5, env="MAX_ITERATIONS")
    code_agent_name: str = Field(default="AI Code Agent", env="CODE_AGENT_NAME")
    reviewer_agent_name: str = Field(default="AI Reviewer Agent", env="REVIEWER_AGENT_NAME")

    database_url: str = Field(default="sqlite:///./app.db", env="DATABASE_URL")

    webhook_timeout: int = Field(default=30, env="WEBHOOK_TIMEOUT")
    ci_check_interval: int = Field(default=60, env="CI_CHECK_INTERVAL")
    ci_max_wait_time: int = Field(default=1800, env="CI_MAX_WAIT_TIME")  # 30 minutes

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


    def get_private_key(self) -> str:
        if self.github_app_private_key.startswith("/") or self.github_app_private_key.endswith(".pem"):
            try:
                with open(self.github_app_private_key, "r") as f:
                    return f.read()
            except FileNotFoundError:
                raise ValueError(f"Private key file not found: {self.github_app_private_key}")
        
        return self.github_app_private_key


settings = Settings()
