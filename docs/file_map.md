# Project file map

This map describes the current production tree under `src/notekeeper`. Dependency direction is `interfaces/composition -> application -> domain`; infrastructure implements application ports and is wired only by composition.

## Package root

- `src/notekeeper/__init__.py` — Explicit public facade for the top-level package.

## `domain`

Pure business model: entities, value objects, domain errors, validation, and deterministic domain services. It has no dependencies on outer layers.

- `src/notekeeper/domain/__init__.py` — Explicit public facade for `domain`.
- `src/notekeeper/domain/enums.py` — Domain enums.
- `src/notekeeper/domain/errors.py` — Domain exceptions.
- `src/notekeeper/domain/ids.py` — Typed domain identifiers.
- `src/notekeeper/domain/validation.py` — Internal validation helpers for domain objects.

### `domain/models`

Business entities and immutable aggregate data.

- `src/notekeeper/domain/models/__init__.py` — Explicit public facade for `domain/models`.
- `src/notekeeper/domain/models/audio_track.py` — Audio track entity.
- `src/notekeeper/domain/models/campaign.py` — Campaign entity.
- `src/notekeeper/domain/models/participant.py` — Participant entity.
- `src/notekeeper/domain/models/processing_job.py` — Processing job entity with an immutable effective-settings snapshot.
- `src/notekeeper/domain/models/recap.py` — Recap entities.
- `src/notekeeper/domain/models/settings.py` — Immutable workspace, campaign, user-preference, settings-catalog, and processing-snapshot DTOs.
- `src/notekeeper/domain/models/transcript.py` — Transcript entities.
- `src/notekeeper/domain/models/user.py` — Authenticated user entity and built-in root identity.
- `src/notekeeper/domain/models/voice_sample.py` — Voice sample entity.
- `src/notekeeper/domain/models/workspace.py` — Workspace and membership entities.

### `domain/services`

Deterministic business calculations spanning domain objects.

- `src/notekeeper/domain/services/__init__.py` — Explicit public facade for `domain/services`.
- `src/notekeeper/domain/services/_speaker_mapping_helpers.py` — Shared speaker mapping service helpers.
- `src/notekeeper/domain/services/add_audio_track.py` — Audio track campaign service.
- `src/notekeeper/domain/services/add_participant.py` — Participant campaign service.
- `src/notekeeper/domain/services/add_voice_sample.py` — Voice sample campaign service.
- `src/notekeeper/domain/services/apply_speaker_mappings.py` — Speaker mapping application service.
- `src/notekeeper/domain/services/campaign_readiness.py` — Campaign readiness service.
- `src/notekeeper/domain/services/processing_job_rules.py` — Business rules for processing-job lifecycle actions.
- `src/notekeeper/domain/services/remove_audio_track.py` — Audio track removal campaign service.
- `src/notekeeper/domain/services/remove_participant.py` — Participant removal campaign service.
- `src/notekeeper/domain/services/remove_voice_sample.py` — Voice sample removal campaign service.
- `src/notekeeper/domain/services/speaker_mapping_issues.py` — Speaker mapping issue detection service.
- `src/notekeeper/domain/services/transcript_validation.py` — Transcript validation service.
- `src/notekeeper/domain/services/update_audio_track.py` — Audio track update campaign service.
- `src/notekeeper/domain/services/update_participant.py` — Participant update campaign service.
- `src/notekeeper/domain/services/update_voice_sample.py` — Voice sample update campaign service.

### `domain/services/utils`

- `src/notekeeper/domain/services/utils/__init__.py` — Explicit public facade for `domain/services/utils`.
- `src/notekeeper/domain/services/utils/replace_member.py` — Tuple member replacement helper.

### `domain/value_objects`

Validated small immutable domain values.

- `src/notekeeper/domain/value_objects/__init__.py` — Explicit public facade for `domain/value_objects`.
- `src/notekeeper/domain/value_objects/artifact_ref.py` — Artifact reference value object.
- `src/notekeeper/domain/value_objects/audio_metadata.py` — Audio metadata value object.
- `src/notekeeper/domain/value_objects/pipeline_warning.py` — Pipeline warning value object.
- `src/notekeeper/domain/value_objects/progress_bar.py` — Generic immutable progress-bar value object.
- `src/notekeeper/domain/value_objects/speaker_label.py` — Speaker label value object.
- `src/notekeeper/domain/value_objects/speaker_mapping.py` — Speaker mapping value object.
- `src/notekeeper/domain/value_objects/time_range.py` — Time range value object.


## `application`

Use-case orchestration and abstract ports. It depends on the domain, but not on concrete storage, APIs, subprocesses, or UI frameworks.

