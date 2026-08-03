import json
from pathlib import Path

import pytest

import notekeeper.infrastructure.filesystem.recap_guidances as recap_guidances_module
from notekeeper.domain import CampaignId
from notekeeper.infrastructure import InfrastructureError
from notekeeper.infrastructure.filesystem import (
    JsonCampaignRecapGuidances,
    LocalCampaignArtifactStorage,
)


def test_campaign_recap_guidances_are_lazily_created_from_template(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template.json"
    _write_prompts(template, " chunk prompt\n", "combined prompt")
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    guidances = JsonCampaignRecapGuidances(storage, template)
    campaign_id = CampaignId("campaign-1")

    chunk = guidances.get_chunk_recap_guidances(campaign_id)
    combined = guidances.get_combined_recap_guidances(campaign_id)

    campaign_file = tmp_path / "artifacts" / "campaign-1" / "recap_prompts.json"
    assert chunk == " chunk prompt\n"
    assert combined == "combined prompt"
    assert json.loads(campaign_file.read_text(encoding="utf-8")) == {
        "chunk_recap_prompt": " chunk prompt\n",
        "combine_chunks_prompt": "combined prompt",
    }


def test_existing_campaign_guidances_do_not_follow_template_changes(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template.json"
    _write_prompts(template, "initial chunk", "initial combined")
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    guidances = JsonCampaignRecapGuidances(storage, template)
    campaign_id = CampaignId("campaign-1")
    guidances.get_chunk_recap_guidances(campaign_id)

    _write_prompts(template, "changed chunk", "changed combined")

    assert guidances.get_chunk_recap_guidances(campaign_id) == "initial chunk"
    assert (
        guidances.get_combined_recap_guidances(campaign_id)
        == "initial combined"
    )


def test_campaign_recap_guidances_are_saved_atomically(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    _write_prompts(template, "chunk", "combined")
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    guidances = JsonCampaignRecapGuidances(storage, template)
    campaign_id = CampaignId("campaign-1")

    guidances.save_recap_guidances(
        campaign_id,
        chunk_recap_guidances="updated chunk",
        combined_recap_guidances="updated combined",
    )

    campaign_path = tmp_path / "artifacts" / "campaign-1"
    assert guidances.get_chunk_recap_guidances(campaign_id) == "updated chunk"
    assert (
        guidances.get_combined_recap_guidances(campaign_id)
        == "updated combined"
    )
    assert list(campaign_path.glob("*.tmp")) == []
    assert list(campaign_path.glob(".recap_prompts.json.*.tmp")) == []


def test_failed_atomic_replace_preserves_existing_guidances(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = tmp_path / "template.json"
    _write_prompts(template, "chunk", "combined")
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    guidances = JsonCampaignRecapGuidances(storage, template)
    campaign_id = CampaignId("campaign-1")
    guidances.get_chunk_recap_guidances(campaign_id)
    campaign_path = tmp_path / "artifacts" / "campaign-1"

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(recap_guidances_module.os, "replace", fail_replace)

    with pytest.raises(InfrastructureError, match="could not write"):
        guidances.save_recap_guidances(
            campaign_id,
            chunk_recap_guidances="new chunk",
            combined_recap_guidances="new combined",
        )

    payload = json.loads(
        (campaign_path / "recap_prompts.json").read_text(encoding="utf-8"),
    )
    assert payload["chunk_recap_prompt"] == "chunk"
    assert list(campaign_path.glob(".recap_prompts.json.*.tmp")) == []


def test_invalid_campaign_file_is_not_overwritten(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    _write_prompts(template, "chunk", "combined")
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    campaign_id = CampaignId("campaign-1")
    storage.ensure_campaign_layout(campaign_id)
    campaign_file = tmp_path / "artifacts" / "campaign-1" / "recap_prompts.json"
    campaign_file.write_text("{broken", encoding="utf-8")
    guidances = JsonCampaignRecapGuidances(storage, template)

    with pytest.raises(InfrastructureError, match="could not read"):
        guidances.save_recap_guidances(
            campaign_id,
            chunk_recap_guidances="new chunk",
            combined_recap_guidances="new combined",
        )

    assert campaign_file.read_text(encoding="utf-8") == "{broken"


@pytest.mark.parametrize(
    "template_content, expected_error",
    (
        (None, "does not exist"),
        ("[]", "must contain a JSON object"),
        ('{"chunk_recap_prompt": "chunk"}', "is missing prompt"),
    ),
)
def test_invalid_template_fails_only_when_guidances_are_requested(
    tmp_path: Path,
    template_content: str | None,
    expected_error: str,
) -> None:
    template = tmp_path / "template.json"
    if template_content is not None:
        template.write_text(template_content, encoding="utf-8")
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    guidances = JsonCampaignRecapGuidances(storage, template)

    with pytest.raises(InfrastructureError, match=expected_error):
        guidances.get_chunk_recap_guidances(CampaignId("campaign-1"))

    assert not (
        tmp_path / "artifacts" / "campaign-1" / "recap_prompts.json"
    ).exists()


def _write_prompts(path: Path, chunk: str, combined: str) -> None:
    path.write_text(
        json.dumps(
            {
                "chunk_recap_prompt": chunk,
                "combine_chunks_prompt": combined,
            },
        ),
        encoding="utf-8",
    )
