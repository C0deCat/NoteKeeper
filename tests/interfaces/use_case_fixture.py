"""Test-only helpers for assembling the grouped use-case facade."""

from notekeeper.application.use_case_facade import (
    ApplicationUseCases,
    CampaignUseCases,
    JobUseCases,
    MediaUseCases,
    ParticipantUseCases,
    RecapUseCases,
    RecordingUseCases,
    SampleUseCases,
    TranscriptUseCases,
)


def application_use_cases_from_flat(**values) -> ApplicationUseCases:
    """Adapt concise legacy-style test fixtures to the grouped facade."""
    queue = values.get("queue_processing_job") or values["run_processing_job"]
    restart = (
        values.get("restart_processing_job")
        or values["restart_failed_processing_job"]
    )
    return ApplicationUseCases(
        campaigns=CampaignUseCases(
            create=values["create_campaign"],
            get=values["get_campaign"],
            list=values["list_campaigns"],
            update=values["update_campaign"],
            delete=values["delete_campaign"],
            sync_folder=values["sync_campaign_folder"],
            get_recap_guidances=values["get_recap_guidances"],
            update_recap_guidances=values["update_recap_guidances"],
        ),
        participants=ParticipantUseCases(
            add=values["add_participant"],
            list=values["list_participants"],
            update=values["update_participant"],
            delete=values["delete_participant"],
        ),
        samples=SampleUseCases(
            add=values["add_voice_sample"],
            list=values["list_voice_samples"],
            update=values.get("update_voice_sample") or values["add_voice_sample"],
            delete=values["delete_voice_sample"],
        ),
        recordings=RecordingUseCases(
            register=values["register_audio_track"],
            list=values["list_audio_tracks"],
            update=values.get("update_audio_track")
            or values["register_audio_track"],
            delete=values.get("delete_audio_track")
            or values["register_audio_track"],
            submit_for_processing=values["submit_recording_for_processing"],
        ),
        jobs=JobUseCases(
            create=values["create_processing_job_for_audio_track"],
            queue=queue,
            restart_failed=values["restart_failed_processing_job"],
            restart=restart,
            clear_failed=values["clear_failed_jobs_for_campaign"],
            delete=values.get("delete_processing_job") or values["get_job_status"],
            cancel=values.get("cancel_processing_job") or values["get_job_status"],
            list_for_campaign=values["list_jobs_for_campaign"],
            get_status=values["get_job_status"],
            review_speaker_mappings=values["review_speaker_mappings"],
        ),
        transcripts=TranscriptUseCases(
            preview_markdown=values["preview_transcript_markdown"],
            export_markdown=values["export_transcript_markdown"],
        ),
        recaps=RecapUseCases(
            generate=values["generate_recap"],
            preview_markdown=values["preview_recap_markdown"],
            export_markdown=values["export_recap_markdown"],
        ),
        media=MediaUseCases(
            inspect_metadata=values["inspect_audio_metadata"],
            inspect_local_file=values["inspect_local_audio_file"],
        ),
    )
