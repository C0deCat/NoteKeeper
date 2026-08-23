"""Authorization, visibility, and campaign locking for queue transitions."""

from notekeeper.application import AccessContext
from notekeeper.application.commands import QueueProcessingJobCommand
from notekeeper.application.errors import AuthorizationError
from notekeeper.application.ports import (
    CampaignRepository,
    JobRepository,
    WorkspaceRepository,
)
from notekeeper.application.results import QueueProcessingJobResult
from notekeeper.domain import ProcessingJobId, WorkspaceRole

from .campaign_mutation_policy import CampaignMutationPolicy
from .lookups import require_campaign, require_job


class GuardedJobQueue:
    def __init__(
        self,
        use_case,
        policy: CampaignMutationPolicy,
        campaign_repository: CampaignRepository,
        job_repository: JobRepository,
        access: AccessContext,
        workspace_repository: WorkspaceRepository | None = None,
    ) -> None:
        self._use_case = use_case
        self._policy = policy
        self._campaign_repository = campaign_repository
        self._job_repository = job_repository
        self._access = access
        self._workspace_repository = workspace_repository

    def execute(self, command: QueueProcessingJobCommand) -> QueueProcessingJobResult:
        role = self._access.role
        if self._workspace_repository is not None:
            membership = self._workspace_repository.membership(
                self._access.workspace_id,
                self._access.actor_user_id,
            )
            if membership is None:
                raise AuthorizationError("workspace access has been revoked")
            role = membership.role
        if role is WorkspaceRole.VIEWER:
            raise AuthorizationError("viewer membership is read-only")
        job = require_job(self._job_repository, ProcessingJobId(command.job_id))
        require_campaign(self._campaign_repository, job.campaign_id)
        with self._policy.queue_transition(job.campaign_id):
            return self._use_case.execute(command)


__all__ = ["GuardedJobQueue"]
