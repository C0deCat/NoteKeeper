from pathlib import Path

from notekeeper.application.use_cases.utils import GuardedCampaignMutation
from notekeeper.composition import NoteKeeperSettings, build_local_host
from notekeeper.infrastructure.runtime import PersistedProgressEventHub


def _interactive_runtime(settings: NoteKeeperSettings):
    return build_local_host(settings).interactive_runtime()


def test_local_host_assembles_grouped_use_cases_and_diagnostics(
    tmp_path: Path,
) -> None:
    runtime = _interactive_runtime(
        NoteKeeperSettings(
            storage_root=tmp_path / "artifacts",
            _env_file=None,
            auth_enabled=False,
            sqlite_path=tmp_path / "notekeeper.sqlite3",
            processing_work_root=tmp_path / "work",
            deepseek_api_key="deepseek-secret",
            whisperx_hf_token="hf-secret",
            whisperx_vad_method="pyannote",
        ),
    )

    diagnostics = runtime.diagnostics()

    assert hasattr(runtime.use_cases.campaigns.create, "execute")
    assert isinstance(runtime.use_cases.campaigns.update, GuardedCampaignMutation)
    assert hasattr(runtime.use_cases.campaigns.delete, "execute")
    assert hasattr(runtime.use_cases.jobs.create, "execute")
    assert hasattr(runtime.use_cases.jobs.restart_failed, "execute")
    assert hasattr(runtime.use_cases.jobs.clear_failed, "execute")
    assert hasattr(runtime.use_cases.jobs.delete, "execute")
    assert hasattr(runtime.use_cases.jobs.cancel, "execute")
    assert hasattr(runtime.use_cases.recaps.generate, "execute")
    assert isinstance(runtime.progress_events, PersistedProgressEventHub)
    assert diagnostics.deepseek_configured is True
    assert diagnostics.huggingface_configured is True
    assert diagnostics.whisperx_vad_method == "pyannote"
    assert "deepseek-secret" not in str(diagnostics)
    assert "hf-secret" not in str(diagnostics)