- `src/notekeeper/application/__init__.py` — Explicit public facade for `application`.
- `src/notekeeper/application/access_context.py` — Immutable actor context and explicit repository scopes.
- `src/notekeeper/application/authenticator.py` — Stateless authentication service.
- `src/notekeeper/application/errors.py` — Application-layer errors.
- `src/notekeeper/application/settings_service.py` — Role-aware workspace, campaign, membership, and user settings orchestration.
- `src/notekeeper/application/use_case_facade.py` — Grouped application use-case facade.

### `application/commands`

- `src/notekeeper/application/commands/__init__.py` — Explicit public facade for `application/commands`.

### `application/ports`

Abstract boundaries implemented by infrastructure.

- `src/notekeeper/application/ports/__init__.py` — Explicit public facade for `application/ports`.
- `src/notekeeper/application/ports/auth.py` — Authentication, user lookup, and credential-mutation port.
- `src/notekeeper/application/ports/events.py` — Application event and progress ports.
- `src/notekeeper/application/ports/processing.py` — Ports used by audio and processing workflows.
- `src/notekeeper/application/ports/recaps.py` — Ports used to tokenize transcripts and generate recaps.
- `src/notekeeper/application/ports/repositories.py` — Persistence ports for domain entities and processing records.
- `src/notekeeper/application/ports/runtime.py` — Clock and identifier generation ports.
- `src/notekeeper/application/ports/settings.py` — Workspace override and user-preference persistence ports.
- `src/notekeeper/application/ports/storage.py` — Artifact and campaign-folder storage ports.

### `application/results`

- `src/notekeeper/application/results/__init__.py` — Explicit public facade for `application/results`.

### `application/use_cases`

Application workflows grouped by feature.

- `src/notekeeper/application/use_cases/__init__.py` — Explicit public facade for `application/use_cases`.
- `src/notekeeper/application/use_cases/_recaps.py` — Shared recap-generation orchestration.

### `application/use_cases/campaigns`

- `src/notekeeper/application/use_cases/campaigns/__init__.py` — Explicit public facade for `application/use_cases/campaigns`.
- `src/notekeeper/application/use_cases/campaigns/add_participant_to_campaign.py` — Add participant to campaign use case.
- `src/notekeeper/application/use_cases/campaigns/add_voice_sample.py` — Add voice sample to campaign use case.
- `src/notekeeper/application/use_cases/campaigns/create_campaign.py` — Create campaign use case.
- `src/notekeeper/application/use_cases/campaigns/delete_audio_track.py` — Delete campaign audio track use case.
- `src/notekeeper/application/use_cases/campaigns/delete_campaign.py` — Delete campaign use case.
- `src/notekeeper/application/use_cases/campaigns/delete_participant.py` — Delete campaign participant use case.
- `src/notekeeper/application/use_cases/campaigns/delete_voice_sample.py` — Delete campaign voice sample use case.
- `src/notekeeper/application/use_cases/campaigns/get_campaign.py` — Get campaign use case.
- `src/notekeeper/application/use_cases/campaigns/get_recap_guidances.py` — Get campaign-specific recap guidances.
- `src/notekeeper/application/use_cases/campaigns/list_audio_tracks.py` — List campaign audio tracks use case.
- `src/notekeeper/application/use_cases/campaigns/list_campaigns.py` — List campaigns use case.
- `src/notekeeper/application/use_cases/campaigns/list_participants.py` — List campaign participants use case.
- `src/notekeeper/application/use_cases/campaigns/list_voice_samples.py` — List campaign voice samples use case.
- `src/notekeeper/application/use_cases/campaigns/register_audio_track.py` — Register campaign audio track use case.
- `src/notekeeper/application/use_cases/campaigns/sync_campaign_folder.py` — Synchronize a campaign folder snapshot into application state.
- `src/notekeeper/application/use_cases/campaigns/update_audio_track.py` — Update campaign audio track use case.
- `src/notekeeper/application/use_cases/campaigns/update_campaign.py` — Update campaign use case.
- `src/notekeeper/application/use_cases/campaigns/update_participant.py` — Update campaign participant use case.
- `src/notekeeper/application/use_cases/campaigns/update_recap_guidances.py` — Update campaign-specific recap guidances.
- `src/notekeeper/application/use_cases/campaigns/update_voice_sample.py` — Update campaign voice sample use case.

### `application/use_cases/campaigns/utils`

- `src/notekeeper/application/use_cases/campaigns/utils/__init__.py` — Explicit public facade for `application/use_cases/campaigns/utils`.
- `src/notekeeper/application/use_cases/campaigns/utils/finders.py` — Campaign aggregate lookup helpers.
- `src/notekeeper/application/use_cases/campaigns/utils/jobs.py` — Campaign job helpers.

### `application/use_cases/export`

