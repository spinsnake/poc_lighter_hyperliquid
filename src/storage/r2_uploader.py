from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from botocore.exceptions import ClientError

from src.storage.r2_config import R2Config, create_r2_s3_client


@dataclass(frozen=True)
class R2UploadResult:
    object_key: str
    uploaded: bool
    skipped_existing: bool
    local_size: int
    remote_size: int | None = None


@dataclass
class R2Uploader:
    config: R2Config
    local_root: Path

    def __post_init__(self) -> None:
        self.local_root = self.local_root.resolve()
        self.client = create_r2_s3_client(self.config)

    def prefixed_object_key(self, object_key: str) -> str:
        relative_key = str(object_key).strip().strip("/")
        if self.config.remote_prefix and relative_key:
            return f"{self.config.remote_prefix}/{relative_key}"
        if self.config.remote_prefix:
            return self.config.remote_prefix
        return relative_key

    def object_key_for(self, path: Path) -> str:
        relative_path = path.resolve().relative_to(self.local_root)
        return self.prefixed_object_key(relative_path.as_posix())

    def extra_args_for(self, path: Path) -> dict[str, str] | None:
        extra_args: dict[str, str] = {}
        content_type, _ = mimetypes.guess_type(path.name)
        if content_type:
            extra_args["ContentType"] = content_type
        return extra_args or None

    def remote_object_size(self, object_key: str) -> int | None:
        try:
            response = self.client.head_object(Bucket=self.config.bucket, Key=object_key)
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = str(error.get("Code", ""))
            status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status_code == 404:
                return None
            raise
        content_length = response.get("ContentLength")
        return int(content_length) if content_length is not None else None

    def remote_object_size_for_key(self, object_key: str) -> int | None:
        return self.remote_object_size(self.prefixed_object_key(object_key))

    def object_exists(self, object_key: str) -> bool:
        return self.remote_object_size_for_key(object_key) is not None

    def verify_bucket_access(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.config.bucket)
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = str(error.get("Code", ""))
            message = str(error.get("Message", "")).strip()
            raise RuntimeError(
                "R2 bucket access failed. Check bucket name, account_id, access_key_id, "
                "secret_access_key, and endpoint_url in config.yaml. "
                f"bucket={self.config.bucket} code={code or 'unknown'} message={message or 'n/a'}"
            ) from exc

    def upload_file(self, path: Path) -> str | None:
        if not path.exists() or not path.is_file():
            return None

        object_key = self.object_key_for(path)
        self.client.upload_file(
            str(path),
            self.config.bucket,
            object_key,
            ExtraArgs=self.extra_args_for(path),
        )
        return object_key

    def upload_path_to_object_key(self, path: Path, object_key: str) -> str | None:
        if not path.exists() or not path.is_file():
            return None

        full_key = self.prefixed_object_key(object_key)
        self.client.upload_file(
            str(path),
            self.config.bucket,
            full_key,
            ExtraArgs=self.extra_args_for(path),
        )
        return full_key

    def upload_file_if_missing(self, path: Path) -> R2UploadResult | None:
        object_key = self.object_key_for(path)
        return self.upload_path_to_object_key_if_missing(path, object_key)

    def upload_path_to_object_key_if_missing(
        self,
        path: Path,
        object_key: str,
    ) -> R2UploadResult | None:
        if not path.exists() or not path.is_file():
            return None

        full_key = self.prefixed_object_key(object_key)
        local_size = int(path.stat().st_size)
        remote_size = self.remote_object_size(full_key)
        if remote_size is not None and remote_size == local_size:
            return R2UploadResult(
                object_key=full_key,
                uploaded=False,
                skipped_existing=True,
                local_size=local_size,
                remote_size=remote_size,
            )

        self.client.upload_file(
            str(path),
            self.config.bucket,
            full_key,
            ExtraArgs=self.extra_args_for(path),
        )
        return R2UploadResult(
            object_key=full_key,
            uploaded=True,
            skipped_existing=False,
            local_size=local_size,
            remote_size=remote_size,
        )

    def upload_fileobj_to_object_key(
        self,
        fileobj: BinaryIO,
        object_key: str,
        *,
        content_type: str | None = None,
    ) -> str:
        full_key = self.prefixed_object_key(object_key)
        extra_args: dict[str, str] | None = None
        if content_type:
            extra_args = {"ContentType": content_type}
        self.client.upload_fileobj(
            fileobj,
            self.config.bucket,
            full_key,
            ExtraArgs=extra_args,
        )
        return full_key

    def upload_files(self, paths: list[Path]) -> list[str]:
        uploaded_keys: list[str] = []
        for path in paths:
            object_key = self.upload_file(path)
            if object_key:
                uploaded_keys.append(object_key)
        return uploaded_keys

    def upload_files_if_missing(self, paths: list[Path]) -> list[R2UploadResult]:
        results: list[R2UploadResult] = []
        for path in paths:
            result = self.upload_file_if_missing(path)
            if result is not None:
                results.append(result)
        return results
