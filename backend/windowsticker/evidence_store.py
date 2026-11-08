"""Run evidence archived in Vultr Object Storage.

Every graded run's full record (steps, commands, network log, verdict) is written once to an
S3-compatible bucket, with its SHA-256 kept next to the run in the database. Anyone holding the
replay can download the bundle and check it against that hash; the lab's own database is no
longer the only copy of the evidence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config


@dataclass
class EvidenceStore:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str = "wsk-evidence"

    def _client(self) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    @staticmethod
    def bundle(record: dict[str, Any]) -> bytes:
        """The canonical bytes of a run's evidence: sorted keys, so the hash is reproducible."""
        payload = {k: v for k, v in record.items() if k != "archive"}
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def _ensure_bucket(self, s3: Any) -> None:
        try:
            s3.head_bucket(Bucket=self.bucket)
        except Exception:
            s3.create_bucket(Bucket=self.bucket)

    def _put(self, test_id: str, run_id: str, data: bytes) -> dict[str, Any]:
        s3 = self._client()
        self._ensure_bucket(s3)
        key = f"{test_id}/{run_id}.json"
        digest = hashlib.sha256(data).hexdigest()
        s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/json",
            Metadata={"sha256": digest},
        )
        return {"key": key, "sha256": digest, "bytes": len(data), "bucket": self.bucket}

    async def put_run(self, test_id: str, record: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._put, test_id, record["run_id"], self.bundle(record))

    def presigned_url(self, key: str, expires_s: int = 3600) -> str:
        url: str = self._client().generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_s
        )
        return url
