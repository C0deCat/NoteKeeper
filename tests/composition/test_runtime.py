import json
from pathlib import Path

from notekeeper.application import (
    CancelProcessingJob,
    ClearFailedJobsForCampaign,
    CreateCampaign,
    CreateProcessingJobForAudioTrack,
    DeleteCampaign,
    DeleteProcessingJob,
    RestartFailedProcessingJob,
    UpdateCampaign,
)
from notekeeper.composition import NoteKeeperSettings, build_runtime


def test_build_runtime_assembles_stage1_use_cases_and_diagnostics(
    tmp_path: Path,
) -> None:
    prompts_file = tmp_path / "recap_prompts.json"
    prompts_file.write_text(
        json.dumps(
            {
                "chunk_recap_prompt": "chunk",
                "combine_chunks_prompt": "combine",
            },
        ),
        encoding="utf-8",
    )

    runtime = build_runtime(
        NoteKeeperSettings(
            storage_root=tmp_path / "artifacts",
            sqlite_path=tmp_path / "notekeeper.sqlite3",
            processing_work_root=tmp_path / "work",
            recap_prompts_file=prompts_file,
            deepseek_api_key="deepseek-secret",
            whisperx_hf_token="hf-secret",
            whisperx_vad_method="pyannote",
        ),
    )

    diagnostics = runtime.diagnostics()

    assert isinstance(runtime.use_cases.create_campaign, CreateCampaign)
    assert isinstance(runtime.use_cases.update_campaign, UpdateCampaign)
    assert isinstance(runtime.use_cases.delete_campaign, DeleteCampaign)
    assert isinstance(
        runtime.use_cases.create_processing_job_for_audio_track,
        CreateProcessingJobForAudioTrack,
    )
    assert isinstance(
        runtime.use_cases.restart_failed_processing_job,
        RestartFailedProcessingJob,
    )
    assert isinstance(
        runtime.use_cases.clear_failed_jobs_for_campaign,
        ClearFailedJobsForCampaign,
    )
    assert isinstance(runtime.use_cases.delete_processing_job, DeleteProcessingJob)
    assert isinstance(runtime.use_cases.cancel_processing_job, CancelProcessingJob)
    assert diagnostics.deepseek_configured is True
    assert diagnostics.huggingface_configured is True
    assert diagnostics.whisperx_vad_method == "pyannote"
    assert "deepseek-secret" not in str(diagnostics)
    assert "hf-secret" not in str(diagnostics)
