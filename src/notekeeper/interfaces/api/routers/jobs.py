"""Processing-job actions, status, and SSE progress routes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import StreamingResponse

from notekeeper.application import (
    CancelProcessingJobCommand,
    CreateProcessingJobForAudioTrackCommand,
    DeleteProcessingJobCommand,
    GetJobStatusCommand,
    ListJobsForCampaignCommand,
    ManualSpeakerMappingCommand,
    QueueProcessingJobCommand,
    RestartProcessingJobCommand,
    ReviewSpeakerMappingsCommand,
)
from notekeeper.application.results import ProgressEvent
from notekeeper.domain import JobStatus

from ..contracts import ApiRuntime, ApiSession
from ..dependencies import RuntimeDependency, WorkspaceSession
from ..mappers import job_response, progress_response, recording_response
from ..openapi import ERROR_RESPONSES
from ..schemas import (
    ItemsResponse,
    JobResponse,
    RecordingSubmissionResponse,
    RestartJobResponse,
    SpeakerReviewRequest,
)

router = APIRouter(tags=["jobs"])
_WORKSPACE = "/api/v1/workspaces/{workspace_id}"


@router.get(
    _WORKSPACE + "/campaigns/{campaign_id}/jobs",
    response_model=ItemsResponse[JobResponse],
    responses=ERROR_RESPONSES,
    operation_id="list_jobs",
)
def list_jobs(
    campaign_id: str,
    session: WorkspaceSession,
    runtime: RuntimeDependency,
) -> ItemsResponse[JobResponse]:
    result = session.use_cases.jobs.list_for_campaign.execute(
        ListJobsForCampaignCommand(campaign_id=campaign_id)
    )
    return ItemsResponse(
        items=[
            job_response(value, runtime.progress_events.latest(str(value.id)))
            for value in result.jobs
        ]
    )


@router.post(
    _WORKSPACE + "/recordings/{recording_id}/jobs",
    response_model=RecordingSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    operation_id="create_job",
)
def create_job(
    recording_id: str,
    request: Request,
    response: Response,
    session: WorkspaceSession,
) -> RecordingSubmissionResponse:
    result = session.use_cases.jobs.create.execute(
        CreateProcessingJobForAudioTrackCommand(audio_track_id=recording_id)
    )
    response.headers["Location"] = str(
        request.url_for(
            "get_job",
            workspace_id=str(session.access.workspace_id),
            job_id=str(result.job.id),
        )
    )
    return RecordingSubmissionResponse(
        recording=recording_response(result.audio_track),
        job=job_response(result.job),
    )


@router.get(
    _WORKSPACE + "/jobs/{job_id}",
    response_model=JobResponse,
    responses=ERROR_RESPONSES,
    operation_id="get_job",
)
def get_job(
    job_id: str,
    session: WorkspaceSession,
    runtime: RuntimeDependency,
) -> JobResponse:
    result = session.use_cases.jobs.get_status.execute(
        GetJobStatusCommand(job_id=job_id)
    )
    return job_response(result.job, runtime.progress_events.latest(job_id))


@router.delete(
    _WORKSPACE + "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
    operation_id="delete_job",
)
def delete_job(job_id: str, session: WorkspaceSession) -> Response:
    session.use_cases.jobs.delete.execute(DeleteProcessingJobCommand(job_id=job_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    _WORKSPACE + "/jobs/{job_id}/queue",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERROR_RESPONSES,
    operation_id="queue_job",
)
def queue_job(
    job_id: str,
    request: Request,
    response: Response,
    session: WorkspaceSession,
) -> JobResponse:
    result = session.use_cases.jobs.queue.execute(
        QueueProcessingJobCommand(job_id=job_id)
    )
    response.headers["Location"] = str(
        request.url_for(
            "get_job",
            workspace_id=str(session.access.workspace_id),
            job_id=job_id,
        )
    )
    return job_response(result.job)


@router.post(
    _WORKSPACE + "/jobs/{job_id}/cancel",
    response_model=JobResponse,
    responses=ERROR_RESPONSES,
    operation_id="cancel_job",
)
def cancel_job(job_id: str, session: WorkspaceSession) -> JobResponse:
    result = session.use_cases.jobs.cancel.execute(
        CancelProcessingJobCommand(job_id=job_id)
    )
    return job_response(result.job)


@router.post(
    _WORKSPACE + "/jobs/{job_id}/restart",
    response_model=RestartJobResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    operation_id="restart_job",
)
def restart_job(
    job_id: str,
    request: Request,
    response: Response,
    session: WorkspaceSession,
) -> RestartJobResponse:
    result = session.use_cases.jobs.restart.execute(
        RestartProcessingJobCommand(job_id=job_id)
    )
    response.headers["Location"] = str(
        request.url_for(
            "get_job",
            workspace_id=str(session.access.workspace_id),
            job_id=str(result.job.id),
        )
    )
    return RestartJobResponse(
        source_job_id=str(result.source_job.id),
        job=job_response(result.job),
    )


@router.post(
    _WORKSPACE + "/jobs/{job_id}/speaker-review",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERROR_RESPONSES,
    operation_id="review_speakers",
)
def review_speakers(
    job_id: str,
    payload: SpeakerReviewRequest,
    request: Request,
    response: Response,
    session: WorkspaceSession,
) -> JobResponse:
    result = session.use_cases.jobs.review_speaker_mappings.execute(
        ReviewSpeakerMappingsCommand(
            job_id=job_id,
            mappings=tuple(
                ManualSpeakerMappingCommand(
                    anonymous_label=value.anonymous_label,
                    participant_id=value.participant_id,
                    named_label=value.named_label,
                    confidence=value.confidence,
                )
                for value in payload.mappings
            ),
        )
    )
    response.headers["Location"] = str(
        request.url_for(
            "get_job",
            workspace_id=str(session.access.workspace_id),
            job_id=job_id,
        )
    )
    return job_response(result.job)


@router.get(
    _WORKSPACE + "/jobs/{job_id}/events",
    responses={
        **ERROR_RESPONSES,
        200: {"content": {"text/event-stream": {}}, "description": "Job events"},
    },
    operation_id="stream_job_events",
)
async def stream_job_events(
    job_id: str,
    request: Request,
    session: WorkspaceSession,
    runtime: RuntimeDependency,
) -> StreamingResponse:
    initial = session.use_cases.jobs.get_status.execute(
        GetJobStatusCommand(job_id=job_id)
    ).job
    return StreamingResponse(
        _event_stream(request, session, runtime, initial),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _event_stream(
    request: Request,
    session: ApiSession,
    runtime: ApiRuntime,
    initial_job,
) -> AsyncIterator[str]:
    job_id = str(initial_job.id)
    queue: asyncio.Queue[ProgressEvent] = asyncio.Queue(maxsize=1)
    loop = asyncio.get_running_loop()

    def listener(event: ProgressEvent) -> None:
        def enqueue_latest() -> None:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

        loop.call_soon_threadsafe(enqueue_latest)

    unsubscribe = runtime.progress_events.subscribe(job_id, listener)
    try:
        yield _sse("status", job_response(initial_job).model_dump_json())
        if _settled(initial_job.status):
            return
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(
                    queue.get(),
                    timeout=runtime.sse_heartbeat_seconds,
                )
            except TimeoutError:
                yield ": heartbeat\n\n"
                continue
            yield _sse("progress", progress_response(event).model_dump_json())
            if event.kind.is_terminal:
                current = session.use_cases.jobs.get_status.execute(
                    GetJobStatusCommand(job_id=job_id)
                ).job
                yield _sse("status", job_response(current).model_dump_json())
                return
    finally:
        unsubscribe()


def _settled(job_status: JobStatus) -> bool:
    return job_status in {
        JobStatus.WAITING_FOR_REVIEW,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELED,
    }


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


__all__ = ["router"]
