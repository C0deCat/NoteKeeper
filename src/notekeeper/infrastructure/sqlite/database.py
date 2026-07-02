"""SQLite database setup."""

from __future__ import annotations

import sqlite3
from pathlib import Path


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

CREATE INDEX IF NOT EXISTS idx_jobs_audio_track
    ON jobs (audio_track_id);
"""


class SQLiteDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
