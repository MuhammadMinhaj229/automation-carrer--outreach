from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def _load_workflow():
    # BaseLoader keeps the GitHub Actions key "on" as a string.
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_ci_runs_for_pull_requests_targeting_stacked_branches():
    workflow = _load_workflow()
    pull_request = workflow["on"]["pull_request"]

    # No target-branch allowlist/denylist: PRs targeting another feature branch
    # must receive the same CI as PRs targeting main.
    if isinstance(pull_request, dict):
        assert "branches" not in pull_request
        assert "branches-ignore" not in pull_request
    else:
        assert pull_request is None


def test_push_ci_remains_limited_to_maintained_branch_families():
    workflow = _load_workflow()

    assert workflow["on"]["push"]["branches"] == [
        "main",
        "master",
        "refactor/**",
        "security/**",
    ]
