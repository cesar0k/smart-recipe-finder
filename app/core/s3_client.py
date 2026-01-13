import asyncio
import json
import logging
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self) -> None:
        self.session = boto3.session.Session()
        self.client = self.session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )

    async def upload_file(
        self, file_obj: BinaryIO, object_name: str, content_type: str
    ) -> str:
        try:
            await asyncio.to_thread(
                self.client.upload_fileobj,
                Fileobj=file_obj,
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_name,
                ExtraArgs={"ContentType": content_type},
            )

            return (
                f"{settings.S3_PUBLIC_ENDPOINT}/{settings.S3_BUCKET_NAME}/{object_name}"
            )

        except ClientError as ex:
            logger.error(f"S3 file upload failed: {ex}")
            raise ex

    async def delete_file(self, object_name: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.delete_object,
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_name,
            )
        except ClientError as ex:
            logger.error(f"S3 file delete failed: {ex}")
            raise ex

    async def ensure_bucket_exists(self) -> None:
        try:
            await asyncio.to_thread(
                self.client.head_bucket, Bucket=settings.S3_BUCKET_NAME
            )
        except ClientError:
            logger.info(f"Bucket {settings.S3_BUCKET_NAME} not found. Creating...")
            await asyncio.to_thread(
                self.client.create_bucket, Bucket=settings.S3_BUCKET_NAME
            )

            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicRead",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{settings.S3_BUCKET_NAME}/*"],
                    }
                ],
            }

            await asyncio.to_thread(
                self.client.put_bucket_policy,
                Bucket=settings.S3_BUCKET_NAME,
                Policy=json.dumps(policy),
            )


s3_client = S3Client()
