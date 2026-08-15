"""Speaker review submissions scoped through processing jobs."""

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import JobRepository, SpeakerReviewSubmissionRepository
from notekeeper.application.results import SpeakerReviewSubmission
from notekeeper.domain import ProcessingJobId

from .user_campaign_access import UserCampaignAccess


class UserScopedSpeakerReviewSubmissionRepository(SpeakerReviewSubmissionRepository):
    def __init__(
        self,
        repository: SpeakerReviewSubmissionRepository,
        jobs: JobRepository,
        access: UserCampaignAccess,
    ) -> None:
        self._repository = repository
        self._jobs = jobs
        self._access = access

    def get(self, job_id: ProcessingJobId) -> SpeakerReviewSubmission | None:
        if not self._allows_job(job_id):
            return None
        return self._repository.get(job_id)

    def save(self, submission: SpeakerReviewSubmission) -> None:
        if not self._allows_job(submission.job_id):
            raise NotFoundError(f"processing job {submission.job_id} was not found")
        self._repository.save(submission)

    def delete(self, job_id: ProcessingJobId) -> None:
        if not self._allows_job(job_id):
            raise NotFoundError(f"processing job {job_id} was not found")
        self._repository.delete(job_id)

    def _allows_job(self, job_id: ProcessingJobId) -> bool:
        job = self._jobs.get(job_id)
        return job is not None and self._access.allows(job.campaign_id)


__all__ = ["UserScopedSpeakerReviewSubmissionRepository"]
