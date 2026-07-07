from pathlib import Path

from notekeeper.composition import NoteKeeperSettings


def test_settings_load_provider_keys_from_dotenv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NOTEKEEPER_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("NOTEKEEPER_WHISPERX_HF_TOKEN", raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "NOTEKEEPER_DEEPSEEK_API_KEY=deepseek-secret",
                "NOTEKEEPER_WHISPERX_HF_TOKEN=hf-secret",
            ),
        ),
        encoding="utf-8",
    )

    settings = NoteKeeperSettings()
    settings_repr = repr(settings)

    assert settings.deepseek_api_key == "deepseek-secret"
    assert settings.whisperx_hf_token == "hf-secret"
    assert "deepseek-secret" not in settings_repr
    assert "hf-secret" not in settings_repr
