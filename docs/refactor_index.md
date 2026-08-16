# Refactoring index

This file tracks the exhaustive review of every application file under `src/notekeeper`.

Status legend:

- [ ] pending review
- [x] reviewed; refactored where needed

Review completion means the file was checked for unused code and imports, clarity and size, error-handling complexity, package/facade hygiene, and architectural dependency direction.

## Verification log

- Baseline (2026-08-09): `pytest` — 280 passed, 1 pre-existing timing-sensitive TUI failure (`test_tui_keeps_progress_subscription_for_review_continuation`).
- Baseline (2026-08-09): architectural import scan — no forbidden direct dependencies from `domain` or `application`.
- Baseline (2026-08-09): direct `pyright` launcher does not resolve the project's installed Textual packages; rerun through the project interpreter during interface review.
- Domain (2026-08-09): `pytest tests/domain` — 46 passed; Ruff — clean; Pyright — clean.
- Application ports (2026-08-09): application import tests — 2 passed; Ruff — clean; Pyright — clean.
- Application commands/results (2026-08-09): import and progress tests — 5 passed; Ruff — clean; Pyright — clean.
- Application use cases and facade (2026-08-09): `pytest tests/application` — 72 passed; Ruff — clean; Pyright — clean.
- Infrastructure cleanup (2026-08-09): cleanup tests — 8 passed; Ruff — clean after unused-import removal; Pyright — clean.
- Infrastructure DeepSeek (2026-08-09): DeepSeek tests — 9 passed; Ruff — clean; Pyright — clean with project interpreter.
- Infrastructure FFmpeg (2026-08-09): FFmpeg tests — 6 passed; Ruff and Pyright — clean.
- Infrastructure filesystem (2026-08-09): filesystem/integration tests — 21 passed; Ruff and Pyright — clean after unused-import removal.
- Infrastructure runtime (2026-08-09): runtime/dashboard tests — 10 passed; Ruff and Pyright — clean.
- Infrastructure speaker mapping/tokenization (2026-08-09): focused tests — 9 passed; Ruff and Pyright — clean.
- Infrastructure SQLite (2026-08-09): repository/smoke tests — 10 passed; Ruff and Pyright — clean.
- Infrastructure WhisperX (2026-08-09): WhisperX tests — 10 passed; Ruff and Pyright — clean.
- Infrastructure full section (2026-08-09): `pytest tests/infrastructure` — 81 passed; Ruff and Pyright — clean.
- Composition (2026-08-09): `pytest tests/composition` — 24 passed; Ruff and Pyright — clean.
- TUI structural split (2026-08-09): `pytest tests/interfaces/test_tui.py` — 44 passed; Ruff and Pyright — clean.
- Interfaces full section (2026-08-09): `pytest tests/interfaces` — 56 passed; Ruff and Pyright — clean.
- Global static audit (2026-08-09): architectural import scan — clean; Ruff and Pyright across `src/notekeeper` — clean; every current source file is present in this index and `docs/file_map.md`.
- Final verification (2026-08-09): `pytest` — 281 passed; Ruff import/unused checks across `src` and `tests` — clean; Pyright across `src/notekeeper` — clean. The baseline TUI timing test failed once during the first full run, then passed both in isolation and in the repeated full suite.

## Application files (221)

### `(package root)`

- [x] `src/notekeeper/__init__.py`

### `application`