- `src/notekeeper/application/use_cases/export/__init__.py` — Explicit public facade for `application/use_cases/export`.
- `src/notekeeper/application/use_cases/export/_markdown.py` — Markdown rendering helpers.
- `src/notekeeper/application/use_cases/export/export_recap_markdown.py` — Export recap markdown use case.
- `src/notekeeper/application/use_cases/export/export_transcript_markdown.py` — Export transcript markdown use case.
- `src/notekeeper/application/use_cases/export/preview_recap_markdown.py` — Preview recap Markdown use case.
- `src/notekeeper/application/use_cases/export/preview_transcript_markdown.py` — Preview transcript Markdown use case.

### `application/use_cases/media`

- `src/notekeeper/application/use_cases/media/__init__.py` — Explicit public facade for `application/use_cases/media`.
- `src/notekeeper/application/use_cases/media/inspect_audio_metadata.py` — Inspect audio metadata use case.
- `src/notekeeper/application/use_cases/media/inspect_local_audio_file.py` — Inspect a local source audio file before it is imported.

### `application/use_cases/processing`

- `src/notekeeper/application/use_cases/processing/__init__.py` — Explicit public facade for `application/use_cases/processing`.
- `src/notekeeper/application/use_cases/processing/cancel_processing_job.py` — Cancel a running processing job.
- `src/notekeeper/application/use_cases/processing/clear_failed_jobs_for_campaign.py` — Clear failed processing jobs and their owned artifacts.
- `src/notekeeper/application/use_cases/processing/create_processing_job_for_audio_track.py` — Create a processing job for an existing audio track use case.
- `src/notekeeper/application/use_cases/processing/delete_processing_job.py` — Delete a processing job and its job-owned temporary artifacts.
- `src/notekeeper/application/use_cases/processing/generate_recap.py` — Generate recap use case.
- `src/notekeeper/application/use_cases/processing/get_job_status.py` — Get job status use case.
- `src/notekeeper/application/use_cases/processing/job_transitions.py` — Atomic processing-job state transitions.
- `src/notekeeper/application/use_cases/processing/list_jobs_for_campaign.py` — List processing jobs for a campaign use case.
- `src/notekeeper/application/use_cases/processing/mapping_records.py` — Speaker-mapping record builders for processing workflows.
- `src/notekeeper/application/use_cases/processing/progress.py` — Progress stage plans for processing use cases.
- `src/notekeeper/application/use_cases/processing/progress_outcomes.py` — Progress outcomes that respect concurrent job cancellation.
- `src/notekeeper/application/use_cases/processing/queue_processing_job.py` — Queue a pending processing job for asynchronous execution.
- `src/notekeeper/application/use_cases/processing/restart_processing_job.py` — Restart a failed or canceled processing job as a new pending job.
- `src/notekeeper/application/use_cases/processing/review_speaker_mappings.py` — Validate speaker-review decisions and queue their application.
- `src/notekeeper/application/use_cases/processing/run_processing_job.py` — Run processing job use case.
- `src/notekeeper/application/use_cases/processing/submit_recording_for_processing.py` — Submit recording for processing use case.

### `application/use_cases/utils`

- `src/notekeeper/application/use_cases/utils/__init__.py` — Explicit public facade for `application/use_cases/utils`.
- `src/notekeeper/application/use_cases/utils/artifact_cleanup.py` — Best-effort cleanup helpers for committed artifact changes.
- `src/notekeeper/application/use_cases/utils/audio_sources.py` — Validation and normalization for audio source inputs.
- `src/notekeeper/application/use_cases/utils/campaign_mutation_policy.py` — Serialize campaign writes against processing-job queue transitions.
- `src/notekeeper/application/use_cases/utils/guarded_campaign_mutation.py` — Typed whole-use-case campaign mutation guard.
- `src/notekeeper/application/use_cases/utils/guarded_job_queue.py` — Authorization, visibility, and locking for queue transitions.
- `src/notekeeper/application/use_cases/utils/lookups.py` — Repository lookup helpers with consistent not-found errors.
- `src/notekeeper/application/use_cases/utils/role_authorized_use_case.py` — Workspace-role authorization boundary.


## `infrastructure`

Concrete adapters for ports: SQLite, filesystem, FFmpeg, WhisperX, DeepSeek, tokenization, cleanup, and runtime event mechanisms.

- `src/notekeeper/infrastructure/__init__.py` — Explicit public facade for `infrastructure`.
- `src/notekeeper/infrastructure/errors.py` — Infrastructure-layer errors.

### `infrastructure/auth`

Local JSON authentication and CLI credential-session persistence.

- `src/notekeeper/infrastructure/auth/__init__.py` — Explicit public facade for `infrastructure/auth`.
- `src/notekeeper/infrastructure/auth/in_memory_api_session_manager.py` — Thread-safe opaque access/refresh sessions for the local API profile.
- `src/notekeeper/infrastructure/auth/local_auth_provider.py` — Locked, atomic local-user authentication and credential mutation adapter.
- `src/notekeeper/infrastructure/auth/local_cli_session_store.py` — Locked, atomic persisted CLI credential session.

