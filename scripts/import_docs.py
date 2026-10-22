"""Import a verified FastLED/dox publication into the website deployment."""

import argparse
import hashlib
import json
import os
import re
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode

UPSTREAM = "https://fastled.github.io/dox/publication.json"
CURRENT = "https://fastled.io/docs/publication.json"
MAX_ARCHIVE = 2 * 1024**3
MAX_EXTRACTED = 10 * 1024**3


def validate_manifest(manifest: dict) -> None:
    try:
        generation = manifest["generation"]
        release = manifest["release"]
        archive = manifest["archive"]
        valid = (
            manifest["schema_version"] == 1
            and isinstance(generation, str)
            and re.fullmatch(r"[0-9]+-[0-9]+", generation)
            and release["generation"] == generation
            and type(release["id"]) is int
            and release["id"] > 0
            and re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+", release["tag_name"])
            and re.fullmatch(r"[0-9a-f]{40}", release["source_sha"])
            and isinstance(release["doxygen_version"], str)
            and release["doxygen_version"]
            and archive["url"]
            == f"https://github.com/FastLED/dox/releases/download/docs-{generation}/docs.tar.gz"
            and re.fullmatch(r"[0-9a-f]{64}", archive["sha256"])
            and type(archive["size"]) is int
            and 0 < archive["size"] <= MAX_ARCHIVE
        )
    except (KeyError, TypeError):
        valid = False
    if not valid:
        raise ValueError("Invalid documentation publication manifest")


def fetch_manifest(url: str, *, missing_ok: bool = False) -> dict | None:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(65537)
    except urllib.error.HTTPError as error:
        if error.code == 404 and missing_ok:
            return None
        raise
    if len(data) > 65536:
        raise ValueError("Documentation manifest exceeds 64 KiB")
    manifest = json.loads(data)
    validate_manifest(manifest)
    return manifest


def check_publication(upstream: str, current: str) -> tuple[dict, bool]:
    manifest = fetch_manifest(upstream)
    try:
        deployed = fetch_manifest(current, missing_ok=True)
    except (ValueError, OSError) as error:
        # The verified upstream can repair a missing or corrupt deployed marker.
        print(
            f"Deployed publication is unreadable; importing verified upstream: {error}"
        )
        deployed = None
    return manifest, manifest != deployed


def download_archive(manifest: dict, destination: Path) -> None:
    validate_manifest(manifest)
    archive = manifest["archive"]
    size = 0
    digest = hashlib.sha256()
    with urllib.request.urlopen(archive["url"], timeout=60) as response:
        with destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > archive["size"]:
                    raise ValueError("Documentation download exceeds manifest size")
                digest.update(chunk)
                output.write(chunk)
    if size != archive["size"] or digest.hexdigest() != archive["sha256"]:
        raise ValueError("Documentation download checksum or size mismatch")


def stage_archive(archive: Path, site: Path, manifest: dict) -> None:
    validate_manifest(manifest)
    if archive.stat().st_size != manifest["archive"]["size"]:
        raise ValueError("Documentation archive size mismatch")
    with archive.open("rb") as source:
        if (
            hashlib.file_digest(source, "sha256").hexdigest()
            != manifest["archive"]["sha256"]
        ):
            raise ValueError("Documentation archive checksum mismatch")
    site.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="dox-import-", dir=site.parent
    ) as temporary:
        staging = Path(temporary) / "docs"
        staging.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            total = 0
            for member in members:
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in member.name
                    or not (member.isfile() or member.isdir())
                    or (member.isfile() and not path.parts)
                ):
                    raise ValueError(
                        f"Unsafe documentation archive entry: {member.name}"
                    )
                if member.isfile():
                    total += member.size
                    if total > MAX_EXTRACTED:
                        raise ValueError(
                            "Documentation archive expands beyond Pages size limit"
                        )
            tar.extractall(staging, members=members, filter="data")
        actual_release = json.loads((staging / "release.json").read_text())
        if actual_release != manifest["release"]:
            raise ValueError("Archive release metadata does not match publication")
        for required in ("index.html", "annotated.html", "search/search.js"):
            path = staging / required
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Missing required documentation output: {required}")
        (staging / "publication.json").write_text(json.dumps(manifest, indent=2) + "\n")
        destination = site / "docs"
        backup = Path(temporary) / "previous"
        if destination.exists():
            destination.rename(backup)
        try:
            staging.rename(destination)
        except OSError:
            if backup.exists():
                backup.rename(destination)
            raise
    print(
        f"Staged FastLED {actual_release['tag_name']} publication {manifest['generation']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "import"))
    parser.add_argument("--site", type=Path, default=Path("_site"))
    args = parser.parse_args()
    if args.command == "check":
        query = urlencode(
            {
                "run": os.environ["GITHUB_RUN_ID"],
                "attempt": os.environ["GITHUB_RUN_ATTEMPT"],
            }
        )
        manifest, changed = check_publication(
            UPSTREAM + "?" + query, CURRENT + "?" + query
        )
        docs_only = os.environ["GITHUB_EVENT_NAME"] == "schedule" or (
            os.environ.get("DOCS_ONLY") == "true"
        )
        outputs = {
            "publication": json.dumps(manifest, separators=(",", ":")),
            "changed": str(changed).lower(),
            "deploy": str(changed or not docs_only).lower(),
            "release_id": str(manifest["release"]["id"]),
            "tag": manifest["release"]["tag_name"],
        }
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            for key, value in outputs.items():
                output.write(f"{key}={value}\n")
        print(
            f"Upstream publication {manifest['generation']}; update required: {outputs['deploy']}"
        )
    else:
        manifest = json.loads(os.environ["PUBLICATION_JSON"])
        validate_manifest(manifest)
        with tempfile.TemporaryDirectory(prefix="dox-download-") as temporary:
            archive = Path(temporary) / "docs.tar.gz"
            download_archive(manifest, archive)
            stage_archive(archive, args.site, manifest)


if __name__ == "__main__":
    main()
