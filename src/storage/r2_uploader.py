from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

from src.storage.r2_config import R2Config, create_r2_s3_client


@dataclass
class R2Uploader:
    config: R2Config
    local_root: Path

    def __post_init__(self) -> None:
        self.local_root = self.local_root.resolve()
        self.client = create_r2_s3_client(self.config)

    def object_key_for(self, path: Path) -> str:
        relative_path = path.resolve().relative_to(self.local_root)
        relative_key = relative_path.as_posix()
        if self.config.remote_prefix:
            return f"{self.config.remote_prefix}/{relative_key}"
        return relative_key

    def upload_file(self, path: Path) -> str | None:
        if not path.exists() or not path.is_file():
            return None

        object_key = self.object_key_for(path)
        extra_args: dict[str, str] = {}
        content_type, _ = mimetypes.guess_type(path.name)
        if content_type:
            extra_args["ContentType"] = content_type

        self.client.upload_file(
            str(path),
            self.config.bucket,
            object_key,
            ExtraArgs=extra_args or None,
        )
        return object_key

    def upload_files(self, paths: list[Path]) -> list[str]:
        uploaded_keys: list[str] = []
        for path in paths:
            object_key = self.upload_file(path)
            if object_key:
                uploaded_keys.append(object_key)
        return uploaded_keys
