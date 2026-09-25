"""AI-aware factory for the GitLab MR publisher.

Returns ``None`` when GitLab settings are not fully configured. Callers
treat ``None`` as "publishing disabled" — the approval still completes
and the YAML still lands in the storage backend, the MR step is just
skipped.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dbt_builder.src.utils.gitlab_mr import GitLabMrPublisher, GitLabPublisher

if TYPE_CHECKING:
    from dbt_builder.src.ai.settings import AISettings

_log = logging.getLogger(__name__)


def make_gitlab_publisher(settings: AISettings) -> GitLabPublisher | None:
    base_url = getattr(settings, "gitlab_base_url", None)
    token = getattr(settings, "gitlab_token", None)
    project_id = getattr(settings, "gitlab_project_id", None)
    if not all([base_url, token, project_id]):
        _log.debug("make_gitlab_publisher: settings incomplete → publisher disabled")
        return None

    token_value = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token)
    return GitLabMrPublisher(
        base_url=str(base_url),
        token=token_value,
        project_id=str(project_id),
        default_branch=getattr(settings, "gitlab_default_branch", "approved-yaml"),
        storage_root_branch=getattr(settings, "gitlab_storage_root_branch", "main"),
        yaml_path_template=getattr(
            settings, "gitlab_yaml_path_template", "catalogs/{catalog}/latest.yaml"
        ),
        branch_template=getattr(
            settings, "gitlab_branch_template", "dwa/approve/{catalog}/{plan_id}-v{version}"
        ),
        mr_title_template=getattr(
            settings,
            "gitlab_mr_title_template",
            "[DWA] Approve {catalog} metadata v{version} ({plan_id})",
        ),
    )


__all__ = ["GitLabMrPublisher", "GitLabPublisher", "make_gitlab_publisher"]
