"""SQLite schema definition."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS participants (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    display_name TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_participants_campaign
    ON participants (campaign_id);

CREATE TABLE IF NOT EXISTS voice_samples (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    artifact_uri TEXT NOT NULL,
    artifact_kind TEXT NOT NULL,
    artifact_checksum TEXT,
    metadata_json TEXT NOT NULL,
    recorded_at TEXT,
    UNIQUE (campaign_id, artifact_uri)
);

CREATE INDEX IF NOT EXISTS idx_voice_samples_campaign
    ON voice_samples (campaign_id);

CREATE INDEX IF NOT EXISTS idx_voice_samples_participant
    ON voice_samples (participant_id);

CREATE TABLE IF NOT EXISTS audio_tracks (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    artifact_uri TEXT NOT NULL,
    artifact_kind TEXT NOT NULL,
    artifact_checksum TEXT,
    metadata_json TEXT NOT NULL,
    title TEXT,
    UNIQUE (campaign_id, artifact_uri)
);

CREATE INDEX IF NOT EXISTS idx_audio_tracks_campaign
    ON audio_tracks (campaign_id);

CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    audio_track_id TEXT NOT NULL,
    payload_uri TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transcripts_audio_track
    ON transcripts (audio_track_id);

CREATE TABLE IF NOT EXISTS recaps (
    id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    payload_uri TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recaps_transcript
    ON recaps (transcript_id);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    audio_track_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    transcript_id TEXT,
    recap_id TEXT,
    warnings_json TEXT NOT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_campaign
    ON jobs (campaign_id);

CREATE INDEX IF NOT EXISTS idx_jobs_campaign_status
    ON jobs (campaign_id, status);

CREATE INDEX IF NOT EXISTS idx_jobs_status_updated
    ON jobs (status, updated_at);

CREATE INDEX IF NOT EXISTS idx_jobs_audio_track
    ON jobs (audio_track_id);

CREATE TABLE IF NOT EXISTS speaker_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    transcript_id TEXT NOT NULL,
    anonymous_label TEXT NOT NULL,
    participant_id TEXT,
    named_label TEXT,
    confidence REAL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_speaker_mappings_job
    ON speaker_mappings (job_id);

CREATE INDEX IF NOT EXISTS idx_speaker_mappings_transcript
    ON speaker_mappings (transcript_id);

CREATE TABLE IF NOT EXISTS speaker_review_submissions (
    job_id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    mappings_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progress_event_snapshots (
    operation_id TEXT PRIMARY KEY,
    event_kind TEXT NOT NULL,
    stage_index INTEGER NOT NULL,
    stage_count INTEGER NOT NULL,
    timing_available INTEGER NOT NULL,
    progress_stage TEXT NOT NULL,
    expected_duration INTEGER NOT NULL,
    current_duration INTEGER NOT NULL
);
"""

__all__ = ["SCHEMA"]

