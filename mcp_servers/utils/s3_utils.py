import json
import time
from typing import Dict


class S3Utils:
    def __init__(self, s3_client, logger):
        self.s3_client = s3_client
        self.logger = logger

    def download_file_from_s3(self, bucket: str, key: str, file_path: str) -> None:
        """Download a file from an S3 bucket.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            file_path: Path to save the downloaded file
        """
        try:
            self.s3_client.download_file(bucket, key, file_path)
            self.logger.info(f"File downloaded from {bucket}/{key} to {file_path}")
        except Exception as e:
            self.logger.error(f"Error downloading file from S3: {str(e)}")

    def upload_file_to_s3(self, file_path: str, bucket: str, key: str) -> str:
        """Upload a file to an S3 bucket.

        Args:
            file_path: Path to the file to upload
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            Presigned URL for the uploaded file
        """
        try:
            self.s3_client.upload_file(file_path, bucket, key)
            self.logger.info(f"File {file_path} uploaded to {bucket}/{key}")

            url = self.s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=3600
            )

            return url
        except Exception as e:
            self.logger.error(f"Error uploading file to S3: {str(e)}")
            return f"Error uploading file to S3: {str(e)}"

    def save_to_s3(self, results: Dict, git_url: str, branch: str, s3_bucket: str) -> str:
        """Save results to S3 bucket.

        Args:
            results: Analysis results
            git_url: Git repository URL
            branch: Branch analyzed

        Returns:
            Presigned URL for the saved results
        """
        # Create a safe filename from git URL
        repo_name = git_url.split('/')[-1].replace('.git', '')
        key = f"{repo_name}/{branch}/{int(time.time())}_results.json"

        try:
            self.s3_client.put_object(
                Bucket=s3_bucket,
                Key=key,
                Body=json.dumps(results, indent=2),
                ContentType='application/json'
            )

            url = self.s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': s3_bucket, 'Key': key},
                ExpiresIn=3600
            )

            return url
        except Exception as e:
            self.logger.error(f"Error saving results to S3: {str(e)}")
            return f"Error saving results to S3: {str(e)}"
