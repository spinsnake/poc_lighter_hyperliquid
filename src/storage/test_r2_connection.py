from __future__ import annotations

import argparse
from datetime import datetime, timezone

from src.storage.r2_config import create_r2_s3_client, load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Cloudflare R2 connection using config.yaml.")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config file.")
    parser.add_argument(
        "--upload-test",
        action="store_true",
        help="Also upload a small test object to verify write access.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the uploaded test object after a successful upload.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app_config = load_config(args.config)
    client = create_r2_s3_client(app_config.r2)

    print("Loaded config:")
    for key, value in app_config.r2.masked().items():
        print(f"  {key}: {value}")

    client.head_bucket(Bucket=app_config.r2.bucket)
    print(f"Bucket reachable: {app_config.r2.bucket}")

    response = client.list_objects_v2(Bucket=app_config.r2.bucket, MaxKeys=5)
    object_count = response.get("KeyCount", 0)
    print(f"List objects OK: first page returned {object_count} objects")

    if not args.upload_test:
        return

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key_prefix = app_config.r2.remote_prefix.strip("/")
    key = f"{key_prefix}/healthcheck/r2_test_{ts}.txt" if key_prefix else f"healthcheck/r2_test_{ts}.txt"
    body = f"r2 connection ok {ts}\n".encode("utf-8")

    client.put_object(Bucket=app_config.r2.bucket, Key=key, Body=body, ContentType="text/plain")
    print(f"Upload OK: s3://{app_config.r2.bucket}/{key}")

    if args.cleanup:
        client.delete_object(Bucket=app_config.r2.bucket, Key=key)
        print(f"Cleanup OK: deleted s3://{app_config.r2.bucket}/{key}")


if __name__ == "__main__":
    main()