### `infrastructure/cleanup`

Removal of job-owned and transient files.

- `src/notekeeper/infrastructure/cleanup/__init__.py` — Explicit public facade for `infrastructure/cleanup`.
- `src/notekeeper/infrastructure/cleanup/job_cleaner.py` — Local processing-job cleanup across SQLite and filesystem storage.
- `src/notekeeper/infrastructure/cleanup/transient_audio_cleaner.py` — Cleanup of transient audio created by processing jobs.

### `infrastructure/cleanup/utils`

- `src/notekeeper/infrastructure/cleanup/utils/__init__.py` — Explicit public facade for `infrastructure/cleanup/utils`.
- `src/notekeeper/infrastructure/cleanup/utils/path_removal.py` — Safe removal of cleanup-owned filesystem paths.

### `infrastructure/deepseek`

Recap generation through the DeepSeek-compatible API.

- `src/notekeeper/infrastructure/deepseek/__init__.py` — Explicit public facade for `infrastructure/deepseek`.
- `src/notekeeper/infrastructure/deepseek/generator.py` — DeepSeek recap-generation adapter.
- `src/notekeeper/infrastructure/deepseek/interfaces.py` — Internal DeepSeek adapter protocols.
- `src/notekeeper/infrastructure/deepseek/local_request_logger.py` — Local JSON artifact logging for DeepSeek request diagnostics.
- `src/notekeeper/infrastructure/deepseek/noop_request_logger.py` — No-op DeepSeek request diagnostics logger.
- `src/notekeeper/infrastructure/deepseek/openai_client.py` — OpenAI-compatible DeepSeek chat client.

### `infrastructure/deepseek/utils`

- `src/notekeeper/infrastructure/deepseek/utils/__init__.py` — Explicit public facade for `infrastructure/deepseek/utils`.
- `src/notekeeper/infrastructure/deepseek/utils/prompts.py` — Prompt rendering for DeepSeek recap requests.

### `infrastructure/ffmpeg`

Audio normalization, concatenation, probing, and progress.

- `src/notekeeper/infrastructure/ffmpeg/__init__.py` — Explicit public facade for `infrastructure/ffmpeg`.
- `src/notekeeper/infrastructure/ffmpeg/processor.py` — FFmpeg audio preparation adapter.
- `src/notekeeper/infrastructure/ffmpeg/recording_normalizer.py` — FFmpeg adapter for canonical recording normalization.

### `infrastructure/ffmpeg/utils`

- `src/notekeeper/infrastructure/ffmpeg/utils/__init__.py` — Explicit public facade for `infrastructure/ffmpeg/utils`.
- `src/notekeeper/infrastructure/ffmpeg/utils/manifests.py` — Prepared-audio range and manifest builders.
- `src/notekeeper/infrastructure/ffmpeg/utils/process.py` — FFmpeg subprocess execution with machine-readable progress.

### `infrastructure/filesystem`

Filesystem repositories, artifact storage, scanning, and manifests.

- `src/notekeeper/infrastructure/filesystem/__init__.py` — Explicit public facade for `infrastructure/filesystem`.
- `src/notekeeper/infrastructure/filesystem/metadata.py` — Local audio metadata reader.
- `src/notekeeper/infrastructure/filesystem/prepared_audio_manifest_store.py` — Prepared-audio manifest storage.
- `src/notekeeper/infrastructure/filesystem/recap_guidances.py` — Campaign-specific recap guidance storage backed by JSON files.
- `src/notekeeper/infrastructure/filesystem/scanner.py` — Local campaign folder scanner.
- `src/notekeeper/infrastructure/filesystem/snapshot_recap_guidances.py` — Read-only recap guidance adapter backed by a processing-job settings snapshot.
- `src/notekeeper/infrastructure/filesystem/source_metadata.py` — Metadata reader for local source audio files.
- `src/notekeeper/infrastructure/filesystem/storage.py` — Local filesystem artifact storage.

### `infrastructure/filesystem/utils`

- `src/notekeeper/infrastructure/filesystem/utils/__init__.py` — Explicit public facade for `infrastructure/filesystem/utils`.
- `src/notekeeper/infrastructure/filesystem/utils/audio_metadata.py` — Build audio metadata from a local filesystem path.
- `src/notekeeper/infrastructure/filesystem/utils/audio_probe.py` — Audio probing helpers.
- `src/notekeeper/infrastructure/filesystem/utils/checksum.py` — Checksum helpers.
- `src/notekeeper/infrastructure/filesystem/utils/paths.py` — Filesystem path safety helpers.

### `infrastructure/runtime`

In-process and persisted event/runtime adapters.

