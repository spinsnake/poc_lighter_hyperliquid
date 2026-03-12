from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import boto3
import yaml
from botocore.client import Config as BotoConfig


@dataclass(frozen=True)
class R2Config:
    bucket: str
    account_id: str
    access_key_id: str
    secret_access_key: str
    endpoint_url: str
    region_name: str = "auto"
    remote_prefix: str = ""

    def masked(self) -> dict[str, str]:
        return {
            "bucket": self.bucket,
            "account_id": mask_secret(self.account_id),
            "access_key_id": mask_secret(self.access_key_id),
            "secret_access_key": mask_secret(self.secret_access_key),
            "endpoint_url": self.endpoint_url,
            "region_name": self.region_name,
            "remote_prefix": self.remote_prefix,
        }


@dataclass(frozen=True)
class StorageConfig:
    local_data_root: str = "data"
    upload_processed_only: bool = True


@dataclass(frozen=True)
class AppConfig:
    r2: R2Config
    storage: StorageConfig


def resolve_s3_endpoint_url(account_id: str, endpoint_url: str) -> str:
    value = endpoint_url.strip()
    if not value:
        return f"https://{account_id}.r2.cloudflarestorage.com"
    if value.endswith(".r2.dev"):
        return f"https://{account_id}.r2.cloudflarestorage.com"
    return value


def mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return ("*" * max(0, len(value) - visible)) + value[-visible:]


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. Copy config.example.yaml to config.yaml and fill in credentials."
        )

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    r2_payload = payload.get("r2") or {}
    storage_payload = payload.get("storage") or {}

    required_fields = [
        "bucket",
        "account_id",
        "access_key_id",
        "secret_access_key",
        "endpoint_url",
    ]
    missing = [field for field in required_fields if not str(r2_payload.get(field, "")).strip()]
    if missing:
        raise ValueError(f"Missing required r2 config fields: {', '.join(missing)}")

    return AppConfig(
        r2=R2Config(
            bucket=str(r2_payload["bucket"]).strip(),
            account_id=str(r2_payload["account_id"]).strip(),
            access_key_id=str(r2_payload["access_key_id"]).strip(),
            secret_access_key=str(r2_payload["secret_access_key"]).strip(),
            endpoint_url=resolve_s3_endpoint_url(
                str(r2_payload["account_id"]).strip(),
                str(r2_payload["endpoint_url"]).strip(),
            ),
            region_name=str(r2_payload.get("region_name", "auto")).strip() or "auto",
            remote_prefix=str(r2_payload.get("remote_prefix", "")).strip().strip("/"),
        ),
        storage=StorageConfig(
            local_data_root=str(storage_payload.get("local_data_root", "data")).strip() or "data",
            upload_processed_only=bool(storage_payload.get("upload_processed_only", True)),
        ),
    )


def create_r2_s3_client(config: R2Config):
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region_name,
        config=BotoConfig(signature_version="s3v4"),
    )
