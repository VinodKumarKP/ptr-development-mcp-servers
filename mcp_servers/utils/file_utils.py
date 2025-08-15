import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from constants import Constants

MAX_FILE_SIZE = 100000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileUtils:
    @staticmethod
    def read_file_content(repo_path: str, file_path: str, max_size: int = None) -> str:
        """
        Reads the content of a file from the given repository path.

        Args:
            repo_path (str): Path to the repository.
            file_path (str): Relative path to the file within the repository.
            max_size (int, optional): Maximum allowed file size in bytes.

        Returns:
            str: File content or error message if file is not found or too large.
        """
        if max_size is None:
            max_size = MAX_FILE_SIZE
        full_path = os.path.join(repo_path, file_path)
        try:
            if not os.path.isfile(full_path):
                return f"File not found: {file_path}"
            if os.path.getsize(full_path) > max_size:
                return f"File too large to process (>{max_size} bytes)"
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return f"Error reading file: {str(e)}"

    @staticmethod
    def get_file_content(directory_path, file_path: str) -> Dict[str, str]:
        """
        Gets the content of a file and returns it in a dictionary.

        Args:
            directory_path (str): Path to the directory.
            file_path (str): Relative path to the file.

        Returns:
            Dict[str, str]: Dictionary with file path and content, or error message.
        """
        try:
            content = FileUtils.read_file_content(directory_path, file_path)
            return {
                "filePath": file_path,
                "content": content
            }
        except Exception as e:
            logger.error(f"Error getting file content: {str(e)}")
            return {
                "error": str(e)
            }

    @staticmethod
    def get_file_list(repo_path: str) -> List[str]:
        """
        Retrieves a list of all files in the repository, excluding certain files and directories.

        Args:
            repo_path (str): Path to the repository.

        Returns:
            List[str]: List of relative file paths.
        """
        file_list = []
        repo_path = Path(repo_path)
        try:
            for path in repo_path.rglob('*'):
                if path.is_dir():
                    continue
                if '.git' in path.parts:
                    continue
                if any(part.startswith('.') for part in path.parts):
                    continue
                if any(part.startswith('__') for part in path.parts):
                    continue
                if path.suffix.lower() in Constants.SKIP_EXTENSIONS:
                    continue
                rel_path = str(path.relative_to(repo_path))
                file_list.append(rel_path)
            return file_list
        except Exception as e:
            logger.error(f"Error getting file list: {str(e)}")
            return []

    @staticmethod
    def cleanup_temp_dir(temp_dir: Optional[str]) -> None:
        """
        Removes the specified temporary directory and its contents.

        Args:
            temp_dir (Optional[str]): Path to the temporary directory.

        Returns:
            None
        """
        if temp_dir and os.path.exists(temp_dir):
            logger.info(f"Cleaning up temporary files at {temp_dir}...")
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Error cleaning up temporary directory: {str(e)}")
                subprocess.run(["rm", "-rf", temp_dir], check=False)

    @staticmethod
    def zip_file_content(repo_path: str, file_content: Dict[str, str], key: str) -> str:
        """
        Writes file contents to a directory and creates a zip archive.

        Args:
            repo_path (str): Path to the repository.
            file_content (Dict[str, str]): Dictionary of file paths and their contents.
            key (str): Subdirectory name for storing files.

        Returns:
            str: Path to the created zip archive.

        Raises:
            Exception: If an error occurs during zipping.
        """
        try:
            destination_folder = os.path.join(repo_path, key)
            os.makedirs(destination_folder, exist_ok=True)
            for file_path, content in file_content.items():
                full_path = os.path.join(destination_folder, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            zip_base_path = os.path.join(repo_path, key)
            zip_path = zip_base_path + '.zip'
            shutil.make_archive(zip_base_path, 'zip', destination_folder)
            return zip_path
        except Exception as e:
            logger.error(f"Error making the remediated code zip: {str(e)}")
            raise Exception(f"Error making the remediated code zip: {str(e)}") from e

    def create_zip_excluding_dirs(self, source_dir, output_zip_path, excluded_dirs=None):
        """
        Create zip file with option to exclude certain directories
        :param source_dir:
        :param output_zip_path:
        :param excluded_dirs:
        :return:
        """
        if excluded_dirs is None:
            excluded_dirs = []
        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                # Modify dirs in-place to prevent os.walk from entering excluded directories
                dirs[:] = [d for d in dirs if d not in excluded_dirs]

                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate the relative path within the archive
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)