- `src/notekeeper/infrastructure/runtime/__init__.py` — Explicit public facade for `infrastructure/runtime`.
- `src/notekeeper/infrastructure/runtime/campaign_mutation_guard.py` — Cross-process campaign mutation locks for a local NoteKeeper database.
- `src/notekeeper/infrastructure/runtime/dashboard_event_hub.py` — Process-local dashboard invalidation event distribution.
- `src/notekeeper/infrastructure/runtime/local_dashboard_campaign_repository.py` — Local dashboard campaign repository decorator.
- `src/notekeeper/infrastructure/runtime/local_dashboard_job_cleaner.py` — Local dashboard job-cleaner decorator.
- `src/notekeeper/infrastructure/runtime/local_dashboard_job_repository.py` — Local dashboard job repository decorator.
- `src/notekeeper/infrastructure/runtime/persisted_progress_event_hub.py` — Cross-runtime progress distribution backed by persisted snapshots.
- `src/notekeeper/infrastructure/runtime/progress_event_hub.py` — Process-local progress event distribution.
- `src/notekeeper/infrastructure/runtime/progress_tracker.py` — Streaming progress tracker implementation.
- `src/notekeeper/infrastructure/runtime/progress_tracker_factory.py` — Factory for streaming progress trackers.
- `src/notekeeper/infrastructure/runtime/system_clock.py` — System clock adapter.
- `src/notekeeper/infrastructure/runtime/uuid_generator.py` — UUID-backed id generator adapter.

### `infrastructure/runtime/jobs`

Local process execution, capacity, IPC, and process-tree infrastructure.

- `src/notekeeper/infrastructure/runtime/jobs/__init__.py` — Explicit public facade for `infrastructure/runtime/jobs`.
- `src/notekeeper/infrastructure/runtime/jobs/job_capacity.py` — Cross-process processing capacity allocation.
- `src/notekeeper/infrastructure/runtime/jobs/process_execution_registry.py` — Persisted worker process identities.
- `src/notekeeper/infrastructure/runtime/jobs/process_job_executor.py` — Local queued-job manager.
- `src/notekeeper/infrastructure/runtime/jobs/process_message_writer.py` — Serialized worker IPC writes.
- `src/notekeeper/infrastructure/runtime/jobs/process_tree.py` — Operating-system process-tree termination.

### `infrastructure/speaker_mapping`

Infrastructure-backed automatic speaker identification.

- `src/notekeeper/infrastructure/speaker_mapping/__init__.py` — Explicit public facade for `infrastructure/speaker_mapping`.
- `src/notekeeper/infrastructure/speaker_mapping/identifier.py` — Sample-based speaker identification adapter.

### `infrastructure/sqlite`

SQLite database and repository implementations.

- `src/notekeeper/infrastructure/sqlite/__init__.py` — Explicit public facade for `infrastructure/sqlite`.
- `src/notekeeper/infrastructure/sqlite/audio_track_repository.py` — SQLite audio track repository.
- `src/notekeeper/infrastructure/sqlite/campaign_repository.py` — SQLite campaign repository.
- `src/notekeeper/infrastructure/sqlite/database.py` — SQLite database setup.
- `src/notekeeper/infrastructure/sqlite/job_repository.py` — SQLite processing job repository.
- `src/notekeeper/infrastructure/sqlite/participant_repository.py` — SQLite participant repository.
- `src/notekeeper/infrastructure/sqlite/progress_event_snapshot_store.py` — SQLite persistence for cross-runtime progress snapshots.
- `src/notekeeper/infrastructure/sqlite/recap_repository.py` — SQLite recap repository.
- `src/notekeeper/infrastructure/sqlite/schema.py` — SQLite schema definition.
- `src/notekeeper/infrastructure/sqlite/scope.py` — SQL tenant predicates and scoped-write checks.
- `src/notekeeper/infrastructure/sqlite/speaker_mapping_repository.py` — SQLite speaker mapping repository.
- `src/notekeeper/infrastructure/sqlite/speaker_review_submission_repository.py` — SQLite persistence for queued speaker-review decisions.
- `src/notekeeper/infrastructure/sqlite/transcript_repository.py` — SQLite transcript repository.
- `src/notekeeper/infrastructure/sqlite/user_preferences_repository.py` — SQLite persistence for each user's default workspace.
- `src/notekeeper/infrastructure/sqlite/voice_sample_repository.py` — SQLite voice sample repository.
- `src/notekeeper/infrastructure/sqlite/workspace_ids.py` — Deterministic personal workspace identifiers.
- `src/notekeeper/infrastructure/sqlite/workspace_repository.py` — SQLite workspace and membership repository.
- `src/notekeeper/infrastructure/sqlite/workspace_settings_repository.py` — SQLite persistence for workspace processing-setting overrides.

### `infrastructure/sqlite/utils`

