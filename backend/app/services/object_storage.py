import re
import tarfile
import uuid
import zipfile
from datetime import timedelta
from functools import lru_cache
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz")
_SAFE_FILE_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")


@lru_cache
def get_minio_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def ensure_bucket_exists() -> None:
    client = get_minio_client()
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def validate_archive_filename(filename: str | None) -> str:
    if not filename:
        raise ValueError("File name is required")
    lowered = filename.lower()
    if not any(lowered.endswith(suffix) for suffix in ARCHIVE_SUFFIXES):
        raise ValueError("Only .zip, .tar, .tar.gz, .tgz files are supported")
    return filename


def _normalized_path_parts(path: str) -> list[str]:
    normalized = path.replace("\\", "/").strip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized:
        return []
    parts = [part for part in normalized.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise ValueError("Invalid archive path")
    return parts


def _is_ignored_archive_entry(parts: list[str]) -> bool:
    lowered_parts = [part.lower() for part in parts]
    if lowered_parts[0] == "__macosx":
        return True
    if lowered_parts[-1] == ".ds_store":
        return True
    if any(part.startswith("._") for part in parts):
        return True
    return False


def validate_archive_contains_skill_md(*, filename: str, file_bytes: bytes) -> str:
    rule_message = (
        "Archive must contain exactly one top-level directory and exactly one "
        "SKILL.md file (case-insensitive)"
    )
    lowered = filename.lower()
    try:
        if lowered.endswith(".zip"):
            with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
                members = [(entry.filename, entry.is_dir()) for entry in archive.infolist()]
        else:
            with tarfile.open(fileobj=BytesIO(file_bytes), mode="r:*") as archive:
                members = [(member.name, member.isdir()) for member in archive.getmembers()]
    except (zipfile.BadZipFile, tarfile.TarError, OSError, EOFError) as exc:
        raise ValueError("Invalid or corrupted archive file") from exc

    top_level_dirs: set[str] = set()
    skill_md_count = 0

    for path, is_dir in members:
        parts = _normalized_path_parts(path)
        if not parts:
            continue
        if _is_ignored_archive_entry(parts):
            continue

        top_level_dirs.add(parts[0])

        if not is_dir and len(parts) == 1:
            raise ValueError(rule_message)

        if not is_dir and parts[-1].lower() == "skill.md":
            skill_md_count += 1

    if len(top_level_dirs) != 1 or skill_md_count != 1:
        raise ValueError(rule_message)

    root_dir = next(iter(top_level_dirs))
    if len(root_dir) > 255:
        raise ValueError("Top-level directory name exceeds 255 characters")
    return root_dir


def sanitize_filename(filename: str) -> str:
    sanitized = _SAFE_FILE_CHARS.sub("_", filename).strip("._")
    return sanitized or "archive.zip"


def build_skill_object_name(skill_id: uuid.UUID, filename: str) -> str:
    safe_name = sanitize_filename(filename)
    unique_name = f"{uuid.uuid4().hex}-{safe_name}"
    return f"skills/{skill_id}/{unique_name}"


def upload_skill_file(*, object_name: str, file_bytes: bytes, content_type: str) -> None:
    ensure_bucket_exists()
    get_minio_client().put_object(
        settings.MINIO_BUCKET,
        object_name,
        data=BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=content_type,
    )


def delete_skill_file(object_name: str) -> None:
    try:
        get_minio_client().remove_object(settings.MINIO_BUCKET, object_name)
    except S3Error as exc:
        if exc.code not in {"NoSuchKey", "NoSuchObject", "NoSuchVersion"}:
            raise


def get_skill_download_url(object_name: str) -> str:
    return get_minio_client().presigned_get_object(
        settings.MINIO_BUCKET,
        object_name,
        expires=timedelta(seconds=settings.SKILL_DOWNLOAD_URL_EXPIRE_SECONDS),
    )


def build_project_minio_url(
    *, presigned_url: str, scheme: str, host: str, nginx_prefix: str = "/minio"
) -> str:
    parsed = urlsplit(presigned_url)
    path = parsed.path or "/"
    prefix = nginx_prefix if nginx_prefix.startswith("/") else f"/{nginx_prefix}"
    rewritten_path = f"{prefix}{path}"
    return urlunsplit((scheme, host, rewritten_path, parsed.query, ""))
