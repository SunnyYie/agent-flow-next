from __future__ import annotations

import argparse
import json
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib import error, parse, request

CDN_UPLOAD_URL = "https://growth-bi-service-fe.in.taou.com/upload/cdn/"
MAX_FILE_BYTES = 1024 * 1024
DEFAULT_QUALITY = 0.92
DEFAULT_TIMEOUT = 30.0
SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".ico",
}


@dataclass(frozen=True)
class UploadCandidate:
    path: Path
    content_type: str
    size_bytes: int


def collect_upload_candidates(path: str | Path) -> tuple[list[UploadCandidate], list[dict[str, str]]]:
    root = Path(path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"path not found: {root}")

    ready: list[UploadCandidate] = []
    rejected: list[dict[str, str]] = []
    for file_path in _iter_image_files(root):
        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            continue

        size_bytes = file_path.stat().st_size
        if size_bytes > MAX_FILE_BYTES:
            rejected.append(
                {
                    "name": file_path.name,
                    "status": "rejected",
                    "reason": "file size exceeds 1MB limit",
                }
            )
            continue

        ready.append(
            UploadCandidate(
                path=file_path,
                content_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
                size_bytes=size_bytes,
            )
        )

    ready.sort(key=lambda item: item.path.name.lower())
    rejected.sort(key=lambda item: item["name"].lower())
    return ready, rejected


def upload_images(
    path: str | Path,
    *,
    quality: float = DEFAULT_QUALITY,
    timeout: float = DEFAULT_TIMEOUT,
    upload_file: Callable[[Path, float, float], str] | None = None,
) -> str:
    if not 0.8 <= quality <= 1.0:
        raise ValueError("quality must be between 0.8 and 1.0")

    ready, rejected = collect_upload_candidates(path)
    uploader = upload_file or _upload_single_file
    results: dict[str, dict[str, str]] = {}

    for item in ready:
        try:
            cdn_url = uploader(item.path, quality, timeout)
            results[item.path.name] = {
                "name": item.path.name,
                "status": "uploaded",
                "cdn_url": cdn_url,
            }
        except Exception as exc:  # pragma: no cover - error path is still observable via results
            results[item.path.name] = {
                "name": item.path.name,
                "status": "failed",
                "reason": str(exc),
            }

    for item in rejected:
        results[item["name"]] = item

    payload = {
        "path": str(Path(path).expanduser()),
        "quality": quality,
        "results": results,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _iter_image_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return [path for path in root.rglob("*") if path.is_file()]


def _upload_single_file(path: Path, quality: float, timeout: float) -> str:
    boundary = f"agentflow-{uuid.uuid4().hex}"
    payload = _build_multipart_payload(path, quality, boundary)
    req = request.Request(
        CDN_UPLOAD_URL,
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as exc:  # pragma: no cover - network path
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"upload failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:  # pragma: no cover - network path
        raise RuntimeError(f"upload failed: {exc.reason}") from exc

    return _extract_cdn_url(body)


def _build_multipart_payload(path: Path, quality: float, boundary: str) -> bytes:
    line_break = b"\r\n"
    quality_value = format(quality, ".2f").rstrip("0").rstrip(".")
    file_bytes = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    chunks = [
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="quality"',
        b"",
        quality_value.encode("utf-8"),
        f"--{boundary}".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"'
        ).encode("utf-8"),
        f"Content-Type: {content_type}".encode("utf-8"),
        b"",
        file_bytes,
        f"--{boundary}--".encode("utf-8"),
        b"",
    ]
    return line_break.join(chunks)


def _extract_cdn_url(body: str) -> str:
    text = body.strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"upload succeeded but response was not JSON or URL: {text}") from exc

    url = _find_url_in_payload(payload)
    if not url:
        raise RuntimeError(f"upload succeeded but no CDN url found in response: {text}")
    return url


def _find_url_in_payload(payload: object) -> str | None:
    if isinstance(payload, str):
        if payload.startswith("http://") or payload.startswith("https://"):
            return payload
        return None

    if isinstance(payload, dict):
        for key in ("cdn_url", "cdnUrl", "url", "link"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        for value in payload.values():
            found = _find_url_in_payload(value)
            if found:
                return found
        return None

    if isinstance(payload, list):
        for item in payload:
            found = _find_url_in_payload(item)
            if found:
                return found
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch upload images to CDN and print JSON results.")
    parser.add_argument("path", help="image file or directory to upload")
    parser.add_argument("--quality", type=float, default=DEFAULT_QUALITY, help="upload quality between 0.8 and 1.0")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="request timeout in seconds")
    args = parser.parse_args(argv)

    print(upload_images(args.path, quality=args.quality, timeout=args.timeout))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