- `src/notekeeper/infrastructure/sqlite/utils/__init__.py` — Explicit public facade for `infrastructure/sqlite/utils`.
- `src/notekeeper/infrastructure/sqlite/utils/common_serialization.py` — Serialization for shared domain value objects.
- `src/notekeeper/infrastructure/sqlite/utils/metadata_serialization.py` — Audio metadata serialization.
- `src/notekeeper/infrastructure/sqlite/utils/payload_storage.py` — Payload storage adapter wrapper.
- `src/notekeeper/infrastructure/sqlite/utils/queries.py` — SQLite aggregate list helpers.
- `src/notekeeper/infrastructure/sqlite/utils/recap_serialization.py` — Recap payload serialization.
- `src/notekeeper/infrastructure/sqlite/utils/row_mappers.py` — SQLite row-to-domain mappers.
- `src/notekeeper/infrastructure/sqlite/utils/serialization.py` — Serialization helper facade for SQLite repositories.
- `src/notekeeper/infrastructure/sqlite/utils/settings_serialization.py` — Processing-settings snapshot JSON serialization.
- `src/notekeeper/infrastructure/sqlite/utils/transcript_serialization.py` — Transcript payload serialization.
- `src/notekeeper/infrastructure/sqlite/utils/warnings_serialization.py` — Pipeline warning payload serialization.
- `src/notekeeper/infrastructure/sqlite/utils/write_helpers.py` — SQLite domain write helpers.

### `infrastructure/tokenization`

Token-count enforcement for recap generation.

- `src/notekeeper/infrastructure/tokenization/__init__.py` — Explicit public facade for `infrastructure/tokenization`.
- `src/notekeeper/infrastructure/tokenization/tokenizer.py` — tiktoken-based transcript tokenizer.

### `infrastructure/whisperx`

WhisperX transcription/alignment/diarization adapter.

- `src/notekeeper/infrastructure/whisperx/__init__.py` — Explicit public facade for `infrastructure/whisperx`.
- `src/notekeeper/infrastructure/whisperx/interfaces.py` — Internal WhisperX adapter protocols.
- `src/notekeeper/infrastructure/whisperx/payload_store.py` — Raw WhisperX payload artifact storage.
- `src/notekeeper/infrastructure/whisperx/runner.py` — Default WhisperX pipeline orchestration.
- `src/notekeeper/infrastructure/whisperx/stages.py` — WhisperX ASR, alignment, and diarization stage execution.
- `src/notekeeper/infrastructure/whisperx/transcriber.py` — WhisperX transcription adapter.

### `infrastructure/whisperx/utils`

- `src/notekeeper/infrastructure/whisperx/utils/__init__.py` — Explicit public facade for `infrastructure/whisperx/utils`.
- `src/notekeeper/infrastructure/whisperx/utils/json_payloads.py` — JSON-safe payload conversion helpers.
- `src/notekeeper/infrastructure/whisperx/utils/segments.py` — WhisperX transcript segment conversion helpers.
- `src/notekeeper/infrastructure/whisperx/utils/speechbrain_compat.py` — Compatibility helpers for SpeechBrain lazy imports.


## `interfaces`

User-facing CLI and Textual TUI adapters plus the interface-facing runtime contract.

- `src/notekeeper/interfaces/__init__.py` — Explicit public facade for `interfaces`.
- `src/notekeeper/interfaces/contracts.py` — Contracts shared by UI adapters.

### `interfaces/api`

Versioned FastAPI adapter with provider-neutral Bearer identity, workspace-scoped
routes, multipart uploads, SSE progress, stable schemas, and error envelopes.

- `src/notekeeper/interfaces/api/__init__.py` — Explicit public facade for `interfaces/api`.
- `src/notekeeper/interfaces/api/app.py` — FastAPI application factory and lifespan wiring.
- `src/notekeeper/interfaces/api/body_limit_middleware.py` — Streaming request-size enforcement for audio uploads.
- `src/notekeeper/interfaces/api/contracts.py` — Transport-facing API runtime and session protocols.
- `src/notekeeper/interfaces/api/dependencies.py` — Bearer identity and workspace-session dependencies.
- `src/notekeeper/interfaces/api/error_handlers.py` — Unified application/domain-to-HTTP exception mapping.
- `src/notekeeper/interfaces/api/errors.py` — API transport error values.
- `src/notekeeper/interfaces/api/openapi.py` — Shared OpenAPI error declarations.
- `src/notekeeper/interfaces/api/request_id_middleware.py` — Request correlation IDs.
- `src/notekeeper/interfaces/api/mappers/__init__.py` — Explicit mapper facade.
- `src/notekeeper/interfaces/api/mappers/resources.py` — Domain-to-HTTP resource mapping.
- `src/notekeeper/interfaces/api/routers/__init__.py` — Explicit router facade.
- `src/notekeeper/interfaces/api/routers/auth.py` — Session, identity, and workspace discovery routes.
- `src/notekeeper/interfaces/api/routers/campaigns.py` — Campaign routes.
- `src/notekeeper/interfaces/api/routers/health.py` — Local service health route.
- `src/notekeeper/interfaces/api/routers/jobs.py` — Job actions, status, and SSE routes.
- `src/notekeeper/interfaces/api/routers/participants.py` — Participant routes.
- `src/notekeeper/interfaces/api/routers/recordings.py` — Multipart recording routes.
- `src/notekeeper/interfaces/api/routers/results.py` — Transcript and recap Markdown routes.
- `src/notekeeper/interfaces/api/routers/samples.py` — Multipart voice-sample routes.
- `src/notekeeper/interfaces/api/schemas/__init__.py` — Explicit HTTP schema facade.
- `src/notekeeper/interfaces/api/schemas/auth.py` — Auth and identity DTOs.
- `src/notekeeper/interfaces/api/schemas/common.py` — Error and collection DTOs.
- `src/notekeeper/interfaces/api/schemas/resources.py` — Workspace resource DTOs.
- `src/notekeeper/interfaces/api/utils/__init__.py` — Explicit API utility facade.
- `src/notekeeper/interfaces/api/utils/uploads.py` — Temporary upload validation, copying, and cleanup.

