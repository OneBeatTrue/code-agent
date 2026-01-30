"""Configuration management for AI Code Agent."""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Configuration settings for the AI Code Agent system."""

    # GitHub Configuration
    github_token: str = Field(..., env="GITHUB_TOKEN")
    github_repo_owner: str = Field(..., env="GITHUB_REPO_OWNER")
    github_repo_name: str = Field(..., env="GITHUB_REPO_NAME")

    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://openrouter.ai/api/v1/chat/completions", env="OPENAI_BASE_URL")  


    # Agent Configuration
    max_iterations: int = Field(default=5, env="MAX_ITERATIONS")
    code_agent_name: str = Field(default="AI Code Agent", env="CODE_AGENT_NAME")
    reviewer_agent_name: str = Field(
        default="AI Reviewer Agent", env="REVIEWER_AGENT_NAME"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT",
    )

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def github_repo_url(self) -> str:
        """Get the full GitHub repository URL."""
        return f"https://github.com/{self.github_repo_owner}/{self.github_repo_name}"

# Global configuration instance
config = Config()