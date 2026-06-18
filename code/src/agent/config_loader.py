import json
import os
from functools import lru_cache

from github import GithubException, UnknownObjectException
from agent.tools.github_tool import gh
from agent.utils.logger import get_logger

log = get_logger(__name__)

_CONFIG_FILENAME = "review_config.json"

DEFAULT_CONFIG = {
    "min_severity": "LOW",
    "skip_files": [],
    "max_files": int(os.getenv("PR_MAX_FILES", "50")),
    "max_patch_size": int(os.getenv("PR_MAX_PATCH_SIZE", "500000")),
}


def _fetch_repo_config(repo_name: str) -> dict:
    try:
        repo = gh.get_repo(repo_name)
        contents = repo.get_contents(_CONFIG_FILENAME)
        raw = contents.decoded_content.decode("utf-8") if isinstance(contents.decoded_content, bytes) else contents.decoded_content
        config = json.loads(raw)
        log.info("Loaded per-repo config from %s/%s", repo_name, _CONFIG_FILENAME)
        return config
    except UnknownObjectException:
        log.debug("No %s found in %s, using defaults", _CONFIG_FILENAME, repo_name)
        return {}
    except (GithubException, json.JSONDecodeError, OSError) as e:
        log.warning("Failed to load %s from %s: %s", _CONFIG_FILENAME, repo_name, e)
        return {}


@lru_cache(maxsize=32)
def load_config(repo_name: str) -> dict:
    file_config = _fetch_repo_config(repo_name)
    merged = dict(DEFAULT_CONFIG)
    merged.update(file_config)
    merged["max_files"] = int(os.getenv("PR_MAX_FILES", str(merged["max_files"])))
    merged["max_patch_size"] = int(os.getenv("PR_MAX_PATCH_SIZE", str(merged["max_patch_size"])))
    return merged


def matches_skip_pattern(filename: str, patterns: list) -> bool:
    import fnmatch
    return any(fnmatch.fnmatch(filename, p) for p in patterns)
