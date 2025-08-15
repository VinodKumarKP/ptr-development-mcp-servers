import json
import os
import sys
import time
import traceback
from typing import Optional, List, Dict

file_root = os.path.dirname(os.path.abspath(__file__))
path_list = [
    file_root,
    os.path.dirname(file_root)
]
for path in path_list:
    if path not in sys.path:
        sys.path.append(path)

MODEL_ID = os.environ.get('MODEL_ID', 'us.anthropic.claude-3-5-haiku-20241022-v1:0')

from mcp_servers.utils.aws_utils import AWSUtils
from mcp_servers.utils.batch_utils import BatchUtils
from mcp_servers.utils.file_utils import FileUtils
from mcp_servers.tools.git_tools import GitTools
from mcp_servers.utils.prompt_generator import PromptGenerator
from mcp_servers.utils.s3_utils import S3Utils
from mcp_server_core.utils.logger_utils import get_logger

logger = get_logger()


class CodeRemediationTools:
    """Agent to analyze and remediate code in git repositories."""
    RESULTS_BUCKET = os.environ['RESULTS_BUCKET']

    def __init__(self, model_id: str = MODEL_ID):
        """Initialize the agent with required configuration.

        Args:
            model_id: The ID of the Bedrock model to use
        """
        self.aws_utils = AWSUtils()
        self.model_id = model_id
        self._validate_environment()
        self.s3_utils = S3Utils(self.aws_utils.get_s3_client(), logger)
        self.batch_utils = BatchUtils(logger, self.aws_utils.get_bedrock_runtime_client())

    def _validate_environment(self) -> None:
        """Validate that required environment variables are present."""
        if not self.model_id:
            raise ValueError("MODEL_ID environment variable is not set")

    def analyze_repository(self, git_url: str, branch: str = "main", issue_flag=True, remediated_code=False) -> dict:
        """
        Analyze the specified git repository.

        Args:
            git_url: Git repository URL
            branch: Branch to analyze (default: main)
            issue_flag: Flag to indicate if issues should be found
            remediated_code: Flag to indicate if remediated code should be returned

        Returns:
            dict: Analysis results
        """
        return self._analyze_repository(git_url=git_url,
                                        branch=branch,
                                        remediated_code=remediated_code,
                                        issue_flag=issue_flag)

    def _analyze_repository(self,
                            repo_directory: Optional[str] = None,
                            git_url: Optional[str] = None,
                            branch: Optional[str] = None,
                            file_limit: Optional[int] = 20,
                            batch_size: Optional[int] = 3,
                            issue_flag: Optional[bool] = True,
                            remediated_code: Optional[bool] = False,
                            file_list: Optional[List[str]] = None) -> Dict:
        """Analyze the repository for code issues.

        Args:
            repo_directory: Directory of the git repository to analyze
            git_url: Optional git repository url
            branch: Optional git branch
            file_limit: Maximum number of files to analyze
            batch_size: Number of files to analyze in one batch
            issue_flag: Flag to indicate if issues should be found
            remediated_code: Flag to indicate if remediated code should be returned
            file_list: Optional list of specific files to analyze

        Returns:
            Dict containing analysis results
            :param git_url:
        """

        if repo_directory is None and git_url is not None:
            git_util = GitTools()
            repo_directory = git_util.clone_repository(git_url=git_url, branch=branch)

        try:

            files_to_analyze = self.batch_utils.get_file_list(repo_directory=repo_directory,
                                                              file_limit=file_limit,
                                                              file_patterns=file_list,
                                                              logger=logger)

            # Create batches for analysis
            batches = self.batch_utils.create_batches(
                files_to_analyze=files_to_analyze,
                temp_dir=repo_directory,
                batch_size=batch_size
            )

            # Process batches and collect results
            all_batch_results = self.batch_utils.process_batches(function=self._analyze_file_batch,
                                                                 batches=batches,
                                                                 kwargs={
                                                                     "issue_flag": issue_flag,
                                                                     "remediated_code": remediated_code
                                                                 },
                                                                 concurrent_batches=2
                                                                 )

            # Process all issues from batch results
            all_issues = self._collect_issues(all_batch_results)
            file_remediations = self._collect_remediations(all_batch_results)

            # Generate summary if issues were found
            summary = {}
            if all_issues:
                summary = self._generate_summary(all_issues)

            # Handle remediated code if available
            zip_file_s3_url = ''
            if file_remediations:
                zip_file_s3_url = self._handle_remediated_code(
                    temp_dir=repo_directory,
                    file_remediations=file_remediations,
                    git_url=git_url,
                    branch=branch
                )

            # Prepare and save final results
            results = {
                "file_analysis": all_issues,
                "summary": summary
            }

            # # Save results to S3
            s3_url = self.s3_utils.save_to_s3(results, git_url, branch, self.RESULTS_BUCKET)
            if s3_url:
                results["s3_url"] = s3_url

            if file_remediations:
                results["remediated_code_s3_url"] = zip_file_s3_url

            return results

        finally:
            # Cleanup should happen even if there's an exception
            if repo_directory and os.path.exists(repo_directory):
                logger.info(f"Cleaning up temporary directory: {repo_directory}")
                import shutil
                shutil.rmtree(repo_directory, ignore_errors=True)

    def _analyze_file_batch(self,
                            file_batch: List[Dict],
                            issue_flag: bool = True,
                            remediated_code: bool = True) -> Dict:
        """Analyze a batch of files for issues.

        Args:
            file_batch: List of file information dictionaries
            issue_flag: Flag to indicate if issues should be found
            remediated_code: Flag to indicate if remediated code should be returned

        Returns:
            Dict containing analysis results
        """
        # Generate prompt for analysis
        prompt = PromptGenerator.generate_prompt_for_code_analyze_and_remediations(
            contents=self.batch_utils.get_file_content(file_batch=file_batch),
            issues=issue_flag,
            remediated_code=remediated_code
        )

        try:

            content = self.batch_utils.analyze_file_batch(model_id=self.model_id,
                                                          file_batch=file_batch,
                                                          prompt=prompt)

            if content and len(content) > 0:
                text = content[0].get('text', '')
                issues = ''
                remediated_code_content = ''

                # Extract issues if present
                if '%issueStart' in text and '%issueEnd' in text:
                    start = text.find('%issueStart') + 12
                    end = text.rfind('%issueEnd')
                    json_text = text[start:end]
                    try:
                        issues = json.loads(json_text)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse issues JSON: {json_text}")
                        issues = []

                # Extract remediated code if present
                if '%remediated_codeStart' in text and '%remediated_codeEnd' in text:
                    start = text.find('%remediated_codeStart') + 22
                    end = text.rfind('%remediated_codeEnd')
                    remediated_code_content = text[start:end]

                return {"issues": issues, "remediated_code": remediated_code_content}

            return {"issues": [], "remediated_code": ""}

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            line_number = traceback.extract_tb(exc_traceback)[-1][1]
            logger.error(f"Error analyzing batch: {str(e)} at line {line_number}")
            logger.error(traceback.format_exc())
            return {"issues": [], "error": str(e)}

    def _collect_remediations(self, batch_results: List[Dict]):
        """Collect all remediated code from batch results.

        Args:
            batch_results: List of batch result dictionaries

        Returns:
            List of all remediated code found
        """
        file_remediations = {}
        for batch_result in batch_results:
            if batch_result.get('remediated_code'):
                batch_remediations = self.batch_utils.extract_files_from_text(batch_result.get('remediated_code'))
                file_remediations.update(batch_remediations)
        return file_remediations

    def _collect_issues(self, batch_results: List[Dict]) -> List[Dict]:
        """Collect all issues from batch results.

        Args:
            batch_results: List of batch result dictionaries

        Returns:
            List of all issues found
        """
        all_issues = []
        for batch_result in batch_results:
            if batch_result.get('issues'):
                all_issues.extend(batch_result.get('issues'))
        return all_issues

    def _generate_summary(self, all_issues: List[Dict]) -> Dict:
        """Generate a summary of all issues found.

        Args:
            all_issues: List of all issues found

        Returns:
            Dict containing summary information
        """
        prompt = f"""
        You are a security and code quality expert reviewing analysis results.

        Below are the analysis results from multiple files. Please provide:
        1. An executive summary of the key findings
        2. Prioritized recommendations for the most critical issues
        3. An overall assessment of the code quality and security
        4. Any patterns or systemic issues identified

        Analysis results:
        {json.dumps([{k: v for k, v in result.items() if k != 'remediated_code'}
                     for result in all_issues], indent=2)}

        Format your response as a JSON object with the following structure:
        {{
          "rating": "Rating of the code quality and security between 1 and 10",
          "executive_summary": "Summary of key findings",
          "priority_recommendations": [
            "Recommendation 1",
            "Recommendation 2",
            ...
          ],
          "overall_assessment": "Overall assessment of code quality and security",
          "patterns_identified": [
            "Pattern 1",
            "Pattern 2",
            ...
          ]
        }}
        """

        try:
            response = self.aws_utils.get_bedrock_runtime_client().invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                })
            )

            response_body = json.loads(response.get('body').read())
            content = response_body.get('content', [])

            if content and len(content) > 0:
                text = content[0].get('text', '')

                # Extract JSON from response
                if '{' in text and '}' in text:
                    start = text.find('{')
                    end = text.rfind('}') + 1
                    json_text = text[start:end]
                    try:
                        return json.loads(json_text)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse summary JSON: {json_text}")

                # Try to parse the entire text as JSON
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse summary from text: {text}")

            return {}

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return {"error": str(e)}

    def _handle_remediated_code(self,
                                temp_dir: str,
                                file_remediations: Dict[str, str],
                                git_url: str,
                                branch: str) -> str:
        """Handle remediated code and upload to S3.

        Args:
            temp_dir: Temporary directory with cloned repository
            file_remediations: Dict mapping filenames to remediated content
            git_url: URL of the git repository
            branch: Branch name

        Returns:
            S3 URL of the uploaded ZIP file
        """
        try:
            zip_path = FileUtils.zip_file_content(
                repo_path=temp_dir,
                file_content=file_remediations,
                key="remediated_code"
            )

            project_name = git_url.split('/')[-1].replace('.git', '')
            key = f"{project_name}/{branch}/remediated_code/{int(time.time())}_{project_name}_{branch}_remediated_code.zip"

            return self.s3_utils.upload_file_to_s3(
                file_path=zip_path,
                bucket=self.RESULTS_BUCKET,
                key=key
            )
        except Exception as e:
            logger.error(f"Error handling remediated code: {str(e)}")
            return ""

# code_remediation_agent = CodeRemediationUtils(model_id='us.anthropic.claude-3-5-haiku-20241022-v1:0')
# response = code_remediation_agent.analyze_repository(git_url='https://github.com/VinodKumarKP/python_project.git', branch='main',
#                                                      remediated_code=True)
# print(json.dumps(response, indent=2))
