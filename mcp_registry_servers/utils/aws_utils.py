import os
import boto3
from botocore.config import Config

class AWSUtils:
    def __init__(self, read_timeout=1000):
        self.region = os.environ.get('AWS_REGION', 'us-east-2')
        self.boto3_config = Config(read_timeout=read_timeout)
        if not self.region:
            raise EnvironmentError("AWS_REGION environment variable is not set")

    def get_bedrock_agent_runtime_client(self):
        """
        Get the Bedrock Agent Runtime client configured with the AWS region and read timeout.
        """
        return boto3.client(
            'bedrock-agent-runtime',
            self.region,
            config=self.boto3_config
        )

    def get_bedrock_agent_client(self):
        """
        Get the Bedrock Agent client configured with the AWS region and read timeout.
        """
        return boto3.client(
            'bedrock-agent',
            self.region,
            config=self.boto3_config
        )

    def get_bedrock_runtime_client(self):
        """
        Get the Bedrock client configured with the AWS region and read timeout.
        """
        return boto3.client(
            'bedrock-runtime',
            self.region,
            config=self.boto3_config
        )

    def get_s3_client(self):
        """
        Get the S3 client configured with the AWS region and read timeout.
        """
        return boto3.client(
            's3',
            self.region,
            config=self.boto3_config
        )