- [x] `src/notekeeper/application/ports/events.py`
- [x] `src/notekeeper/application/ports/processing.py`
- [x] `src/notekeeper/application/ports/recaps.py`
- [x] `src/notekeeper/application/ports/repositories.py`
- [x] `src/notekeeper/application/ports/runtime.py`
- [x] `src/notekeeper/application/ports/storage.py`
- [x] `src/notekeeper/application/__init__.py`
- [x] `src/notekeeper/application/commands/__init__.py`
- [x] `src/notekeeper/application/errors.py`
- [x] `src/notekeeper/application/ports/__init__.py`
- [x] `src/notekeeper/application/results/__init__.py`
- [x] `src/notekeeper/application/use_cases/__init__.py`
- [x] `src/notekeeper/application/use_cases/_recaps.py`
- [x] `src/notekeeper/application/use_cases/campaigns/__init__.py`
- [x] `src/notekeeper/application/use_cases/campaigns/add_participant_to_campaign.py`
- [x] `src/notekeeper/application/use_cases/campaigns/add_voice_sample.py`
- [x] `src/notekeeper/application/use_cases/campaigns/create_campaign.py`
- [x] `src/notekeeper/application/use_cases/campaigns/delete_audio_track.py`
- [x] `src/notekeeper/application/use_cases/campaigns/delete_campaign.py`
- [x] `src/notekeeper/application/use_cases/campaigns/delete_participant.py`
- [x] `src/notekeeper/application/use_cases/campaigns/delete_voice_sample.py`
- [x] `src/notekeeper/application/use_cases/campaigns/get_campaign.py`
- [x] `src/notekeeper/application/use_cases/campaigns/get_recap_guidances.py`
- [x] `src/notekeeper/application/use_cases/campaigns/list_audio_tracks.py`
- [x] `src/notekeeper/application/use_cases/campaigns/list_campaigns.py`
- [x] `src/notekeeper/application/use_cases/campaigns/list_participants.py`
- [x] `src/notekeeper/application/use_cases/campaigns/list_voice_samples.py`
- [x] `src/notekeeper/application/use_cases/campaigns/register_audio_track.py`
- [x] `src/notekeeper/application/use_cases/campaigns/sync_campaign_folder.py`
- [x] `src/notekeeper/application/use_cases/campaigns/update_audio_track.py`
- [x] `src/notekeeper/application/use_cases/campaigns/update_campaign.py`
- [x] `src/notekeeper/application/use_cases/campaigns/update_participant.py`
- [x] `src/notekeeper/application/use_cases/campaigns/update_recap_guidances.py`
- [x] `src/notekeeper/application/use_cases/campaigns/update_voice_sample.py`
- [x] `src/notekeeper/application/use_cases/campaigns/utils/__init__.py`
- [x] `src/notekeeper/application/use_cases/campaigns/utils/finders.py`
- [x] `src/notekeeper/application/use_cases/campaigns/utils/jobs.py`
- [x] `src/notekeeper/application/use_cases/export/__init__.py`
- [x] `src/notekeeper/application/use_cases/export/_markdown.py`
- [x] `src/notekeeper/application/use_cases/export/export_recap_markdown.py`
- [x] `src/notekeeper/application/use_cases/export/export_transcript_markdown.py`
- [x] `src/notekeeper/application/use_cases/export/preview_recap_markdown.py`
- [x] `src/notekeeper/application/use_cases/export/preview_transcript_markdown.py`
- [x] `src/notekeeper/application/use_cases/media/__init__.py`
- [x] `src/notekeeper/application/use_cases/media/inspect_audio_metadata.py`
- [x] `src/notekeeper/application/use_cases/media/inspect_local_audio_file.py`
- [x] `src/notekeeper/application/use_cases/processing/__init__.py`
- [x] `src/notekeeper/application/use_cases/processing/cancel_processing_job.py`
- [x] `src/notekeeper/application/use_cases/processing/clear_failed_jobs_for_campaign.py`
- [x] `src/notekeeper/application/use_cases/processing/create_processing_job_for_audio_track.py`
- [x] `src/notekeeper/application/use_cases/processing/delete_processing_job.py`
- [x] `src/notekeeper/application/use_cases/processing/generate_recap.py`
- [x] `src/notekeeper/application/use_cases/processing/get_job_status.py`
- [x] `src/notekeeper/application/use_cases/processing/job_transitions.py`
- [x] `src/notekeeper/application/use_cases/processing/list_jobs_for_campaign.py`
- [x] `src/notekeeper/application/use_cases/processing/mapping_records.py`
- [x] `src/notekeeper/application/use_cases/processing/progress.py`
- [x] `src/notekeeper/application/use_cases/processing/progress_outcomes.py`
- [x] `src/notekeeper/application/use_cases/processing/queue_processing_job.py`
- [x] `src/notekeeper/application/use_cases/processing/restart_failed_processing_job.py` (removed: unused compatibility-only module)
- [x] `src/notekeeper/application/use_cases/processing/restart_processing_job.py`
- [x] `src/notekeeper/application/use_cases/processing/review_speaker_mappings.py`
- [x] `src/notekeeper/application/use_cases/processing/run_processing_job.py`
- [x] `src/notekeeper/application/use_cases/processing/submit_recording_for_processing.py`
- [x] `src/notekeeper/application/use_cases/utils/__init__.py`
- [x] `src/notekeeper/application/use_cases/utils/artifact_cleanup.py`
- [x] `src/notekeeper/application/use_cases/utils/audio_sources.py`
- [x] `src/notekeeper/application/use_cases/utils/campaign_mutation_policy.py`
- [x] `src/notekeeper/application/use_cases/utils/guarded_campaign_mutation.py`
- [x] `src/notekeeper/application/use_cases/utils/lookups.py`

### `composition`

