import os
import io
import logging
from typing import Optional
import boto3
from botocore.client import Config

logger = logging.getLogger("ai_os.minio")

class MinIOClient:
    """
    Manages object storage for media and report storage using MinIO/S3 API.
    Provides local filesystem fallback for offline development.
    """
    def __init__(self, endpoint: Optional[str] = None, access_key: Optional[str] = None, secret_key: Optional[str] = None):
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "")
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "ai-os-storage")
        
        self.s3_client = None
        self.is_mocked = False
        self.local_dir = os.getenv(
            "STORAGE_LOCAL_DIR",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "local_buckets"),
        )
        
        self.connect()

    def connect(self):
        try:
            # Minio requires HTTP/HTTPS protocols in the endpoint
            endpoint_url = self.endpoint
            if not endpoint_url.startswith("http://") and not endpoint_url.startswith("https://"):
                endpoint_url = f"http://{endpoint_url}"
                
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1"
            )
            # Verify client works by creating bucket if not exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
            except self.s3_client.exceptions.ClientError:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"MinIO bucket '{self.bucket_name}' created.")
            
            logger.info("Connected to MinIO object storage successfully.")
            self.is_mocked = False
        except Exception as e:
            logger.warning(f"Failed to connect to MinIO: {e}. Falling back to local filesystem directory storage.")
            self.is_mocked = True
            os.makedirs(os.path.join(self.local_dir, self.bucket_name), exist_ok=True)

    def upload_file(self, object_name: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
        """
        Uploads data to bucket and returns the object reference identifier/URL.
        """
        if self.is_mocked:
            local_path = os.path.join(self.local_dir, self.bucket_name, object_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_data)
            logger.info(f"Local mock storage: Saved object to {local_path}")
            return f"local://{self.bucket_name}/{object_name}"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_name,
                Body=file_data,
                ContentType=content_type
            )
            return f"s3://{self.bucket_name}/{object_name}"
        except Exception as e:
            logger.error(f"Error uploading to MinIO: {e}")
            # Fall back to local mock
            local_path = os.path.join(self.local_dir, self.bucket_name, object_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_data)
            return f"local://{self.bucket_name}/{object_name}"

    def download_file(self, object_name: str) -> Optional[bytes]:
        """
        Downloads data from the storage bucket.
        """
        # Parse schemes
        clean_name = object_name
        if object_name.startswith("s3://") or object_name.startswith("local://"):
            parts = object_name.split("/", 3)
            if len(parts) >= 4:
                clean_name = parts[3]

        if self.is_mocked or object_name.startswith("local://"):
            local_path = os.path.join(self.local_dir, self.bucket_name, clean_name)
            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    return f.read()
                logger.info(f"Local mock storage: Read object from {local_path}")
            logger.warning(f"File not found in local mock: {local_path}")
            return None

        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=clean_name)
            return response["Body"].read()
        except Exception as e:
            logger.error(f"Error downloading from MinIO: {e}")
            # Try loading from local path as backup
            local_path = os.path.join(self.local_dir, self.bucket_name, clean_name)
            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    return f.read()
            return None
