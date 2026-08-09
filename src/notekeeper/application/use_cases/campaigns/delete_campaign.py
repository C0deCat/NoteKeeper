"""Delete campaign use case."""

from notekeeper.application.commands import DeleteCampaignCommand
from notekeeper.application.errors import InvalidOperationError
from notekeeper.application.ports import CampaignArtifactStorage, CampaignRepository
from notekeeper.application.results import DeleteCampaignResult
from notekeeper.application.use_cases.utils import (
    CampaignMutationPolicy,
    _require_campaign,
)
from notekeeper.domain import CampaignId


class DeleteCampaign:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        artifact_storage: CampaignArtifactStorage | None = None,
        mutation_policy: CampaignMutationPolicy | None = None,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._artifact_storage = artifact_storage
        self._mutation_policy = mutation_policy

    def execute(self, command: DeleteCampaignCommand) -> DeleteCampaignResult:
        campaign_id = CampaignId(command.campaign_id)
        context = (
            self._mutation_policy.mutation(campaign_id)
            if self._mutation_policy is not None
            else _null_context()
        )
        with context:
            _require_campaign(self._campaign_repository, campaign_id)
            if command.delete_files:
                if self._artifact_storage is None:
                    raise InvalidOperationError("campaign file deletion is not available")
                self._artifact_storage.delete_campaign(campaign_id)
            self._campaign_repository.delete(campaign_id)
        return DeleteCampaignResult(campaign_id=command.campaign_id)


def _null_context():
    from contextlib import nullcontext

    return nullcontext()
