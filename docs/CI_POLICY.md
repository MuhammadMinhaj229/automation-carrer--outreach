# ACIOS CI policy

## Pull requests

The ACIOS Local Core CI workflow runs for pull requests targeting **any base branch**.

This is intentional. ACIOS uses stacked pull requests while a multi-part safety repair is reviewed. GitHub's pull_request.branches filter matches the PR's **target/base branch**, not the source/head branch. Restricting that filter to main and master silently skips PRs whose base is another feature branch.

Do not add a base-branch allowlist or denylist to the pull_request trigger without replacing this coverage with an equivalent explicit policy and regression test.

## Pushes

Push-triggered CI remains limited to main, master, refactor/** and security/**. This avoids running the full suite on every topic-branch push while keeping CI active on maintained integration branches.

## What CI verifies

The workflow runs the Python 3.11 and 3.12 test matrix, the private runtime-file and secret/session-state guard, Ruff syntax/correctness checks, the complete pytest suite, Bandit static security review, and pip-audit against core requirements.

A missing workflow run is **not** a passing check. Review the current head commit's Actions result before treating a PR as validated. Stacked PRs still need their own successful head-commit run.

The workflow uses pull_request, not pull_request_target, and has read-only repository contents permission. Do not add secrets, mailbox access, or outbound-email actions to this validation workflow.

## Regression test

tests/test_ci_workflow_config.py parses the workflow with PyYAML's BaseLoader so YAML 1.1 boolean handling of the word on does not hide the GitHub Actions event key. It asserts that pull-request target-branch filters stay absent and that push scope remains limited.

Reference: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
