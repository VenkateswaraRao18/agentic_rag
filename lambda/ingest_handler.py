import os
import subprocess
from pathlib import Path

import boto3

from app.config import settings


def _download_docs(bucket: str, prefix: str, target_dir: Path) -> None:
    s3 = boto3.client("s3", region_name=settings.aws_region)
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            rel_path = key[len(prefix) :].lstrip("/")
            output = target_dir / rel_path
            output.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(output))


def handler(event, _context):
    bucket = event.get("bucket", settings.s3_docs_bucket)
    prefix = event.get("prefix", "docs/")
    local_docs = Path("/tmp/docs")
    local_docs.mkdir(parents=True, exist_ok=True)
    _download_docs(bucket, prefix, local_docs)

    env = os.environ.copy()
    subprocess.run(
        ["python", "-m", "ingestion.build_index", "--docs-dir", str(local_docs)],
        check=True,
        env=env,
    )
    return {"status": "ok", "bucket": bucket, "prefix": prefix}
