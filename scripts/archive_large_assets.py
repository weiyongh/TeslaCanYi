from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path


DEFAULT_EXTENSIONS = {
    ".asc",
    ".mp3",
    ".m4a",
    ".wav",
    ".flac",
    ".aac",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".webp",
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()


def sha256_stream(stream, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()

    while chunk := stream.read(chunk_size):
        digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive large experiment assets and generate a SHA-256 manifest."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project root to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("archives"),
        help="Archive output directory. Defaults to archives under the project root.",
    )
    parser.add_argument(
        "--min-size-mb",
        type=float,
        default=0,
        help="Only archive matching files at least this large. Defaults to all sizes.",
    )
    parser.add_argument(
        "--compression",
        choices=("stored", "deflated"),
        default="deflated",
        help="stored is faster; deflated attempts compression.",
    )
    parser.add_argument(
        "--delete-source-after-verify",
        action="store_true",
        help=(
            "Delete source files only after the ZIP passes its CRC check and "
            "every archived file passes SHA-256 verification."
        ),
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    output_dir = args.output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = output_dir / f"TeslaCanYi_assets_{timestamp}.zip"
    manifest_path = output_dir / f"TeslaCanYi_assets_{timestamp}.manifest.json"
    min_size = int(args.min_size_mb * 1024 * 1024)

    candidates: list[tuple[Path, int]] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if output_dir == path or output_dir in path.parents:
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() not in DEFAULT_EXTENSIONS:
            continue

        size = path.stat().st_size
        if size >= min_size:
            candidates.append((path, size))

    candidates.sort(key=lambda item: item[0].relative_to(root).as_posix())
    compression = (
        zipfile.ZIP_STORED
        if args.compression == "stored"
        else zipfile.ZIP_DEFLATED
    )

    manifest = {
        "format": 1,
        "project_root_name": root.name,
        "created_at": datetime.now().astimezone().isoformat(),
        "archive": zip_path.name,
        "files": [],
    }

    with zipfile.ZipFile(
        zip_path,
        mode="w",
        compression=compression,
        allowZip64=True,
    ) as archive:
        for path, size in candidates:
            relative_path = path.relative_to(root)
            digest = sha256_file(path)
            archive.write(path, arcname=relative_path.as_posix())
            manifest["files"].append(
                {
                    "path": relative_path.as_posix(),
                    "size": size,
                    "sha256": digest,
                }
            )
            print(f"Archived: {relative_path} ({size / 1024 / 1024:.2f} MiB)")

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.delete_source_after_verify:
        expected = {
            item["path"]: item["sha256"]
            for item in manifest["files"]
        }

        print()
        print("Verifying ZIP before deleting source files...")

        with zipfile.ZipFile(zip_path, mode="r") as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise RuntimeError(
                    f"ZIP CRC verification failed for {bad_member}; "
                    "source files were not deleted."
                )

            archived_names = set(archive.namelist())
            if archived_names != set(expected):
                raise RuntimeError(
                    "ZIP contents do not match the manifest; "
                    "source files were not deleted."
                )

            for relative_name, expected_digest in expected.items():
                with archive.open(relative_name, mode="r") as archived_file:
                    actual_digest = sha256_stream(archived_file)
                if actual_digest != expected_digest:
                    raise RuntimeError(
                        f"ZIP SHA-256 verification failed for {relative_name}; "
                        "source files were not deleted."
                    )

        # Recheck every source before deleting any of them. This prevents a
        # file changed during archiving from being removed.
        for path, _ in candidates:
            relative_name = path.relative_to(root).as_posix()
            if not path.is_file():
                raise RuntimeError(
                    f"Source file disappeared before deletion: {relative_name}; "
                    "no source files were deleted."
                )
            if sha256_file(path) != expected[relative_name]:
                raise RuntimeError(
                    f"Source file changed before deletion: {relative_name}; "
                    "no source files were deleted."
                )

        for path, _ in candidates:
            relative_name = path.relative_to(root)
            path.unlink()
            print(f"Deleted source: {relative_name}")

    print()
    print(f"Files: {len(candidates)}")
    print(f"Archive: {zip_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Archive size: {zip_path.stat().st_size / 1024 / 1024:.2f} MiB")


if __name__ == "__main__":
    main()
