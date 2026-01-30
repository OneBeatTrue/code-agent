import os
import pytest
from unittest.mock import patch

from ai_code_agent.config import Config


class TestConfig:
    def test_config_initialization_with_env_vars(self):
        with patch.dict(os.environ, {
            'GITHUB_TOKEN': 'test_token',
            'GITHUB_REPO_OWNER': 'test_owner',
            'GITHUB_REPO_NAME': 'test_repo',
            'OPENAI_API_KEY': 'test_openai_key',
        }):
            config = Config()
            assert config.github_token == 'test_token'
            assert config.github_repo_owner == 'test_owner'
            assert config.github_repo_name == 'test_repo'
            assert config.openai_api_key == 'test_openai_key'

    def test_config_defaults(self):
        with patch.dict(os.environ, {
            'GITHUB_TOKEN': 'test_token',
            'GITHUB_REPO_OWNER': 'test_owner',
            'GITHUB_REPO_NAME': 'test_repo',
            'OPENAI_API_KEY': 'test_openai_key',
        }):
            config = Config()
            assert config.openai_model == 'gpt-4o-mini'
            assert config.max_iterations == 5
            assert config.code_agent_name == 'AI Code Agent'
            assert config.log_level == 'INFO'

    def test_github_repo_url_property(self):
        with patch.dict(os.environ, {
            'GITHUB_TOKEN': 'test_token',
            'GITHUB_REPO_OWNER': 'testowner',
            'GITHUB_REPO_NAME': 'testrepo',
            'OPENAI_API_KEY': 'test_openai_key',
        }):
            config = Config()
            expected_url = 'https://github.com/testowner/testrepo'
            assert config.github_repo_url == expected_url

    def test_missing_required_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception): 
                Config()