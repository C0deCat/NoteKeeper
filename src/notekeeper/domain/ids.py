"""Typed domain identifiers."""

from typing import NewType

CampaignId = NewType("CampaignId", str)
UserId = NewType("UserId", str)
WorkspaceId = NewType("WorkspaceId", str)
ParticipantId = NewType("ParticipantId", str)
VoiceSampleId = NewType("VoiceSampleId", str)
AudioTrackId = NewType("AudioTrackId", str)
TranscriptId = NewType("TranscriptId", str)
RecapId = NewType("RecapId", str)
ProcessingJobId = NewType("ProcessingJobId", str)

BUILTIN_ROOT_USER_ID = UserId("00000000-0000-0000-0000-000000000001")
BUILTIN_ROOT_WORKSPACE_ID = WorkspaceId("00000000-0000-0000-0000-000000000101")
