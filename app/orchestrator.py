import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .database import db_manager, IssueIteration, IterationStatus
from .github_client import get_github_client
from .github_app.auth import github_app_auth
from .config import settings
from ai_code_agent.code_agent import CodeAgent
from ai_code_agent.reviewer_agent import ReviewerAgent
from ai_code_agent.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class SDLCOrchestrator:
    def __init__(self):
        self.llm_client = OpenAIClient(
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_base_url=settings.openai_base_url
        )
    
    async def start_issue_cycle(
        self,
        repo_full_name: str,
        issue_number: int,
        installation_id: int
    ) -> Optional[IssueIteration]:
        try:
            logger.info(f"Starting SDLC cycle for {repo_full_name}#{issue_number}")
            
            existing_iteration = db_manager.get_active_iteration(repo_full_name, issue_number)
            if existing_iteration:
                logger.info(f"Active iteration already exists for issue #{issue_number} (ID: {existing_iteration.id})")
                return existing_iteration
            
            owner, repo = repo_full_name.split("/")
            
            async with await get_github_client(installation_id) as github:
                issue_data = await github.get_issue(owner, repo, issue_number)
            
            iteration = db_manager.create_iteration(
                repo_full_name=repo_full_name,
                issue_number=issue_number,
                installation_id=installation_id,
                issue_title=issue_data.get("title"),
                issue_body=issue_data.get("body"),
                max_iterations=settings.max_iterations
            )
            
            await self._run_code_iteration(iteration)
            
            return iteration
            
        except Exception as e:
            logger.error(f"Failed to start issue cycle: {e}", exc_info=True)
            return None
    
    async def restart_issue_cycle(
        self,
        repo_full_name: str,
        issue_number: int,
        installation_id: int
    ) -> Optional[IssueIteration]:
        try:
            logger.info(f"Restarting SDLC cycle for {repo_full_name}#{issue_number}")
            
            existing_iteration = db_manager.get_active_iteration(repo_full_name, issue_number)
            if existing_iteration:
                logger.info(f"Marking existing iteration {existing_iteration.id} as failed to restart")
                db_manager.complete_iteration(existing_iteration.id, IterationStatus.FAILED)
            
            owner, repo = repo_full_name.split("/")
            
            async with await get_github_client(installation_id) as github:
                issue_data = await github.get_issue(owner, repo, issue_number)
            
            iteration = db_manager.create_iteration(
                repo_full_name=repo_full_name,
                issue_number=issue_number,
                installation_id=installation_id,
                issue_title=issue_data.get("title"),
                issue_body=issue_data.get("body"),
                max_iterations=settings.max_iterations
            )
            
            await self._run_code_iteration(iteration)
            
            return iteration
            
        except Exception as e:
            logger.error(f"Failed to restart issue cycle: {e}", exc_info=True)
            return None
    
    async def _run_code_iteration(self, iteration: IssueIteration) -> bool:
        try:
            logger.info(f"Running code iteration {iteration.current_iteration + 1} for {iteration.repo_full_name}#{iteration.issue_number}")
            
            iteration = db_manager.increment_iteration(iteration.id)
            if not iteration:
                logger.error("Failed to increment iteration")
                return False
            
            if iteration.current_iteration >= iteration.max_iterations:
                await self._complete_iteration(iteration, IterationStatus.FAILED, 
                                             "Maximum iterations reached")
                return False
            
            owner, repo = iteration.repo_full_name.split("/")
            
            context = {
                "repo_full_name": iteration.repo_full_name,
                "issue_number": iteration.issue_number,
                "issue_title": iteration.issue_title,
                "issue_body": iteration.issue_body,
                "iteration": iteration.current_iteration,
                "branch_name": iteration.branch_name,
                "pr_number": iteration.pr_number,
                "last_review_feedback": iteration.last_review_feedback
            }
            
            async with await get_github_client(iteration.installation_id) as github:
                result = await self._execute_code_agent(github, context)
            
            if not result:
                await self._complete_iteration(iteration, IterationStatus.FAILED, 
                                             "Code generation failed")
                return False
            
            db_manager.update_iteration(
                iteration.id,
                branch_name=result.get("branch_name"),
                pr_number=result.get("pr_number"),
                status=IterationStatus.WAITING_CI
            )
            
            logger.info(f"Code iteration completed, waiting for CI. PR: {result.get('pr_number')}")
            return True
            
        except Exception as e:
            logger.error(f"Code iteration failed: {e}", exc_info=True)
            await self._complete_iteration(iteration, IterationStatus.FAILED, str(e))
            return False
    
    async def _execute_code_agent(
        self, 
        github, 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        try:
            owner, repo = context["repo_full_name"].split("/")
            issue_number = context["issue_number"]
            
            branch_name = context.get("branch_name")
            if not branch_name:
                branch_name = f"agent/issue-{issue_number}"
            
            default_branch = await github.get_default_branch(owner, repo)
            base_sha = await github.get_branch_sha(owner, repo, default_branch)
            
            try:
                await github.create_branch(owner, repo, branch_name, base_sha)
                logger.info(f"Created branch {branch_name}")
            except Exception as e:
                error_str = str(e).lower()
                if "422" in error_str or "already exists" in error_str or "reference already exists" in error_str:
                    logger.info(f"Branch {branch_name} already exists, will update it")
                    try:
                        await github.update_branch(owner, repo, branch_name, base_sha)
                        logger.info(f"Updated branch {branch_name} to latest commit")
                    except Exception as update_e:
                        logger.warning(f"Could not update branch {branch_name}: {update_e}, continuing anyway")
                else:
                    logger.error(f"Failed to create branch: {e}")
                    return None
            
            analysis = await self._analyze_issue_requirements(context)
            if not analysis:
                return None
            
            changes_applied = await self._apply_code_changes(
                github, owner, repo, branch_name, analysis, context
            )
            
            if not changes_applied:
                return None
            
            pr_number = context.get("pr_number")
            if pr_number:
                pr_title = f"Fix #{issue_number}: {context['issue_title']} (Iteration {context['iteration']})"
                pr_body = self._generate_pr_description(context, analysis)
                
                await github.update_pull_request(
                    owner, repo, pr_number, title=pr_title, body=pr_body
                )
                logger.info(f"Updated PR #{pr_number}")
            else:
                pr_title = f"Fix #{issue_number}: {context['issue_title']}"
                pr_body = self._generate_pr_description(context, analysis)
                
                pr_data = await github.create_pull_request(
                    owner, repo, pr_title, pr_body, branch_name, default_branch
                )
                pr_number = pr_data["number"]
                logger.info(f"Created PR #{pr_number}")
            
            return {
                "branch_name": branch_name,
                "pr_number": pr_number,
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"Code agent execution failed: {e}", exc_info=True)
            return None
    
    async def _analyze_issue_requirements(self, context: Dict[str, Any]) -> Optional[Dict]:
        """Analyze issue requirements using LLM."""
        try:
            system_prompt = """You are an expert software developer analyzing GitHub issues.
            Analyze the issue and provide a structured response for implementation.
            
            Consider:
            1. What needs to be implemented
            2. Files to create or modify
            3. Technical approach
            4. Dependencies needed
            
            If this is a follow-up iteration, also consider the previous feedback.
            
            Respond in JSON format:
            {
                "summary": "Brief description",
                "files_to_modify": ["list", "of", "files"],
                "files_to_create": ["list", "of", "new", "files"],
                "requirements": ["list", "of", "requirements"],
                "technical_approach": "Implementation approach",
                "dependencies": ["list", "of", "dependencies"]
            }"""
            
            user_prompt = f"""Issue #{context['issue_number']}: {context['issue_title']}

Description:
{context['issue_body'] or 'No description provided'}

Iteration: {context['iteration']}"""
            
            if context.get('last_review_feedback'):
                user_prompt += f"\n\nPrevious review feedback:\n{context['last_review_feedback']}"
            
            messages = [
                self.llm_client.create_system_message(system_prompt),
                self.llm_client.create_user_message(user_prompt)
            ]
            
            response = await self.llm_client.generate_response(messages)
            
            import json
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            logger.error("Could not parse LLM analysis response")
            return None
            
        except Exception as e:
            logger.error(f"Issue analysis failed: {e}", exc_info=True)
            return None
    
    async def _apply_code_changes(
        self,
        github,
        owner: str,
        repo: str,
        branch_name: str,
        analysis: Dict,
        context: Dict[str, Any]
    ) -> bool:
        try:
            repo_files = await github.list_repository_files(owner, repo)
            
            for file_path in analysis.get("files_to_modify", []):
                success = await self._modify_file(
                    github, owner, repo, branch_name, file_path, analysis, context
                )
                if not success:
                    logger.warning(f"Failed to modify {file_path}")
            
            for file_path in analysis.get("files_to_create", []):
                success = await self._create_file(
                    github, owner, repo, branch_name, file_path, analysis, context
                )
                if not success:
                    logger.warning(f"Failed to create {file_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply code changes: {e}", exc_info=True)
            return False
    
    async def _modify_file(
        self,
        github,
        owner: str,
        repo: str,
        branch_name: str,
        file_path: str,
        analysis: Dict,
        context: Dict[str, Any]
    ) -> bool:
        try:
            file_data = await github.get_file_content(owner, repo, file_path, branch_name)
            if not file_data:
                logger.warning(f"File {file_path} not found, will create instead")
                return await self._create_file(github, owner, repo, branch_name, file_path, analysis, context)
            
            import base64
            current_content = base64.b64decode(file_data["content"]).decode()
            
            modified_content = await self._generate_file_content(
                file_path, current_content, analysis, context, is_modification=True
            )
            
            if not modified_content:
                return False
            
            commit_message = f"Modify {file_path} for issue #{context['issue_number']} (iteration {context['iteration']})"
            
            await github.create_or_update_file(
                owner, repo, file_path, modified_content, commit_message, branch_name, file_data["sha"]
            )
            
            logger.info(f"Modified file {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to modify file {file_path}: {e}", exc_info=True)
            return False
    
    async def _create_file(
        self,
        github,
        owner: str,
        repo: str,
        branch_name: str,
        file_path: str,
        analysis: Dict,
        context: Dict[str, Any]
    ) -> bool:
        try:
            file_content = await self._generate_file_content(
                file_path, None, analysis, context, is_modification=False
            )
            
            if not file_content:
                return False
            
            commit_message = f"Create {file_path} for issue #{context['issue_number']} (iteration {context['iteration']})"
            
            await github.create_or_update_file(
                owner, repo, file_path, file_content, commit_message, branch_name
            )
            
            logger.info(f"Created file {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create file {file_path}: {e}", exc_info=True)
            return False
    
    async def _generate_file_content(
        self,
        file_path: str,
        current_content: Optional[str],
        analysis: Dict,
        context: Dict[str, Any],
        is_modification: bool
    ) -> Optional[str]:
        try:
            if is_modification:
                system_prompt = f"""You are an expert software developer modifying code files.
                
                Modify the existing file to implement the required functionality.
                
                Requirements:
                - Summary: {analysis.get('summary', '')}
                - Technical approach: {analysis.get('technical_approach', '')}
                - Requirements: {', '.join(analysis.get('requirements', []))}
                
                Rules:
                1. Preserve existing functionality unless it conflicts
                2. Follow best practices and coding standards
                3. Add proper error handling and documentation
                4. Include type hints where appropriate
                
                Return only the complete modified file content."""
                
                user_prompt = f"""File to modify: {file_path}

Current content:
```
{current_content}
```

Please provide the modified file content."""
            else:
                system_prompt = f"""You are an expert software developer creating new code files.
                
                Create a new file that implements the required functionality.
                
                Requirements:
                - Summary: {analysis.get('summary', '')}
                - Technical approach: {analysis.get('technical_approach', '')}
                - Requirements: {', '.join(analysis.get('requirements', []))}
                - Dependencies: {', '.join(analysis.get('dependencies', []))}
                
                Rules:
                1. Follow best practices and coding standards
                2. Add comprehensive documentation
                3. Include proper error handling
                4. Add type hints and imports
                
                Return only the complete file content."""
                
                user_prompt = f"""Create new file: {file_path}

Please provide the complete file content."""
            
            if context.get('last_review_feedback'):
                user_prompt += f"\n\nConsider this feedback from previous review:\n{context['last_review_feedback']}"
            
            messages = [
                self.llm_client.create_system_message(system_prompt),
                self.llm_client.create_user_message(user_prompt)
            ]
            
            response = await self.llm_client.generate_response(messages)
            
            # Clean up response (remove code block markers)
            import re
            response = re.sub(r'^```[a-zA-Z]*\n', '', response)
            response = re.sub(r'\n```$', '', response)
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate content for {file_path}: {e}", exc_info=True)
            return None
    
    def _generate_pr_description(self, context: Dict[str, Any], analysis: Dict) -> str:
        """Generate PR description."""
        description = f"""## Fixes #{context['issue_number']}

**Issue Title:** {context['issue_title']}

**Iteration:** {context['iteration']}/{context.get('max_iterations', settings.max_iterations)}

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

        if context.get('last_review_feedback'):
            description += f"\n**Addressed Feedback:**\n{context['last_review_feedback']}\n"

        description += "\n### Testing\n"
        description += "- [ ] Code follows project standards\n"
        description += "- [ ] All tests pass\n"
        description += "- [ ] No linting errors\n"
        description += "- [ ] Functionality works as expected\n"

        return description
    
    async def handle_ci_completion(
        self,
        repo_full_name: str,
        pr_number: int,
        ci_status: str,
        ci_conclusion: str
    ) -> bool:
        try:
            logger.info(f"Handling CI completion for {repo_full_name} PR#{pr_number}: {ci_status}/{ci_conclusion}")
            
            iteration = db_manager.get_iteration_by_pr(repo_full_name, pr_number)
            if not iteration:
                logger.warning(f"No active iteration found for PR #{pr_number}")
                return False
            
            if iteration.status == IterationStatus.REVIEWING:
                logger.info(f"Review already in progress for iteration {iteration.id}, skipping")
                return True
            
            if iteration.status != IterationStatus.WAITING_CI:
                logger.info(f"Iteration {iteration.id} not waiting for CI (status: {iteration.status}), skipping")
                return True
            
            db_manager.update_iteration(
                iteration.id,
                last_ci_status=ci_status,
                last_ci_conclusion=ci_conclusion,
                status=IterationStatus.REVIEWING
            )
            
            await self._run_review_iteration(iteration)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle CI completion: {e}", exc_info=True)
            return False
    
    async def _run_review_iteration(self, iteration: IssueIteration) -> bool:
        try:
            logger.info(f"Running review for {iteration.repo_full_name}#{iteration.issue_number}")
            
            owner, repo = iteration.repo_full_name.split("/")
            
            async with await get_github_client(iteration.installation_id) as github:
                pr_data = await github.get_pull_request(owner, repo, iteration.pr_number)
                pr_files = await github.get_pull_request_files(owner, repo, iteration.pr_number)
                
                review_context = {
                    "repo_full_name": iteration.repo_full_name,
                    "issue_number": iteration.issue_number,
                    "issue_title": iteration.issue_title,
                    "issue_body": iteration.issue_body,
                    "pr_number": iteration.pr_number,
                    "pr_data": pr_data,
                    "pr_files": pr_files,
                    "ci_status": iteration.last_ci_status,
                    "ci_conclusion": iteration.last_ci_conclusion,
                    "iteration": iteration.current_iteration,
                    "installation_id": iteration.installation_id
                }
                
                review_result = await self._execute_reviewer_agent(review_context)
                
                if not review_result:
                    await self._complete_iteration(iteration, IterationStatus.FAILED, "Review failed")
                    return False
                
                db_manager.update_iteration(
                    iteration.id,
                    last_review_score=review_result.get("score"),
                    last_review_recommendation=review_result.get("recommendation"),
                    last_review_feedback=review_result.get("feedback")
                )
                
                await self._post_review_results(github, review_context, review_result)
                
                await self._decide_next_action(iteration, review_result)
                
                return True
                
        except Exception as e:
            logger.error(f"Review iteration failed: {e}", exc_info=True)
            await self._complete_iteration(iteration, IterationStatus.FAILED, str(e))
            return False
    
    async def _execute_reviewer_agent(self, context: Dict[str, Any]) -> Optional[Dict]:
        try:
            async with await get_github_client(context.get("installation_id")) as github:
                from ai_code_agent.github_client import GitHubClient
                
                owner, repo = context["repo_full_name"].split("/")
                installation_token = await github_app_auth.get_installation_token(
                    context.get("installation_id")
                )
                
                github_client = GitHubClient(
                    github_token=installation_token,
                    repo_owner=owner,
                    repo_name=repo
                )
                
                reviewer_agent = ReviewerAgent(github_client, self.llm_client)
                
                pr_files_data = []
                for file_info in context["pr_files"]:
                    pr_files_data.append({
                        "filename": file_info["filename"],
                        "status": file_info["status"],
                        "additions": file_info["additions"],
                        "deletions": file_info["deletions"],
                        "changes": file_info["changes"],
                        "patch": file_info.get("patch", "")
                    })
                
                review_result = await reviewer_agent._perform_comprehensive_review(
                    context["pr_data"],
                    {"title": context["issue_title"], "body": context["issue_body"]},
                    pr_files_data
                )
                
                if context["ci_conclusion"] != "success":
                    if review_result.get("overall_assessment", {}).get("score", 0) > 50:
                        review_result["overall_assessment"]["score"] *= 0.8
                        review_result["overall_assessment"]["summary"] += f" CI failed with status: {context['ci_conclusion']}"
                
                return review_result
            
        except Exception as e:
            logger.error(f"Reviewer agent execution failed: {e}", exc_info=True)
            return None
    
    async def _post_review_results(
        self, 
        github, 
        context: Dict[str, Any], 
        review_result: Dict
    ) -> None:
        try:
            owner, repo = context["repo_full_name"].split("/")
            
            comment = self._format_review_comment(review_result, context)
            
            await github.create_issue_comment(
                owner, repo, context["pr_number"], comment
            )
            
            recommendation = review_result.get("overall_assessment", {}).get("recommendation", "")
            if recommendation == "approve" and context["ci_conclusion"] == "success":
                event = "APPROVE"
            elif recommendation == "request_changes":
                event = "REQUEST_CHANGES"
            else:
                event = "COMMENT"
            
            review_summary = review_result.get("overall_assessment", {}).get("summary", "")
            await github.create_pull_request_review(
                owner, repo, context["pr_number"], review_summary, event
            )
            
            logger.info(f"Posted review results to PR #{context['pr_number']}")
            
        except Exception as e:
            logger.error(f"Failed to post review results: {e}", exc_info=True)
    
    def _format_review_comment(self, review_result: Dict, context: Dict[str, Any]) -> str:
        overall = review_result.get("overall_assessment", {})
        
        comment = f"""## AI Code Review - Iteration {context['iteration']}

### {overall.get('status', 'Review Completed')}

**Overall Score:** {overall.get('score', 0)}/100

**CI Status:** {context['ci_conclusion']} ({'✅' if context['ci_conclusion'] == 'success' else '❌'})

### Analysis:
- **Code Quality:** {review_result.get('code_quality', {}).get('summary', 'N/A')}
- **Requirements Compliance:** {review_result.get('requirements_compliance', {}).get('summary', 'N/A')}
- **Security & Best Practices:** {review_result.get('security_analysis', {}).get('summary', 'N/A')}

### Recommendation: **{overall.get('recommendation', 'unknown').upper()}**

{overall.get('summary', 'No summary available')}

---
*This review was generated automatically by AI Coding Agent*"""
        
        return comment
    
    async def _decide_next_action(
        self, 
        iteration: IssueIteration, 
        review_result: Dict
    ) -> None:
        try:
            overall = review_result.get("overall_assessment", {})
            recommendation = overall.get("recommendation", "")
            ci_success = iteration.last_ci_conclusion == "success"
            
            if recommendation in ["approve", "approve_with_suggestions"] and ci_success:
                await self._complete_iteration(
                    iteration, 
                    IterationStatus.COMPLETED,
                    "Code approved and CI passed"
                )
                return
            
            if (recommendation == "request_changes" and 
                iteration.current_iteration < iteration.max_iterations):
                
                db_manager.update_iteration(
                    iteration.id,
                    status=IterationStatus.RUNNING
                )
                
                asyncio.create_task(self._run_code_iteration(iteration))
                return
            
            await self._complete_iteration(
                iteration,
                IterationStatus.FAILED,
                f"Max iterations reached or unresolvable issues. Last recommendation: {recommendation}"
            )
            
        except Exception as e:
            logger.error(f"Failed to decide next action: {e}", exc_info=True)
            await self._complete_iteration(iteration, IterationStatus.FAILED, str(e))
    
    async def _complete_iteration(
        self, 
        iteration: IssueIteration, 
        status: IterationStatus,
        message: str
    ) -> None:
        try:
            db_manager.complete_iteration(iteration.id, status)
            
            if iteration.pr_number:
                async with await get_github_client(iteration.installation_id) as github:
                    owner, repo = iteration.repo_full_name.split("/")
                    
                    if status == IterationStatus.COMPLETED:
                        final_comment = f"""## SDLC Cycle Completed Successfully!

The automated development cycle has been completed successfully after {iteration.current_iteration} iteration(s).

**Final Status:** {message}

This PR is ready for human review and merge."""
                    else:
                        final_comment = f"""## SDLC Cycle Failed

The automated development cycle could not be completed successfully.

**Reason:** {message}
**Iterations:** {iteration.current_iteration}/{iteration.max_iterations}

Manual intervention may be required to resolve the remaining issues."""
                    
                    await github.create_issue_comment(
                        owner, repo, iteration.pr_number, final_comment
                    )
            
            logger.info(f"Completed iteration {iteration.id} with status {status}: {message}")
            
        except Exception as e:
            logger.error(f"Failed to complete iteration: {e}", exc_info=True)


orchestrator = SDLCOrchestrator()