- [x] `src/notekeeper/composition/__init__.py`
- [x] `src/notekeeper/composition/factory.py`
- [x] `src/notekeeper/composition/worker.py`
- [x] `src/notekeeper/composition/job_capacity.py`
- [x] `src/notekeeper/composition/job_pipeline.py`
- [x] `src/notekeeper/composition/main.py`
- [x] `src/notekeeper/infrastructure/runtime/jobs/process_execution_registry.py`
- [x] `src/notekeeper/infrastructure/runtime/jobs/process_job_executor.py`
- [x] `src/notekeeper/infrastructure/runtime/jobs/process_message_writer.py`
- [x] `src/notekeeper/infrastructure/runtime/jobs/process_tree.py`
- [x] `src/notekeeper/composition/runtime.py`
- [x] `src/notekeeper/composition/settings.py`
- [x] `src/notekeeper/composition/use_cases.py`

### `domain`

- [x] `src/notekeeper/domain/__init__.py`
- [x] `src/notekeeper/domain/enums.py`
- [x] `src/notekeeper/domain/errors.py`
- [x] `src/notekeeper/domain/ids.py`
- [x] `src/notekeeper/domain/models/__init__.py`
- [x] `src/notekeeper/domain/models/audio_track.py`
- [x] `src/notekeeper/domain/models/campaign.py`
- [x] `src/notekeeper/domain/models/participant.py`
- [x] `src/notekeeper/domain/models/processing_job.py`
- [x] `src/notekeeper/domain/models/recap.py`
- [x] `src/notekeeper/domain/models/transcript.py`
- [x] `src/notekeeper/domain/models/voice_sample.py`
- [x] `src/notekeeper/domain/services/__init__.py`
- [x] `src/notekeeper/domain/services/_speaker_mapping_helpers.py`
- [x] `src/notekeeper/domain/services/add_audio_track.py`
- [x] `src/notekeeper/domain/services/add_participant.py`
- [x] `src/notekeeper/domain/services/add_voice_sample.py`
- [x] `src/notekeeper/domain/services/apply_speaker_mappings.py`
- [x] `src/notekeeper/domain/services/campaign_readiness.py`
- [x] `src/notekeeper/domain/services/processing_job_rules.py`
- [x] `src/notekeeper/domain/services/remove_audio_track.py`
- [x] `src/notekeeper/domain/services/remove_participant.py`
- [x] `src/notekeeper/domain/services/remove_voice_sample.py`
- [x] `src/notekeeper/domain/services/speaker_mapping_issues.py`
- [x] `src/notekeeper/domain/services/transcript_validation.py`
- [x] `src/notekeeper/domain/services/update_audio_track.py`
- [x] `src/notekeeper/domain/services/update_participant.py`
- [x] `src/notekeeper/domain/services/update_voice_sample.py`
- [x] `src/notekeeper/domain/services/utils/__init__.py`
- [x] `src/notekeeper/domain/services/utils/replace_member.py`
- [x] `src/notekeeper/domain/validation.py`
- [x] `src/notekeeper/domain/value_objects/__init__.py`
- [x] `src/notekeeper/domain/value_objects/artifact_ref.py`
- [x] `src/notekeeper/domain/value_objects/audio_metadata.py`
- [x] `src/notekeeper/domain/value_objects/pipeline_warning.py`
- [x] `src/notekeeper/domain/value_objects/progress_bar.py`
- [x] `src/notekeeper/domain/value_objects/speaker_label.py`
- [x] `src/notekeeper/domain/value_objects/speaker_mapping.py`
- [x] `src/notekeeper/domain/value_objects/time_range.py`

### `infrastructure`

