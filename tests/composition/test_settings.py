from pathlib import Path

import pytest
from pydantic import ValidationError

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


def test_settings_load_normalized_audio_configuration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "NOTEKEEPER_NORMALIZED_AUDIO_SAMPLE_RATE_HZ=22050",
                "NOTEKEEPER_NORMALIZED_AUDIO_CHANNELS=2",
                "NOTEKEEPER_NORMALIZED_AUDIO_CODEC=pcm_s24le",
                "NOTEKEEPER_NORMALIZED_AUDIO_CONTAINER=wav",
            ),
        ),
        encoding="utf-8",
    )

    settings = NoteKeeperSettings()

    assert settings.normalized_audio_sample_rate_hz == 22050
    assert settings.normalized_audio_channels == 2
    assert settings.normalized_audio_codec == "pcm_s24le"
    assert settings.normalized_audio_container == "wav"


def test_settings_use_default_job_limits() -> None:
    settings = NoteKeeperSettings(_env_file=None)
    assert settings.max_concurrent_jobs == 4
    assert settings.max_concurrent_gpu_jobs == 1


def test_settings_reject_gpu_limit_above_total_limit() -> None:
    with pytest.raises(ValidationError, match="must not exceed"):
        NoteKeeperSettings(
            _env_file=None,
            max_concurrent_jobs=1,
            max_concurrent_gpu_jobs=2,
        )


def test_settings_load_local_auth_configuration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "NOTEKEEPER_AUTH_ENABLED=true",
                "NOTEKEEPER_AUTH_PROVIDER=local",
                "NOTEKEEPER_LOCAL_AUTH_USERS_PATH=private/users.json",
                "NOTEKEEPER_CLI_AUTH_SESSION_PATH=private/session.json",
            )
        ),
        encoding="utf-8",
    )

    settings = NoteKeeperSettings()

    assert settings.auth_enabled is True
    assert settings.auth_provider == "local"
    assert settings.local_auth_users_path == Path("private/users.json")
    assert settings.cli_auth_session_path == Path("private/session.json")
