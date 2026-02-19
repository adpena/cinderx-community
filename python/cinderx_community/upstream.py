"""Upstream repository sync and version-tracking helpers."""

from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_REPOS: dict[str, str] = {
    "cinderx": "https://github.com/facebookincubator/cinderx.git",
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PINS_FILE = Path(__file__).resolve().with_name("pins.toml")
HISTORY_ROOT = PROJECT_ROOT / ".cache/upstream/history"
LEGACY_PIN_ROOT = PROJECT_ROOT / ".cache/upstream/pins"


@dataclass(slots=True)
class PinRecord:
    repo_url: str
    commit_sha: str
    clone_timestamp_utc: str
    destination: str
    tags: list[str]


@dataclass(slots=True)
class UpstreamStatus:
    repo: str
    repo_url: str
    destination: Path
    pinned_commit: str | None
    pinned_timestamp_utc: str | None
    pinned_tags: list[str]
    local_commit: str | None
    latest_remote_commit: str | None


class UpstreamError(RuntimeError):
    """Raised when upstream operations fail."""


def resolve_repo_url(repo: str) -> str:
    if repo not in DEFAULT_REPOS:
        known = ", ".join(sorted(DEFAULT_REPOS))
        raise UpstreamError(f"Unknown repo '{repo}'. Known values: {known}")
    return DEFAULT_REPOS[repo]


def _git(args: list[str], cwd: Path | None = None) -> str:
    command = ["git", *args]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise UpstreamError("git is required but was not found in PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or "(no stderr)"
        raise UpstreamError(f"git command failed: {' '.join(command)}\n{stderr}") from exc

    return result.stdout.strip()


def history_path(repo: str) -> Path:
    return HISTORY_ROOT / f"{repo}.jsonl"


def _legacy_pin_path(repo: str) -> Path:
    return LEGACY_PIN_ROOT / f"{repo}.txt"


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _normalize_destination(destination: Path) -> str:
    resolved = destination.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def _load_pins() -> dict[str, PinRecord]:
    if not PINS_FILE.exists():
        return {}
    raw = tomllib.loads(PINS_FILE.read_text(encoding="utf-8"))
    repos = raw.get("repos")
    if not isinstance(repos, dict):
        return {}

    records: dict[str, PinRecord] = {}
    for repo, payload in repos.items():
        if not isinstance(repo, str) or not isinstance(payload, dict):
            continue
        commit = str(payload.get("commit_sha", "")).strip()
        if not commit:
            continue
        tags = payload.get("tags", [])
        normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        default_repo_url = DEFAULT_REPOS.get(repo, "")
        records[repo] = PinRecord(
            repo_url=str(payload.get("repo_url", "")).strip() or default_repo_url,
            commit_sha=commit,
            clone_timestamp_utc=str(payload.get("clone_timestamp_utc", "")).strip()
            or datetime.now(UTC).isoformat(),
            destination=str(payload.get("destination", "")).strip(),
            tags=sorted(set(normalized_tags)),
        )
    return records


def _dump_pins(records: dict[str, PinRecord]) -> str:
    lines = [
        "# Managed by cxc upstream pin. Edit manually with care.",
        "",
        "[repos]",
        "",
    ]
    for repo in sorted(records):
        record = records[repo]
        lines.append(f"[repos.{repo}]")
        lines.append(f'repo_url = "{_toml_escape(record.repo_url)}"')
        lines.append(f'commit_sha = "{_toml_escape(record.commit_sha)}"')
        lines.append(f'clone_timestamp_utc = "{_toml_escape(record.clone_timestamp_utc)}"')
        lines.append(f'destination = "{_toml_escape(record.destination)}"')
        tags = ", ".join(f'"{_toml_escape(tag)}"' for tag in sorted(set(record.tags)))
        lines.append(f"tags = [{tags}]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_pins(records: dict[str, PinRecord]) -> None:
    PINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PINS_FILE.write_text(_dump_pins(records), encoding="utf-8")


def read_pin_record(repo: str) -> PinRecord | None:
    pins = _load_pins()
    record = pins.get(repo)
    if record is not None:
        return record

    legacy_path = _legacy_pin_path(repo)
    if not legacy_path.exists():
        return None
    commit = legacy_path.read_text(encoding="utf-8").strip()
    if not commit:
        return None
    legacy_timestamp = datetime.fromtimestamp(legacy_path.stat().st_mtime, tz=UTC).isoformat()
    return PinRecord(
        repo_url=resolve_repo_url(repo),
        commit_sha=commit,
        clone_timestamp_utc=legacy_timestamp,
        destination="",
        tags=[],
    )


def read_pin(repo: str) -> str | None:
    record = read_pin_record(repo)
    return None if record is None else record.commit_sha


def write_pin(
    repo: str,
    commit: str,
    repo_url: str,
    destination: Path,
    tags: list[str] | None = None,
    clone_timestamp_utc: str | None = None,
) -> None:
    records = _load_pins()
    records[repo] = PinRecord(
        repo_url=repo_url,
        commit_sha=commit,
        clone_timestamp_utc=clone_timestamp_utc or datetime.now(UTC).isoformat(),
        destination=_normalize_destination(destination),
        tags=sorted(set(tags or [])),
    )
    _write_pins(records)


def append_history(repo: str, commit: str, repo_url: str, note: str) -> None:
    record = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "repo": repo,
        "repo_url": repo_url,
        "commit": commit,
        "note": note,
    }
    path = history_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_history(repo: str, limit: int = 20) -> list[dict[str, str]]:
    path = history_path(repo)
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    return records[-limit:]


def latest_remote_head(repo_url: str) -> str | None:
    try:
        raw = _git(["ls-remote", repo_url, "HEAD"])
    except UpstreamError:
        return None

    if not raw:
        return None
    parts = raw.split()
    return parts[0] if parts else None


def local_head(destination: Path) -> str | None:
    git_dir = destination / ".git"
    if not git_dir.exists():
        return None
    try:
        return _git(["rev-parse", "HEAD"], cwd=destination)
    except UpstreamError:
        return None


def ensure_latest_clone(repo: str, destination: Path) -> UpstreamStatus:
    repo_url = resolve_repo_url(repo)
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    if (destination / ".git").exists():
        _git(["fetch", "origin", "--tags", "--prune"], cwd=destination)
    elif destination.exists() and any(destination.iterdir()):
        raise UpstreamError(f"Destination '{destination}' exists and is not a git repository")
    else:
        if destination.exists() and not any(destination.iterdir()):
            destination.rmdir()
        _git(["clone", repo_url, str(destination)])

    latest_commit = latest_remote_head(repo_url)
    if latest_commit:
        _git(["checkout", "--detach", latest_commit], cwd=destination)
        write_pin(
            repo=repo,
            commit=latest_commit,
            repo_url=repo_url,
            destination=destination,
            tags=[],
        )
        append_history(repo, latest_commit, repo_url, "synced-latest-remote-head")

    return upstream_status(repo=repo, destination=destination, repo_url=repo_url)


def pin_upstream(
    repo: str,
    destination: Path,
    commit: str | None = None,
    tags: list[str] | None = None,
) -> UpstreamStatus:
    repo_url = resolve_repo_url(repo)
    destination = destination.resolve()

    resolved_commit = commit
    if resolved_commit is None:
        resolved_commit = local_head(destination)
        if resolved_commit is None:
            raise UpstreamError(
                "Could not determine commit to pin. Clone first or pass --commit explicitly."
            )
    elif (destination / ".git").exists():
        try:
            resolved_commit = _git(["rev-parse", resolved_commit], cwd=destination)
        except UpstreamError:
            # If this isn't a local commit reference, keep user input as-is.
            pass

    write_pin(
        repo=repo,
        commit=resolved_commit,
        repo_url=repo_url,
        destination=destination,
        tags=tags or [],
    )
    append_history(repo, resolved_commit, repo_url, "manual-pin")
    return upstream_status(repo=repo, destination=destination, repo_url=repo_url)


def upstream_status(repo: str, destination: Path, repo_url: str | None = None) -> UpstreamStatus:
    resolved_url = repo_url or resolve_repo_url(repo)
    pin = read_pin_record(repo)
    return UpstreamStatus(
        repo=repo,
        repo_url=resolved_url,
        destination=destination,
        pinned_commit=None if pin is None else pin.commit_sha,
        pinned_timestamp_utc=None if pin is None else pin.clone_timestamp_utc,
        pinned_tags=[] if pin is None else pin.tags,
        local_commit=local_head(destination),
        latest_remote_commit=latest_remote_head(resolved_url),
    )