### `interfaces/cli`

Scriptable Typer commands and terminal progress output.

- `src/notekeeper/interfaces/cli/__init__.py` — Explicit public facade for `interfaces/cli`.
- `src/notekeeper/interfaces/cli/auth_app.py` — Local registration, login, logout, and auth-status commands.
- `src/notekeeper/interfaces/cli/campaign_app.py` — Campaign CLI commands.
- `src/notekeeper/interfaces/cli/cli.py` — Typer application composition and common workspace selection.
- `src/notekeeper/interfaces/cli/common.py` — Shared CLI command helpers.
- `src/notekeeper/interfaces/cli/diagnostics_app.py` — Diagnostics CLI command registration.
- `src/notekeeper/interfaces/cli/job_app.py` — Processing job CLI commands.
- `src/notekeeper/interfaces/cli/participant_app.py` — Participant CLI commands.
- `src/notekeeper/interfaces/cli/progress.py` — Rich-backed CLI progress rendering.
- `src/notekeeper/interfaces/cli/recap_app.py` — Recap CLI commands.
- `src/notekeeper/interfaces/cli/recap_prompts_app.py` — Campaign recap prompt CLI commands.
- `src/notekeeper/interfaces/cli/recording_app.py` — Recording CLI commands.
- `src/notekeeper/interfaces/cli/review_app.py` — Speaker mapping review CLI commands.
- `src/notekeeper/interfaces/cli/sample_app.py` — Voice sample CLI commands.
- `src/notekeeper/interfaces/cli/settings_app.py` — JSON workspace, campaign, membership, and user settings commands.
- `src/notekeeper/interfaces/cli/transcript_app.py` — Transcript CLI commands.

### `interfaces/tui`

Interactive Textual dashboard, screens, and actions.

