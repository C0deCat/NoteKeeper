"""Shared immutable dependencies for focused use-case builders."""

from dataclasses import dataclass

from notekeeper.application import AccessContext
from notekeeper.application.ports import JobManager, ProgressTrackerFactory
from notekeeper.application.use_cases.utils import CampaignMutationPolicy

from ..factory import LocalServices
from ..repositories import WorkspaceRepositories


@dataclass(frozen=True, slots=True)
class UseCaseWiringContext:
    services: LocalServices
    repositories: WorkspaceRepositories
    progress_tracker_factory: ProgressTrackerFactory
    job_manager: JobManager
    mutation_policy: CampaignMutationPolicy
    access: AccessContext


__all__ = ["UseCaseWiringContext"]