- [x] `src/notekeeper/infrastructure/__init__.py`
- [x] `src/notekeeper/infrastructure/cleanup/__init__.py`
- [x] `src/notekeeper/infrastructure/cleanup/failed_job_cleaner.py` (removed: unused compatibility-only module)
- [x] `src/notekeeper/infrastructure/cleanup/job_cleaner.py`
- [x] `src/notekeeper/infrastructure/cleanup/transient_audio_cleaner.py`
- [x] `src/notekeeper/infrastructure/cleanup/utils/__init__.py`
- [x] `src/notekeeper/infrastructure/cleanup/utils/path_removal.py`
- [x] `src/notekeeper/infrastructure/deepseek/__init__.py`
- [x] `src/notekeeper/infrastructure/deepseek/generator.py`
- [x] `src/notekeeper/infrastructure/deepseek/interfaces.py`
- [x] `src/notekeeper/infrastructure/deepseek/local_request_logger.py`
- [x] `src/notekeeper/infrastructure/deepseek/noop_request_logger.py`
- [x] `src/notekeeper/infrastructure/deepseek/openai_client.py`
- [x] `src/notekeeper/infrastructure/deepseek/utils/__init__.py`
- [x] `src/notekeeper/infrastructure/deepseek/utils/prompts.py`
- [x] `src/notekeeper/infrastructure/errors.py`
- [x] `src/notekeeper/infrastructure/ffmpeg/__init__.py`
- [x] `src/notekeeper/infrastructure/ffmpeg/processor.py`
- [x] `src/notekeeper/infrastructure/ffmpeg/recording_normalizer.py`
- [x] `src/notekeeper/infrastructure/ffmpeg/utils/__init__.py`
- [x] `src/notekeeper/infrastructure/ffmpeg/utils/manifests.py`
- [x] `src/notekeeper/infrastructure/ffmpeg/utils/process.py`
- [x] `src/notekeeper/infrastructure/filesystem/__init__.py`
- [x] `src/notekeeper/infrastructure/filesystem/metadata.py`
- [x] `src/notekeeper/infrastructure/filesystem/prepared_audio_manifest_store.py`
- [x] `src/notekeeper/infrastructure/filesystem/recap_guidances.py`
- [x] `src/notekeeper/infrastructure/filesystem/scanner.py`
- [x] `src/notekeeper/infrastructure/filesystem/source_metadata.py`
- [x] `src/notekeeper/infrastructure/filesystem/storage.py`
- [x] `src/notekeeper/infrastructure/filesystem/utils/__init__.py`
- [x] `src/notekeeper/infrastructure/filesystem/utils/audio_metadata.py`
- [x] `src/notekeeper/infrastructure/filesystem/utils/audio_probe.py`
- [x] `src/notekeeper/infrastructure/filesystem/utils/checksum.py`
- [x] `src/notekeeper/infrastructure/filesystem/utils/paths.py`
- [x] `src/notekeeper/infrastructure/runtime/__init__.py`
- [x] `src/notekeeper/infrastructure/runtime/campaign_mutation_guard.py`
- [x] `src/notekeeper/infrastructure/runtime/dashboard_event_hub.py`
- [x] `src/notekeeper/infrastructure/runtime/event_publishing_campaign_repository.py`
- [x] `src/notekeeper/infrastructure/runtime/event_publishing_job_cleaner.py`
- [x] `src/notekeeper/infrastructure/runtime/event_publishing_job_repository.py`
- [x] `src/notekeeper/infrastructure/runtime/mutation_guarding_campaign_repository.py`
- [x] `src/notekeeper/infrastructure/runtime/persisted_progress_event_hub.py`
- [x] `src/notekeeper/infrastructure/runtime/progress_event_hub.py`
- [x] `src/notekeeper/infrastructure/runtime/progress_tracker_factory.py`
- [x] `src/notekeeper/infrastructure/runtime/progress_tracker.py`
- [x] `src/notekeeper/infrastructure/runtime/system_clock.py`
- [x] `src/notekeeper/infrastructure/runtime/uuid_generator.py`
- [x] `src/notekeeper/infrastructure/speaker_mapping/__init__.py`
- [x] `src/notekeeper/infrastructure/speaker_mapping/identifier.py`
- [x] `src/notekeeper/infrastructure/sqlite/__init__.py`
- [x] `src/notekeeper/infrastructure/sqlite/audio_track_repository.py`
- [x] `src/notekeeper/infrastructure/sqlite/campaign_repository.py`
- [x] `src/notekeeper/infrastructure/sqlite/database.py`
- [x] `src/notekeeper/infrastructure/sqlite/job_repository.py`
- [x] `src/notekeeper/infrastructure/sqlite/participant_repository.py`
- [x] `src/notekeeper/infrastructure/sqlite/progress_event_snapshot_store.py`
- [x] `src/notekeeper/infrastructure/sqlite/recap_repository.py`
- [x] `src/notekeeper/infrastructure/sqlite/schema.py`
- [x] `src/notekeeper/infrastructure/sqlite/speaker_mapping_repository.py`
- [x] `src/notekeeper/infrastructure/sqlite/speaker_review_submission_repository.py`
- [x] `src/notekeeper/infrastructure/sqlite/transcript_repository.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/__init__.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/payload_storage.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/queries.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/row_mappers.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/serialization.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/common_serialization.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/metadata_serialization.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/recap_serialization.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/transcript_serialization.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/warnings_serialization.py`
- [x] `src/notekeeper/infrastructure/sqlite/utils/write_helpers.py`
- [x] `src/notekeeper/infrastructure/sqlite/voice_sample_repository.py`
- [x] `src/notekeeper/infrastructure/tokenization/__init__.py`
- [x] `src/notekeeper/infrastructure/tokenization/tokenizer.py`
- [x] `src/notekeeper/infrastructure/whisperx/__init__.py`
- [x] `src/notekeeper/infrastructure/whisperx/interfaces.py`
- [x] `src/notekeeper/infrastructure/whisperx/payload_store.py`
- [x] `src/notekeeper/infrastructure/whisperx/runner.py`
- [x] `src/notekeeper/infrastructure/whisperx/stages.py`
- [x] `src/notekeeper/infrastructure/whisperx/transcriber.py`
- [x] `src/notekeeper/infrastructure/whisperx/utils/__init__.py`
- [x] `src/notekeeper/infrastructure/whisperx/utils/json_payloads.py`
- [x] `src/notekeeper/infrastructure/whisperx/utils/segments.py`
- [x] `src/notekeeper/infrastructure/whisperx/utils/speechbrain_compat.py`