- `src/notekeeper/interfaces/tui/__init__.py` — Explicit public facade for `interfaces/tui`.
- `src/notekeeper/interfaces/tui/audio_file_explorer_screen.py` — Shared audio file explorer for the Textual interface.
- `src/notekeeper/interfaces/tui/campaign_app.py` — Campaign synchronization action for the Textual interface.
- `src/notekeeper/interfaces/tui/campaign_deletion_screen.py` — Confirmation screen for destructive campaign deletion.
- `src/notekeeper/interfaces/tui/campaign_management_screen.py` — Campaign management modal for the Textual interface.
- `src/notekeeper/interfaces/tui/campaign_settings_screen.py` — Campaign selector and recap-prompt settings form for the Textual interface.
- `src/notekeeper/interfaces/tui/clear_failed_jobs_screen.py` — Confirmation screen for clearing failed processing jobs.
- `src/notekeeper/interfaces/tui/common.py` — Shared Textual formatting and validation helpers.
- `src/notekeeper/interfaces/tui/dashboard_messages.py` — Dashboard selection models and internal Textual messages.
- `src/notekeeper/interfaces/tui/dashboard_progress.py` — Processing progress subscriptions and rendering.
- `src/notekeeper/interfaces/tui/dashboard_refresh.py` — Dashboard data loading and table refresh operations.
- `src/notekeeper/interfaces/tui/dashboard_selection.py` — Dashboard selection restoration and action-button state.
- `src/notekeeper/interfaces/tui/diagnostics_app.py` — Diagnostics modal action for the Textual interface.
- `src/notekeeper/interfaces/tui/identifier_data_table.py` — Data table support for compact identifier cells and their tooltips.
- `src/notekeeper/interfaces/tui/job_action_confirmation_screen.py` — Confirmation screen for destructive processing-job actions.
- `src/notekeeper/interfaces/tui/job_app.py` — Processing job actions for the Textual interface.
- `src/notekeeper/interfaces/tui/login_screen.py` — Masked local-auth login modal.
- `src/notekeeper/interfaces/tui/object_action_confirmation_screen.py` — Confirmation screen for destructive recording and player actions.
- `src/notekeeper/interfaces/tui/participant_app.py` — Participant actions and modal screen for the Textual interface.
- `src/notekeeper/interfaces/tui/preview_app.py` — Markdown preview modal screen.
- `src/notekeeper/interfaces/tui/recap_app.py` — Recap generation, preview, and export actions.
- `src/notekeeper/interfaces/tui/recap_prompt_editor_screen.py` — Multiline campaign recap prompt editor.
- `src/notekeeper/interfaces/tui/recording_app.py` — Recording actions and modal screen for the Textual interface.
- `src/notekeeper/interfaces/tui/registration_screen.py` — Masked local-user registration modal.
- `src/notekeeper/interfaces/tui/remove_voice_sample_screen.py` — Voice-sample selection and removal confirmation screen.
- `src/notekeeper/interfaces/tui/rename_screen.py` — Modal screen for renaming dashboard objects.
- `src/notekeeper/interfaces/tui/review_app.py` — Speaker-mapping review actions and modal screen.
- `src/notekeeper/interfaces/tui/sample_app.py` — Voice sample actions and modal screen for the Textual interface.
- `src/notekeeper/interfaces/tui/settings_confirmation_screen.py` — Shared settings reset/removal confirmation modal.
- `src/notekeeper/interfaces/tui/settings_screen.py` — First-level Workspace, Campaign, and User settings menu.
- `src/notekeeper/interfaces/tui/styles.tcss` — Textual layout, sizing, color, and responsive presentation rules.
- `src/notekeeper/interfaces/tui/transcript_app.py` — Transcript preview and export actions.
- `src/notekeeper/interfaces/tui/tui.py` — Textual dashboard composition with workspace and campaign scoping selectors.
- `src/notekeeper/interfaces/tui/user_settings_screen.py` — Login, password, and default-workspace settings form.
- `src/notekeeper/interfaces/tui/workspace_members_screen.py` — Workspace membership and role management form.
- `src/notekeeper/interfaces/tui/workspace_settings_screen.py` — Typed workspace model, language, temperature, and name settings form.


## `composition`

The composition root: settings, concrete dependency construction, host/session/worker assembly, and executable entry points.

- `src/notekeeper/composition/__init__.py` — Explicit public facade for `composition`.
- `src/notekeeper/composition/factory.py` — Local technical-service composition factory.
- `src/notekeeper/composition/job_pipeline.py` — Construction of the in-process processing pipeline.
- `src/notekeeper/composition/local_interface_runtime.py` — CLI/TUI-owned mutable user/workspace session controller.
- `src/notekeeper/composition/main.py` — Application entrypoint.
- `src/notekeeper/composition/repositories.py` — Typed system and workspace repository sets.
- `src/notekeeper/composition/runtime.py` — Local host and immutable application-session roots.
- `src/notekeeper/composition/web.py` — Local API runtime adapter and single-worker Uvicorn runner.
- `src/notekeeper/composition/settings.py` — Environment-loaded platform configuration, defaults, and settings allowlists.
- `src/notekeeper/composition/use_cases.py` — Aggregation of grouped use-case builders.
- `src/notekeeper/composition/worker.py` — Isolated worker composition root rebuilt from each processing job's settings snapshot.
- `src/notekeeper/composition/workspace_recap_generator_factory.py` — Builds explicit recap generators from current workspace LLM settings.

### `composition/use_case_builders`

One focused builder per public use-case group: campaigns, participants, samples,
recordings, jobs, transcripts, recaps, and media.

- `src/notekeeper/composition/use_case_builders/__init__.py` — Explicit public facade for grouped use-case builders.
- `src/notekeeper/composition/use_case_builders/campaigns.py` — Campaign use-case wiring.
- `src/notekeeper/composition/use_case_builders/guards.py` — Live workspace-role guard construction.
- `src/notekeeper/composition/use_case_builders/jobs.py` — Processing-job use-case wiring, including settings snapshots.
- `src/notekeeper/composition/use_case_builders/media.py` — Media inspection use-case wiring.
- `src/notekeeper/composition/use_case_builders/participants.py` — Participant use-case wiring.
- `src/notekeeper/composition/use_case_builders/recaps.py` — Recap use-case wiring with current-workspace generator selection.
- `src/notekeeper/composition/use_case_builders/recordings.py` — Recording use-case wiring.
- `src/notekeeper/composition/use_case_builders/samples.py` — Voice-sample use-case wiring.
- `src/notekeeper/composition/use_case_builders/transcripts.py` — Transcript use-case wiring.
- `src/notekeeper/composition/use_case_builders/wiring_context.py` — Shared immutable dependencies for use-case builders.
