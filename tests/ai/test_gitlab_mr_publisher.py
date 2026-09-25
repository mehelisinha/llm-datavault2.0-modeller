"""Tests for the GitLab MR publisher using a stub HTTP client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from dbt_builder.src.utils.gitlab_mr import GitLabMrPublisher


@dataclass
class _StubResponse:
    status_code: int
    text: str = ""
    payload: Any = None

    def json(self) -> Any:
        return self.payload


@dataclass
class _StubHttp:
    """Records calls and serves canned responses by URL + method."""

    responses: dict[tuple[str, str], list[_StubResponse]] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def _respond(self, method: str, url: str) -> _StubResponse:
        queue = self.responses.get((method, url))
        if not queue:
            return _StubResponse(status_code=200, payload={})
        return queue.pop(0)

    def get(self, url, headers=None, params=None):  # noqa: D401
        self.calls.append({"method": "GET", "url": url, "params": params, "headers": headers})
        return self._respond("GET", url)

    def post(self, url, headers=None, params=None, json=None):  # noqa: D401
        self.calls.append(
            {"method": "POST", "url": url, "params": params, "json": json, "headers": headers}
        )
        return self._respond("POST", url)


def _publisher(http: _StubHttp) -> GitLabMrPublisher:
    return GitLabMrPublisher(
        base_url="https://git.example.com",
        token="abc",
        project_id="123",
        default_branch="approved-yaml",
        storage_root_branch="main",
        http_client=http,
    )


_STORAGE_BRANCH_GET = (
    "GET",
    "https://git.example.com/api/v4/projects/123/repository/branches/approved-yaml",
)
_STORAGE_BRANCH_GET_NS = (
    "GET",
    "https://git.example.com/api/v4/projects/group%2Fdwa/repository/branches/approved-yaml",
)


def test_publish_creates_branch_commit_and_mr():
    http = _StubHttp(
        responses={
            _STORAGE_BRANCH_GET: [_StubResponse(status_code=200)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/branches"): [
                _StubResponse(status_code=201)
            ],
            # File doesn't exist → action=create
            (
                "GET",
                "https://git.example.com/api/v4/projects/123/repository/files/"
                + "catalogs%2Fiec%2Flatest.yaml",
            ): [_StubResponse(status_code=404)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/commits"): [
                _StubResponse(status_code=201)
            ],
            ("POST", "https://git.example.com/api/v4/projects/123/merge_requests"): [
                _StubResponse(
                    status_code=201,
                    payload={"web_url": "https://git.example.com/grp/proj/-/merge_requests/42"},
                )
            ],
        }
    )

    pub = _publisher(http)
    url = pub.publish(
        catalog="iec",
        plan_id="abc123",
        version=4,
        rendered_yaml="system: {}\n",
        actor="lead@example.com",
    )

    assert url.endswith("/42")
    commit_call = next(c for c in http.calls if "commits" in c["url"])
    assert commit_call["json"]["actions"][0]["action"] == "create"
    assert commit_call["json"]["actions"][0]["file_path"] == "catalogs/iec/latest.yaml"
    assert "lead@example.com" in commit_call["json"]["commit_message"]
    branch_call = next(c for c in http.calls if c["url"].endswith("/repository/branches"))
    assert branch_call["params"]["branch"] == "dwa/approve/iec/abc123-v4"


def test_publish_uses_update_when_file_exists():
    http = _StubHttp(
        responses={
            _STORAGE_BRANCH_GET: [_StubResponse(status_code=200)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/branches"): [
                _StubResponse(status_code=201)
            ],
            (
                "GET",
                "https://git.example.com/api/v4/projects/123/repository/files/"
                + "catalogs%2Fiec%2Flatest.yaml",
            ): [_StubResponse(status_code=200)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/commits"): [
                _StubResponse(status_code=201)
            ],
            ("POST", "https://git.example.com/api/v4/projects/123/merge_requests"): [
                _StubResponse(status_code=201, payload={"web_url": "x"})
            ],
        }
    )
    pub = _publisher(http)
    pub.publish(catalog="iec", plan_id="p1", version=1, rendered_yaml="y\n", actor="u")
    commit_call = next(c for c in http.calls if "commits" in c["url"])
    assert commit_call["json"]["actions"][0]["action"] == "update"


def test_existing_branch_is_idempotent():
    http = _StubHttp(
        responses={
            _STORAGE_BRANCH_GET: [_StubResponse(status_code=200)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/branches"): [
                _StubResponse(status_code=400, text="Branch already exists")
            ],
            (
                "GET",
                "https://git.example.com/api/v4/projects/123/repository/files/"
                + "catalogs%2Fiec%2Flatest.yaml",
            ): [_StubResponse(status_code=200)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/commits"): [
                _StubResponse(status_code=201)
            ],
            ("POST", "https://git.example.com/api/v4/projects/123/merge_requests"): [
                _StubResponse(status_code=201, payload={"web_url": "ok"})
            ],
        }
    )
    pub = _publisher(http)
    assert pub.publish(catalog="iec", plan_id="p1", version=1, rendered_yaml="y", actor="u") == "ok"


def test_mr_conflict_returns_existing_url():
    http = _StubHttp(
        responses={
            _STORAGE_BRANCH_GET: [_StubResponse(status_code=200)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/branches"): [
                _StubResponse(status_code=201)
            ],
            (
                "GET",
                "https://git.example.com/api/v4/projects/123/repository/files/"
                + "catalogs%2Fiec%2Flatest.yaml",
            ): [_StubResponse(status_code=404)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/commits"): [
                _StubResponse(status_code=201)
            ],
            ("POST", "https://git.example.com/api/v4/projects/123/merge_requests"): [
                _StubResponse(status_code=409, text="conflict")
            ],
            ("GET", "https://git.example.com/api/v4/projects/123/merge_requests"): [
                _StubResponse(
                    status_code=200,
                    payload=[{"web_url": "https://git.example.com/.../merge_requests/7"}],
                )
            ],
        }
    )
    pub = _publisher(http)
    url = pub.publish(catalog="iec", plan_id="p1", version=1, rendered_yaml="y", actor="u")
    assert url.endswith("/merge_requests/7")


def test_branch_create_hard_failure_raises():
    http = _StubHttp(
        responses={
            _STORAGE_BRANCH_GET: [_StubResponse(status_code=200)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/branches"): [
                _StubResponse(status_code=500, text="boom")
            ],
        }
    )
    pub = _publisher(http)
    with pytest.raises(RuntimeError):
        pub.publish(catalog="iec", plan_id="p1", version=1, rendered_yaml="y", actor="u")


def test_namespace_project_id_is_url_encoded():
    http = _StubHttp(
        responses={
            _STORAGE_BRANCH_GET_NS: [_StubResponse(status_code=200)],
            (
                "POST",
                "https://git.example.com/api/v4/projects/group%2Fdwa/repository/branches",
            ): [_StubResponse(status_code=201)],
            (
                "GET",
                "https://git.example.com/api/v4/projects/group%2Fdwa/repository/files/"
                + "catalogs%2Fiec%2Flatest.yaml",
            ): [_StubResponse(status_code=404)],
            (
                "POST",
                "https://git.example.com/api/v4/projects/group%2Fdwa/repository/commits",
            ): [_StubResponse(status_code=201)],
            (
                "POST",
                "https://git.example.com/api/v4/projects/group%2Fdwa/merge_requests",
            ): [_StubResponse(status_code=201, payload={"web_url": "ok"})],
        }
    )
    pub = GitLabMrPublisher(
        base_url="https://git.example.com",
        token="t",
        project_id="group/dwa",
        default_branch="approved-yaml",
        storage_root_branch="main",
        http_client=http,
    )
    assert pub.publish(catalog="iec", plan_id="p1", version=1, rendered_yaml="y", actor="u") == "ok"


def test_refuses_main_as_default_branch():
    with pytest.raises(ValueError, match="main"):
        GitLabMrPublisher(
            base_url="https://git.example.com",
            token="t",
            project_id="123",
            default_branch="main",
        )


def test_refuses_master_as_default_branch():
    with pytest.raises(ValueError, match="master"):
        GitLabMrPublisher(
            base_url="https://git.example.com",
            token="t",
            project_id="123",
            default_branch="master",
        )


def test_storage_branch_is_bootstrapped_when_missing():
    http = _StubHttp(
        responses={
            # Storage branch does not exist yet → publisher creates it from main.
            _STORAGE_BRANCH_GET: [_StubResponse(status_code=404)],
            # Two POSTs to /repository/branches: (a) bootstrap storage branch,
            # (b) create the per-approval feature branch.
            ("POST", "https://git.example.com/api/v4/projects/123/repository/branches"): [
                _StubResponse(status_code=201),
                _StubResponse(status_code=201),
            ],
            (
                "GET",
                "https://git.example.com/api/v4/projects/123/repository/files/"
                + "catalogs%2Fiec%2Flatest.yaml",
            ): [_StubResponse(status_code=404)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/commits"): [
                _StubResponse(status_code=201)
            ],
            ("POST", "https://git.example.com/api/v4/projects/123/merge_requests"): [
                _StubResponse(status_code=201, payload={"web_url": "ok"})
            ],
        }
    )
    pub = _publisher(http)
    assert pub.publish(catalog="iec", plan_id="p1", version=1, rendered_yaml="y", actor="u") == "ok"
    branch_posts = [
        c for c in http.calls
        if c["method"] == "POST" and c["url"].endswith("/repository/branches")
    ]
    assert len(branch_posts) == 2
    # First POST = bootstrap storage branch off main.
    assert branch_posts[0]["params"] == {"branch": "approved-yaml", "ref": "main"}
    # Second POST = feature branch off the storage branch (never off main).
    assert branch_posts[1]["params"]["ref"] == "approved-yaml"
    assert branch_posts[1]["params"]["branch"] == "dwa/approve/iec/p1-v1"
    # MR targets the storage branch.
    mr_post = next(c for c in http.calls if c["method"] == "POST" and c["url"].endswith("/merge_requests"))
    assert mr_post["json"]["target_branch"] == "approved-yaml"


def test_storage_branch_check_only_runs_once_across_calls():
    http = _StubHttp(
        responses={
            _STORAGE_BRANCH_GET: [_StubResponse(status_code=200)],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/branches"): [
                _StubResponse(status_code=201),
                _StubResponse(status_code=201),
            ],
            (
                "GET",
                "https://git.example.com/api/v4/projects/123/repository/files/"
                + "catalogs%2Fiec%2Flatest.yaml",
            ): [
                _StubResponse(status_code=404),
                _StubResponse(status_code=200),
            ],
            ("POST", "https://git.example.com/api/v4/projects/123/repository/commits"): [
                _StubResponse(status_code=201),
                _StubResponse(status_code=201),
            ],
            ("POST", "https://git.example.com/api/v4/projects/123/merge_requests"): [
                _StubResponse(status_code=201, payload={"web_url": "u1"}),
                _StubResponse(status_code=201, payload={"web_url": "u2"}),
            ],
        }
    )
    pub = _publisher(http)
    pub.publish(catalog="iec", plan_id="p1", version=1, rendered_yaml="y", actor="u")
    pub.publish(catalog="iec", plan_id="p2", version=2, rendered_yaml="y", actor="u")
    storage_checks = [c for c in http.calls if c["url"] == _STORAGE_BRANCH_GET[1]]
    assert len(storage_checks) == 1
