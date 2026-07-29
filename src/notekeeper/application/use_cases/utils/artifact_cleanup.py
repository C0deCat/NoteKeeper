"""Best-effort cleanup helpers for committed artifact changes."""

from notekeeper.application.ports import CampaignArtifactStorage
from notekeeper.domain import ArtifactRef


def delete_artifact_with_warning(
    storage: CampaignArtifactStorage,
    artifact: ArtifactRef,
) -> tuple[str, ...]:
    try:
        storage.delete_artifact(artifact)
    except Exception as exc:
        return (f"could not delete source artifact {artifact.uri}: {exc}",)
    return ()
