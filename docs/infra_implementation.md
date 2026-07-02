# Infrastructure Implementation Plan

## Summary

Infrastructure owns SQLite persistence, local filesystem artifact storage, campaign folder scanning, audio probing, and runtime adapters. Application owns CRUD and sync orchestration. Domain owns only business invariants.

File URIs stored in SQLite are relative to the configured `storage_root` and use `/` separators, for example `campaign-1/records/session-01.wav`. The configured root belongs to composition settings, not to domain models.

## Port-Based Fragments

1. Application CRUD ports and use cases
   - Extend repositories with `get`, `list`/`list_for_*`, `save`, and `delete`.
   - Add campaign, participant, voice sample, audio track CRUD use cases.
   - Add `SyncCampaignFolder` as the application-level comparison between scanner output and DB state.

2. Filesystem artifact storage
   - Maintain `storage_root/<campaign_id>/players`, `records`, `transcripts`, and `recaps`.
   - Reject absolute paths, URI schemes, drive-qualified paths, and `..` path segments.
   - Save transcript/recap payload files and return relative `ArtifactRef` URIs.

3. Campaign folder scanner
   - Read `players/<player_name>/*` as voice samples and `records/*` as session recordings.
   - Ignore unsupported extensions and non-file entries.
   - Return a snapshot only; do not mutate DB or make business decisions.

4. Audio metadata reader
   - Resolve `ArtifactRef` through configured storage.
   - Read duration, stream metadata, file size, and checksum through `ffprobe`.
   - Fall back to stdlib WAV probing for local tests and simple PCM WAV files.

5. SQLite repositories
   - Store campaign, participant, sample, track, job indexes in SQLite.
   - Store transcript and recap payload JSON in campaign artifact folders; SQLite keeps `payload_uri`.
   - Preserve completed job/transcript/recap history when sync removes a missing source recording.

6. Composition
   - Provide `NoteKeeperSettings` for `storage_root`, `sqlite_path`, audio extensions, and `ffprobe_path`.
   - Build storage, scanner, metadata reader, SQLite repositories, clock, and id generator in one bundle.

## Sync Semantics

- `players/<name>/audio.*` creates a participant when the display name does not exist.
- Found player samples and session recordings are inserted or metadata-refreshed by URI.
- Missing samples and recordings are deleted from DB state only; physical files are never deleted by sync.
- When a recording disappears, pending jobs for that recording are deleted. Completed jobs, transcripts, and recaps are preserved as history.
- Empty or removed player folders do not delete participants.
- Sync does not start processing jobs automatically.

## Test Coverage

- Application sync unit tests cover create/update/delete counts and pending-job removal.
- Filesystem tests cover layout creation, scanner filtering, unsafe URI rejection, and WAV metadata probing.
- SQLite tests cover aggregate reconstruction, artifact URI lookups, payload URI storage, job listing, and deletion.
- Integration tests cover scanner + metadata reader + SQLite sync behavior with real temporary files.
