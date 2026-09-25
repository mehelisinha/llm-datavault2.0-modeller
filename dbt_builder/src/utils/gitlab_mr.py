"""GitLab Merge-Request publisher for approved YAML metadata.

Approved YAMLs are committed to a long-lived **storage branch** (default
``approved-yaml``) via a per-approval feature branch + MR. ``main`` /
``master`` are never written to or targeted — the publisher refuses to
start if ``default_branch`` is one of those names. The storage branch is
bootstrapped from ``storage_root_branch`` (read-only ref) the first time
it is needed and is reused thereafter.

REST endpoints used (GitLab REST API v4)::

    GET    /api/v4/projects/:id/repository/branches/:branch        (existence)
    POST   /api/v4/projects/:id/repository/branches                (create branch)
    POST   /api/v4/projects/:id/repository/commits                 (commit file)
    POST   /api/v4/projects/:id/merge_requests                     (open MR)

All requests carry the PRIVATE-TOKEN header. The publisher does not merge
the MR — that step is reserved for the human reviewer with merge rights.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable
from urllib.parse import quote

_log = logging.getLogger(__name__)

# Branches the publisher must never target or write to. The safety guard
# below raises in ``__init__`` if ``default_branch`` matches one of these.
_FORBIDDEN_TARGET_BRANCHES: frozenset[str] = frozenset({"main", "master"})


@runtime_checkable
class GitLabPublisher(Protocol):
    """Minimum surface the service facade depends on."""

    def publish(
        self,
        *,
        catalog: str,
        plan_id: str,
        version: int,
        rendered_yaml: str,
        actor: str,
    ) -> str:
        """Open an MR carrying *rendered_yaml*; return the MR web URL."""
        ...


class GitLabMrPublisher:
    """Concrete :class:`GitLabPublisher` backed by GitLab REST API v4.

    Path / branch / title strings are rendered from format templates so a
    single configuration covers every catalog without code changes.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        project_id: str,
        default_branch: str = "approved-yaml",
        storage_root_branch: str = "main",
        yaml_path_template: str = "catalogs/{catalog}/latest.yaml",
        branch_template: str = "dwa/approve/{catalog}/{plan_id}-v{version}",
        mr_title_template: str = "[DWA] Approve {catalog} metadata v{version} ({plan_id})",
        http_client=None,  # type: ignore[no-untyped-def]  # httpx.Client; injected for tests
        timeout_seconds: float = 15.0,
    ) -> None:
        if not all([base_url, token, project_id]):
            raise ValueError("GitLabMrPublisher requires base_url, token and project_id.")
        if default_branch in _FORBIDDEN_TARGET_BRANCHES:
            raise ValueError(
                f"GitLabMrPublisher refuses default_branch={default_branch!r}: "
                f"approved YAML MRs must target a dedicated storage branch "
                f"(e.g. 'approved-yaml'), never {sorted(_FORBIDDEN_TARGET_BRANCHES)}."
            )
        self._base = base_url.rstrip("/")
        self._token = token
        # The GitLab project id may be a numeric id or URL-encoded namespace path.
        # We do not pre-encode here so callers can pass either form unchanged.
        self._project = project_id
        self._default_branch = default_branch
        self._storage_root_branch = storage_root_branch
        self._yaml_path_template = yaml_path_template
        self._branch_template = branch_template
        self._mr_title_template = mr_title_template
        self._timeout = timeout_seconds
        self._client = http_client  # lazy-built when None to keep import-time cheap
        self._storage_branch_verified = False

    def _http(self):  # type: ignore[no-untyped-def]
        if self._client is not None:
            return self._client
        import httpx  # noqa: PLC0415 — lazy

        self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def _project_path(self) -> str:
        # numeric ids pass through; namespace paths get URL-encoded once.
        if self._project.isdigit() or "%2F" in self._project:
            return self._project
        return quote(self._project, safe="")

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self._token, "Accept": "application/json"}

    def publish(
        self,
        *,
        catalog: str,
        plan_id: str,
        version: int,
        rendered_yaml: str,
        actor: str,
    ) -> str:
        ctx = {"catalog": catalog, "plan_id": plan_id, "version": int(version)}
        branch = self._branch_template.format(**ctx)
        file_path = self._yaml_path_template.format(**ctx)
        mr_title = self._mr_title_template.format(**ctx)

        project = self._project_path()
        base = f"{self._base}/api/v4/projects/{project}"
        http = self._http()

        # 0) Bootstrap the storage branch on first use. Idempotent: if the
        #    branch already exists we skip the create. The storage branch is
        #    the ONLY target of feature-branch MRs; main / master are never
        #    touched.
        self._ensure_storage_branch(base)

        # 1) Create the feature branch off the storage branch.
        #    Idempotency: if the branch already exists GitLab returns 400 with
        #    message "Branch already exists" — we treat that as success because
        #    the same plan_id+version can legitimately be re-approved.
        resp = http.post(
            f"{base}/repository/branches",
            headers=self._headers(),
            params={"branch": branch, "ref": self._default_branch},
        )
        if resp.status_code not in (201, 400):
            raise RuntimeError(
                f"GitLab create-branch failed: HTTP {resp.status_code} {resp.text[:200]}"
            )

        # 2) Commit the YAML. Use action='update' if the file exists, else 'create'.
        action = "update" if self._file_exists(base, branch, file_path) else "create"
        commit_msg = f"DWA approve {catalog} v{version} ({plan_id}) by {actor}"
        resp = http.post(
            f"{base}/repository/commits",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "branch": branch,
                "commit_message": commit_msg,
                "actions": [
                    {
                        "action": action,
                        "file_path": file_path,
                        "content": rendered_yaml,
                    }
                ],
            },
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"GitLab commit failed: HTTP {resp.status_code} {resp.text[:200]}"
            )

        # 3) Open the MR. If one is already open for the same source branch
        #    GitLab returns 409 — we surface its existing URL instead of erroring.
        resp = http.post(
            f"{base}/merge_requests",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "source_branch": branch,
                "target_branch": self._default_branch,
                "title": mr_title,
                "remove_source_branch": True,
                "description": (
                    f"Generated by DWA approval pipeline.\n\n"
                    f"- catalog: `{catalog}`\n"
                    f"- plan_id: `{plan_id}`\n"
                    f"- version: `{version}`\n"
                    f"- approver: `{actor}`\n"
                ),
            },
        )
        if resp.status_code in (200, 201):
            return str(resp.json().get("web_url", ""))
        if resp.status_code == 409:
            existing = self._find_open_mr(base, branch)
            if existing:
                return existing
        raise RuntimeError(
            f"GitLab open-MR failed: HTTP {resp.status_code} {resp.text[:200]}"
        )

    def _ensure_storage_branch(self, base: str) -> None:
        if self._storage_branch_verified:
            return
        encoded = quote(self._default_branch, safe="")
        resp = self._http().get(
            f"{base}/repository/branches/{encoded}",
            headers=self._headers(),
        )
        if resp.status_code == 200:
            self._storage_branch_verified = True
            return
        if resp.status_code != 404:
            raise RuntimeError(
                f"GitLab check-storage-branch failed: HTTP {resp.status_code} {resp.text[:200]}"
            )
        # 404 — bootstrap from the read-only root branch.
        create = self._http().post(
            f"{base}/repository/branches",
            headers=self._headers(),
            params={"branch": self._default_branch, "ref": self._storage_root_branch},
        )
        # 400 = already exists (race); both 201 and 400 are acceptable.
        if create.status_code not in (201, 400):
            raise RuntimeError(
                f"GitLab bootstrap storage branch {self._default_branch!r} failed: "
                f"HTTP {create.status_code} {create.text[:200]}"
            )
        self._storage_branch_verified = True

    def _file_exists(self, base: str, branch: str, file_path: str) -> bool:
        encoded = quote(file_path, safe="")
        resp = self._http().get(
            f"{base}/repository/files/{encoded}",
            headers=self._headers(),
            params={"ref": branch},
        )
        return resp.status_code == 200

    def _find_open_mr(self, base: str, branch: str) -> str | None:
        resp = self._http().get(
            f"{base}/merge_requests",
            headers=self._headers(),
            params={"state": "opened", "source_branch": branch},
        )
        if resp.status_code != 200:
            return None
        items = resp.json()
        if items:
            return str(items[0].get("web_url", "")) or None
        return None


__all__ = ["GitLabMrPublisher", "GitLabPublisher"]
