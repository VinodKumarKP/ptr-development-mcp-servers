import concurrent.futures
import fnmatch
import json
from typing import List, Dict

from utils.file_utils import FileUtils


class BatchUtils:
    """
    A utility class for batch processing of items.
    """

    def __init__(self, logger, bedrock_runtime):
        """
        Initialize the BatchUtils class.

        Args:
            logger: Logger instance for logging messages
        """
        self.logger = logger
        self.bedrock_runtime = bedrock_runtime

    def get_file_content(self, file_batch: List[Dict]) -> str:
        """
        Get the content of files in a batch.

        Args:
        :param file_batch: file batch to process
        :return: file content in JSON format
        """
        return json.dumps([
            {"file_path": file_info["file_path"], "content": file_info["content"]}
            for file_info in file_batch
        ])

    def create_batches(self,
                       files_to_analyze: List[str],
                       temp_dir: str,
                       batch_size: int = 3,
                       max_batch_chars: int = 500000) -> List[List[Dict]]:
        """Create batches of files for analysis.

        Args:
            files_to_analyze: List of files to analyze
            github_utils: Instance of GitHubUtils
            temp_dir: Temporary directory with cloned repository
            batch_size: Maximum number of files per batch
            max_batch_chars: Maximum batch size in characters

        Returns:
            List of batches, each containing file information
        """
        batches = []
        current_batch = []
        current_batch_size = 0

        for file_path in files_to_analyze:
            content = FileUtils.read_file_content(temp_dir, file_path)

            # Skip files with errors or that are too large
            if content.startswith("Error") or content.startswith("File too large"):
                self.logger.info(f"Skipping {file_path}: {content}")
                continue

            # Calculate approximate size of this file (in chars)
            file_size = len(content)

            # If adding this file would make the batch too large,
            # or we've reached the batch size limit, start a new batch
            if current_batch_size + file_size > max_batch_chars or len(current_batch) >= batch_size:
                if current_batch:  # Only append non-empty batches
                    batches.append(current_batch)
                current_batch = []
                current_batch_size = 0

            file_info = {"file_path": file_path, "content": content}
            current_batch.append(file_info)
            current_batch_size += file_size

        # Add the last batch if it has any files
        if current_batch:
            batches.append(current_batch)

        self.logger.info(f"Created {len(batches)} batches of files")
        return batches

    def analyze_file_batch(self,
                           model_id: str,
                           file_batch: List[Dict],
                           prompt: str
                           ) -> Dict:
        """Analyze a batch of files for issues.

        Args:
            file_batch: List of file information dictionaries
            issue_flag: Flag to indicate if issues should be found
            remediated_code: Flag to indicate if remediated code should be returned

        Returns:
            Dict containing analysis results
        """
        # Log which files are being analyzed
        for file_info in file_batch:
            self.logger.info(f"Analyzing file: {file_info['file_path']}")

        try:
            # Call Bedrock model
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 8000,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "top_p": 0.5,
                    "top_k": 50,
                    "stop_sequences": ["\n\nHuman:"]
                })
            )

            # Process response
            response_body = json.loads(response.get('body').read())
            content = response_body.get('content', [])

            return content

        except Exception as e:
            self.logger.error(f"Error analyzing batch: {str(e)}")
            return {"error": str(e)}

    def process_batches(self,
                        batches: List[List[Dict]],
                        function,
                        concurrent_batches: int = 2,
                        kwargs=None) -> List[Dict]:
        """Process batches in parallel to analyze files.

        Args:
            batches: List of batches to process
            issue_flag: Flag to indicate if issues should be found
            remediated_code: Flag to indicate if remediated code should be returned
            concurrent_batches: Number of batches to process concurrently

        Returns:
            Tuple of (batch_results, file_remediations)
        """
        all_batch_results = []

        # Process batches in groups of concurrent_batches
        for i in range(0, len(batches), concurrent_batches):
            current_batches = batches[i:i + concurrent_batches]
            self.logger.info(
                f"Processing batch group {i // concurrent_batches + 1} with {len(current_batches)} batches")

            # Use ThreadPoolExecutor for parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_batches) as executor:
                # Submit all batch tasks
                future_to_batch = {
                    executor.submit(
                        function,
                        batch,
                        **kwargs
                    ): batch for batch in current_batches
                }

                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    batch_index = batches.index(batch)
                    self.logger.info(f"Completed batch {batch_index + 1} of {len(batches)} with {len(batch)} files")

                    try:
                        batch_result = future.result()
                        all_batch_results.append(batch_result)

                    except Exception as e:
                        self.logger.error(f"Batch processing failed: {str(e)}")
                        # self.logger.error(traceback.format_exc())

        return all_batch_results

    def extract_files_from_text(self, text: str) -> Dict[str, str]:
        """Extract filenames and their content from a text block.

        Args:
            text: Text containing file information

        Returns:
            Dict mapping filenames to content
        """
        files_dict = {}

        # Split the text by the separator
        file_blocks = text.split("================")

        # Process each file block
        for block in file_blocks:
            block = block.strip()
            if not block:  # Skip empty blocks
                continue

            # Extract the filename (between *** ***)
            filename_start = block.find("***") + 3
            filename_end = block.find("***", filename_start)

            if filename_start >= 3 and filename_end != -1:
                filename = block[filename_start:filename_end].strip()

                # Extract the content (everything after the filename line)
                content_start = block.find("\n", filename_end) + 1
                if content_start > 0:
                    content = block[content_start:].strip()
                    files_dict[filename] = content

        return files_dict

    def get_file_list(self, repo_directory, file_patterns=None, file_limit=None,
                      logger=None):
        """
        Filter a list of files based on patterns or limit to a maximum number.

        Args:
            github_utils: Instance of GitHubUtils
            repo_directory: Temporary directory with cloned repository
            file_patterns (list, optional): List of file patterns or exact filenames to filter
            file_limit (int, optional): Maximum number of files to return if no patterns provided
            logger (logging.Logger, optional): Logger for informational messages

        Returns:
            list: Filtered list of files to analyze
        """

        all_files = FileUtils.get_file_list(repo_directory)
        logger.info(f"Found {len(all_files)} files")

        # Filter files if specific file patterns were provided
        if file_patterns:
            files_to_analyze = []
            for pattern in file_patterns:
                # Check if pattern contains wildcard characters
                if '*' in pattern or '?' in pattern or '[' in pattern:
                    # Use fnmatch to find files matching the pattern
                    matching_files = [f for f in all_files if fnmatch.fnmatch(f, pattern)]
                    files_to_analyze.extend(matching_files)
                else:
                    # Exact filename match
                    if pattern in all_files:
                        files_to_analyze.append(pattern)

            # Remove duplicates while preserving order
            files_to_analyze = list(dict.fromkeys(files_to_analyze))
            logger.info(f"Filtering to {len(files_to_analyze)} files matching specified patterns")
        else:
            # Otherwise limit by file_limit (if provided)
            if file_limit is not None:
                files_to_analyze = all_files[:file_limit]
                logger.info(f"Analyzing up to {file_limit} files")
            else:
                files_to_analyze = all_files
                logger.info(f"Analyzing all {len(all_files)} files")

        return files_to_analyze
