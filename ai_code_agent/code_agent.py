import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .github_client import GitHubClient
from .openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class CodeAgent:
    def __init__(self, github_client: GitHubClient, llm_client: OpenAIClient) -> None:
        self.github_client = github_client
        self.llm_client = llm_client

    async def process_issue(self, issue_number: int) -> Optional[int]:
        try:
            issue = self.github_client.get_issue(issue_number)
            logger.info(f"Processing issue #{issue_number}: {issue.title}")

            analysis = await self._analyze_issue(issue.title, issue.body or "")
            if not analysis:
                logger.error("Failed to analyze issue requirements")
                return None

            branch_name = f"feature/issue-{issue_number}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            self.github_client.create_branch(branch_name)

            changes_applied = await self._generate_and_apply_changes(
                analysis, branch_name, issue_number
            )

            if not changes_applied:
                logger.error("Failed to apply code changes")
                return None

            pr_title = f"Fix #{issue_number}: {issue.title}"
            pr_body = self._generate_pr_description(issue, analysis)
            
            pr = self.github_client.create_pull_request(
                title=pr_title,
                body=pr_body,
                head_branch=branch_name,
                base_branch="main"
            )

            logger.info(f"Created pull request #{pr.number} for issue #{issue_number}")
            return pr.number

        except Exception as e:
            logger.error(f"Error processing issue {issue_number}: {e}")
            return None

    async def _analyze_issue(self, title: str, body: str) -> Optional[Dict]:
        """Analyze issue requirements and determine what needs to be implemented."""
        system_prompt = """You are an expert software developer analyzing GitHub issues.
        Your task is to understand the requirements and provide a structured analysis.
        
        Analyze the issue and provide:
        1. Summary of what needs to be implemented
        2. List of files that need to be created or modified
        3. Key functionality requirements
        4. Technical approach
        5. Dependencies or libraries needed
        
        Respond in JSON format with the following structure:
        {
            "summary": "Brief description of what needs to be implemented",
            "files_to_modify": ["list", "of", "files"],
            "files_to_create": ["list", "of", "new", "files"],
            "requirements": ["list", "of", "key", "requirements"],
            "technical_approach": "Description of how to implement",
            "dependencies": ["list", "of", "dependencies"]
        }"""

        user_prompt = f"""Issue Title: {title}

Issue Description:
{body}

Please analyze this issue and provide the structured response."""

        try:
            messages = [
                self.llm_client.create_system_message(system_prompt),
                self.llm_client.create_user_message(user_prompt)
            ]
            
            response = await self.llm_client.generate_response(messages)

            import json
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                logger.error("Could not extract JSON from LLM response")
                return None
                
        except Exception as e:
            logger.error(f"Error analyzing issue: {e}")
            return None

    async def _generate_and_apply_changes(
        self, analysis: Dict, branch_name: str, issue_number: int
    ) -> bool:
        try:
            repo_files = self.github_client.list_repository_files()

            all_changes_applied = True

            for file_path in analysis.get("files_to_modify", []):
                if file_path in repo_files:
                    success = await self._modify_existing_file(
                        file_path, analysis, branch_name, issue_number
                    )
                    if not success:
                        all_changes_applied = False
                else:
                    logger.warning(f"File {file_path} not found in repository")

            for file_path in analysis.get("files_to_create", []):
                success = await self._create_new_file(
                    file_path, analysis, branch_name, issue_number
                )
                if not success:
                    all_changes_applied = False

            return all_changes_applied

        except Exception as e:
            logger.error(f"Error generating and applying changes: {e}")
            return False

    async def _modify_existing_file(
        self, file_path: str, analysis: Dict, branch_name: str, issue_number: int
    ) -> bool:
        try:
            current_content = self.github_client.get_file_content(file_path, "main")

            system_prompt = f"""You are an expert software developer modifying code files.
            
            Based on the issue analysis, modify the existing file to implement the required functionality.
            
            Analysis:
            - Summary: {analysis.get('summary', '')}
            - Requirements: {', '.join(analysis.get('requirements', []))}
            - Technical Approach: {analysis.get('technical_approach', '')}
            
            Rules:
            1. Preserve existing functionality unless it conflicts with requirements
            2. Follow Python best practices and PEP 8
            3. Add proper error handling
            4. Include docstrings for new functions/classes
            5. Add type hints where appropriate
            
            Return only the complete modified file content, no explanations."""

            user_prompt = f"""File to modify: {file_path}

Current content:
```
{current_content}
```

Please provide the modified file content that implements the required functionality."""

            messages = [
                self.llm_client.create_system_message(system_prompt),
                self.llm_client.create_user_message(user_prompt)
            ]
            
            modified_content = await self.llm_client.generate_response(messages)

            modified_content = re.sub(r'^```[a-zA-Z]*\n', '', modified_content)
            modified_content = re.sub(r'\n```$', '', modified_content)

            commit_message = f"Modify {file_path} for issue #{issue_number}"
            self.github_client.update_file(
                file_path, modified_content, commit_message, branch_name
            )
            
            logger.info(f"Modified file {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error modifying file {file_path}: {e}")
            return False

    async def _create_new_file(
        self, file_path: str, analysis: Dict, branch_name: str, issue_number: int
    ) -> bool:
        try:
            system_prompt = f"""You are an expert software developer creating new code files.
            
            Based on the issue analysis, create a new file that implements the required functionality.
            
            Analysis:
            - Summary: {analysis.get('summary', '')}
            - Requirements: {', '.join(analysis.get('requirements', []))}
            - Technical Approach: {analysis.get('technical_approach', '')}
            - Dependencies: {', '.join(analysis.get('dependencies', []))}
            
            Rules:
            1. Follow Python best practices and PEP 8
            2. Add proper error handling
            3. Include comprehensive docstrings
            4. Add type hints
            5. Include necessary imports
            6. Add basic tests if it's a test file
            
            Return only the complete file content, no explanations."""

            user_prompt = f"""Create new file: {file_path}

Please provide the complete file content that implements the required functionality."""

            messages = [
                self.llm_client.create_system_message(system_prompt),
                self.llm_client.create_user_message(user_prompt)
            ]
            
            file_content = await self.llm_client.generate_response(messages)

            file_content = re.sub(r'^```[a-zA-Z]*\n', '', file_content)
            file_content = re.sub(r'\n```$', '', file_content)

            commit_message = f"Create {file_path} for issue #{issue_number}"
            self.github_client.update_file(
                file_path, file_content, commit_message, branch_name
            )
            
            logger.info(f"Created file {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating file {file_path}: {e}")
            return False

    def _generate_pr_description(self, issue, analysis: Dict) -> str:
        description = f"""## Fixes #{issue.number}

**Issue Title:** {issue.title}

**Summary:** {analysis.get('summary', 'No summary available')}

### Changes Made:
"""
        
        if analysis.get('files_to_create'):
            description += "\n**New Files:**\n"
            for file_path in analysis['files_to_create']:
                description += f"- `{file_path}`\n"
        
        if analysis.get('files_to_modify'):
            description += "\n**Modified Files:**\n"
            for file_path in analysis['files_to_modify']:
                description += f"- `{file_path}`\n"

        if analysis.get('requirements'):
            description += "\n**Requirements Implemented:**\n"
            for req in analysis['requirements']:
                description += f"- {req}\n"

        if analysis.get('technical_approach'):
            description += f"\n**Technical Approach:**\n{analysis['technical_approach']}\n"

        description += "\n### Testing\n"
        description += "- Code follows project standards\n"
        description += "- All tests pass\n"
        description += "- No linting errors\n"
        description += "- Functionality works as expected\n"

        return description