### `interfaces`

- [x] `src/notekeeper/interfaces/__init__.py`
- [x] `src/notekeeper/interfaces/cli/__init__.py`
- [x] `src/notekeeper/interfaces/cli/campaign_app.py`
- [x] `src/notekeeper/interfaces/cli/cli.py`
- [x] `src/notekeeper/interfaces/cli/common.py`
- [x] `src/notekeeper/interfaces/cli/diagnostics_app.py`
- [x] `src/notekeeper/interfaces/cli/job_app.py`
- [x] `src/notekeeper/interfaces/cli/participant_app.py`
- [x] `src/notekeeper/interfaces/cli/progress.py`
- [x] `src/notekeeper/interfaces/cli/recap_app.py`
- [x] `src/notekeeper/interfaces/cli/recap_prompts_app.py`
- [x] `src/notekeeper/interfaces/cli/recording_app.py`
- [x] `src/notekeeper/interfaces/cli/review_app.py`
- [x] `src/notekeeper/interfaces/cli/sample_app.py`
- [x] `src/notekeeper/interfaces/cli/transcript_app.py`
- [x] `src/notekeeper/interfaces/contracts.py`
- [x] `src/notekeeper/interfaces/tui/__init__.py`
- [x] `src/notekeeper/interfaces/tui/audio_file_explorer_screen.py`
- [x] `src/notekeeper/interfaces/tui/campaign_app.py`
- [x] `src/notekeeper/interfaces/tui/campaign_deletion_screen.py`
- [x] `src/notekeeper/interfaces/tui/campaign_management_screen.py`
- [x] `src/notekeeper/interfaces/tui/campaign_settings_screen.py`
- [x] `src/notekeeper/interfaces/tui/clear_failed_jobs_screen.py`
- [x] `src/notekeeper/interfaces/tui/common.py`
- [x] `src/notekeeper/interfaces/tui/dashboard_messages.py`
- [x] `src/notekeeper/interfaces/tui/dashboard_progress.py`
- [x] `src/notekeeper/interfaces/tui/dashboard_refresh.py`
- [x] `src/notekeeper/interfaces/tui/dashboard_selection.py`
- [x] `src/notekeeper/interfaces/tui/diagnostics_app.py`
- [x] `src/notekeeper/interfaces/tui/identifier_data_table.py`
- [x] `src/notekeeper/interfaces/tui/job_action_confirmation_screen.py`
- [x] `src/notekeeper/interfaces/tui/job_app.py`
- [x] `src/notekeeper/interfaces/tui/object_action_confirmation_screen.py`
- [x] `src/notekeeper/interfaces/tui/participant_app.py`
- [x] `src/notekeeper/interfaces/tui/preview_app.py`
- [x] `src/notekeeper/interfaces/tui/recap_app.py`
- [x] `src/notekeeper/interfaces/tui/recap_prompt_editor_screen.py`
- [x] `src/notekeeper/interfaces/tui/recording_app.py`
- [x] `src/notekeeper/interfaces/tui/remove_voice_sample_screen.py`
- [x] `src/notekeeper/interfaces/tui/rename_screen.py`
- [x] `src/notekeeper/interfaces/tui/review_app.py`
- [x] `src/notekeeper/interfaces/tui/sample_app.py`
- [x] `src/notekeeper/interfaces/tui/styles.tcss`
- [x] `src/notekeeper/interfaces/tui/transcript_app.py`
- [x] `src/notekeeper/interfaces/tui/tui.py`
