"""Typed domain identifiers."""

from typing import NewType

CampaignId = NewType("CampaignId", str)
ParticipantId = NewType("ParticipantId", str)
VoiceSampleId = NewType("VoiceSampleId", str)
AudioTrackId = NewType("AudioTrackId", str)
TranscriptId = NewType("TranscriptId", str)
RecapId = NewType("RecapId", str)
ProcessingJobId = NewType("ProcessingJobId", str)
