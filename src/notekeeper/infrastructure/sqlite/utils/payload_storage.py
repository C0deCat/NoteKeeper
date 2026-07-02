"""Payload storage adapter wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from notekeeper.domain import ArtifactRef, CampaignId


@dataclass(frozen=True, slots=True)
class PayloadStorage:
    store: Any

    def save_json_payload(
        self,
        *,
        campaign_id: CampaignId,
        folder: str,
        suggested_name: str,
        payload: dict[str, Any],
    ) -> ArtifactRef:
        return self.store.save_json_payload(
            campaign_id=campaign_id,
            folder=folder,
            suggested_name=suggested_name,
            payload=payload,
        )

    def read_json_payload(self, artifact_uri: str) -> dict[str, Any]:
        return self.store.read_json_payload(artifact_uri)
