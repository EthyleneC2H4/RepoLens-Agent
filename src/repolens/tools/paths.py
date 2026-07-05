"""Path-safety helpers shared by repository tools."""

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath


def resolve_within_root(root: Path, relative_path: str) -> Path:
    """Resolve an existing relative path and reject root or symlink escapes."""

    candidate_path = Path(relative_path)
    if candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise ValueError("path must be repository-relative and cannot contain '..'")

    resolved_root = root.expanduser().resolve()
    resolved_candidate = (resolved_root / candidate_path).resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("path resolves outside the repository root") from exc
    return resolved_candidate


def should_ignore(relative_path: PurePosixPath, patterns: tuple[str, ...]) -> bool:
    """Return whether any path component or full relative path matches a pattern."""

    path_text = relative_path.as_posix()
    for pattern in patterns:
        if fnmatch(path_text, pattern) or any(fnmatch(part, pattern) for part in relative_path.parts):
            return True
    return False
