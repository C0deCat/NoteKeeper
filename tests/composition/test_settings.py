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
                "NOTEKEEPER_WHISPERX_VAD_METHOD=silero",
                "NOTEKEEPER_FFMPEG_BIN=C:/tools/ffmpeg-7.1.1/bin",
            ),
        ),
        encoding="utf-8",
    )

    settings = NoteKeeperSettings()
    settings_repr = repr(settings)

    assert settings.deepseek_api_key == "deepseek-secret"
    assert settings.whisperx_hf_token == "hf-secret"
    assert settings.whisperx_vad_method == "silero"
    assert settings.ffmpeg_bin == Path("C:/tools/ffmpeg-7.1.1/bin")
    assert "deepseek-secret" not in settings_repr
    assert "hf-secret" not in settings_repr
