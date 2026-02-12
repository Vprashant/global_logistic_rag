"""
S3 Connector for ingesting documents from AWS S3 buckets.
Supports PDF contracts, bills of lading, and other unstructured documents.
"""

import boto3
from typing import List, Dict, Optional, Generator
from datetime import datetime
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Connector:
    """Connector for AWS S3 data source."""

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1"
    ):
        """
        Initialize S3 connector.

        Args:
            aws_access_key_id: AWS access key (uses env/IAM role if None)
            aws_secret_access_key: AWS secret key (uses env/IAM role if None)
            region_name: AWS region name
        """
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        logger.info(f"S3 connector initialized for region: {region_name}")

    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        suffix: str = "",
        max_keys: int = 1000
    ) -> List[Dict]:
        """
        List objects in S3 bucket with optional filtering.

        Args:
            bucket: S3 bucket name
            prefix: Filter by prefix (e.g., "contracts/2024/")
            suffix: Filter by suffix (e.g., ".pdf")
            max_keys: Maximum number of objects to return

        Returns:
            List of object metadata dictionaries
        """
        objects = []
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=bucket,
                Prefix=prefix,
                PaginationConfig={'MaxItems': max_keys}
            )

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    if suffix and not obj['Key'].endswith(suffix):
                        continue

                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag'].strip('"'),
                        'bucket': bucket
                    })

            logger.info(f"Found {len(objects)} objects in s3://{bucket}/{prefix}")
            return objects

        except ClientError as e:
            logger.error(f"Error listing S3 objects: {e}")
            raise

    def download_object(
        self,
        bucket: str,
        key: str
    ) -> bytes:
        """
        Download object content from S3.

        Args:
            bucket: S3 bucket name
            key: Object key

        Returns:
            Object content as bytes
        """
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read()
            logger.debug(f"Downloaded s3://{bucket}/{key} ({len(content)} bytes)")
            return content

        except ClientError as e:
            logger.error(f"Error downloading s3://{bucket}/{key}: {e}")
            raise

    def get_object_metadata(
        self,
        bucket: str,
        key: str
    ) -> Dict:
        """
        Get object metadata without downloading content.

        Args:
            bucket: S3 bucket name
            key: Object key

        Returns:
            Metadata dictionary
        """
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)

            metadata = {
                'bucket': bucket,
                'key': key,
                'size': response['ContentLength'],
                'content_type': response.get('ContentType', ''),
                'last_modified': response['LastModified'],
                'etag': response['ETag'].strip('"'),
                'metadata': response.get('Metadata', {}),
                'source_type': 's3',
                'source_uri': f"s3://{bucket}/{key}"
            }

            return metadata

        except ClientError as e:
            logger.error(f"Error getting metadata for s3://{bucket}/{key}: {e}")
            raise

    def stream_objects(
        self,
        bucket: str,
        prefix: str = "",
        suffix: str = ".pdf",
        batch_size: int = 10
    ) -> Generator[List[Dict], None, None]:
        """
        Stream objects in batches for efficient processing.

        Args:
            bucket: S3 bucket name
            prefix: Filter by prefix
            suffix: Filter by file extension
            batch_size: Number of objects per batch

        Yields:
            Batches of document dictionaries with content and metadata
        """
        objects = self.list_objects(bucket, prefix, suffix)
        batch = []

        for obj_meta in objects:
            try:
                content = self.download_object(bucket, obj_meta['key'])
                full_metadata = self.get_object_metadata(bucket, obj_meta['key'])

                document = {
                    'content': content,
                    'metadata': full_metadata,
                    'ingestion_timestamp': datetime.utcnow().isoformat()
                }

                batch.append(document)

                if len(batch) >= batch_size:
                    logger.info(f"Yielding batch of {len(batch)} documents")
                    yield batch
                    batch = []

            except Exception as e:
                logger.error(f"Error processing {obj_meta['key']}: {e}")
                continue

        if batch:
            logger.info(f"Yielding final batch of {len(batch)} documents")
            yield batch

    def ingest_folder(
        self,
        bucket: str,
        prefix: str,
        file_extensions: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Ingest all documents from a specific S3 folder.

        Args:
            bucket: S3 bucket name
            prefix: Folder prefix (e.g., "contracts/2024/Q1/")
            file_extensions: List of allowed extensions (e.g., [".pdf", ".docx"])

        Returns:
            List of ingested document dictionaries
        """
        if file_extensions is None:
            file_extensions = [".pdf", ".docx", ".txt"]

        documents = []
        objects = self.list_objects(bucket, prefix)

        for obj_meta in objects:
            if not any(obj_meta['key'].endswith(ext) for ext in file_extensions):
                continue

            try:
                content = self.download_object(bucket, obj_meta['key'])
                full_metadata = self.get_object_metadata(bucket, obj_meta['key'])

                document = {
                    'content': content,
                    'metadata': full_metadata,
                    'ingestion_timestamp': datetime.utcnow().isoformat()
                }

                documents.append(document)

            except Exception as e:
                logger.error(f"Error ingesting {obj_meta['key']}: {e}")
                continue

        logger.info(f"Ingested {len(documents)} documents from s3://{bucket}/{prefix}")
        return documents


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    connector = S3Connector()

    # List PDF contracts
    objects = connector.list_objects(
        bucket="logistics-contracts",
        prefix="2024/",
        suffix=".pdf"
    )
    print(f"Found {len(objects)} PDF contracts")

    # Stream and process in batches
    for batch in connector.stream_objects(
        bucket="logistics-contracts",
        prefix="2024/Q1/",
        batch_size=5
    ):
        print(f"Processing batch of {len(batch)} documents")
