# NoteKeeper

NoteKeeper turns long tabletop role-playing game recordings into structured
transcripts and session recaps. It prepares audio with FFmpeg, transcribes and
diarizes speech with WhisperX, maps speakers to campaign participants, and uses
DeepSeek to generate a readable Markdown summary.

The project provides an interactive terminal interface (TUI) for regular use
and a scriptable CLI for automation. For the project's background, processing
workflow, technology stack, and architecture, see the
[project overview](docs/overview.md). A more detailed architectural description
is available in [docs/architecture.md](docs/architecture.md).

## Features

- Manage campaigns, players, and player voice samples.
- Inspect, normalize, and combine session recordings.
- Transcribe recordings and align timestamps with WhisperX.
- Diarize speakers and match them to known campaign participants.
- Review uncertain speaker mappings before recap generation.
- Generate session recaps with DeepSeek.
- Preview and export transcripts and recaps as Markdown.
- Track long-running processing jobs from either the TUI or CLI.

## Requirements

- Python 3.11 (the project requires `>=3.11,<3.12`).
- [uv](https://docs.astral.sh/uv/) for dependency and environment management.
- FFmpeg and FFprobe available as commands or configured explicitly.
- A DeepSeek API key for recap generation.
- A Hugging Face token when using the default Pyannote-based diarization.
- An NVIDIA CUDA-capable GPU is strongly recommended for long recordings. The
  default configuration uses CUDA and `float16`; CPU processing can be
  configured but will be considerably slower.

## Installation

1. Clone the repository and enter its directory.

2. Install the project and development dependencies:

   ```console
   uv sync
   ```

3. Create a local environment file from the provided template:

   PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

   Linux or macOS:

   ```sh
   cp .env.example .env
   ```

4. Replace the placeholder values in `.env` with your own configuration:

   ```dotenv
   NOTEKEEPER_DEEPSEEK_API_KEY=your-deepseek-api-key
   NOTEKEEPER_WHISPERX_HF_TOKEN=your-hugging-face-token
   NOTEKEEPER_WHISPERX_VAD_METHOD=pyannote
   NOTEKEEPER_FFMPEG_BIN=C:\path\to\ffmpeg\bin
   ```

   Do not commit real API keys or tokens. `NOTEKEEPER_FFMPEG_BIN` is primarily
   needed on Windows and is explained in the next section.

## FFmpeg and TorchCodec on Windows

TorchCodec needs a shared FFmpeg build containing the FFmpeg DLLs, not only an
`ffmpeg.exe` executable. Use the FFmpeg 7.1.1 full shared build from GyanD:

[Download FFmpeg 7.1.1 full shared](https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-full_build-shared.zip)

Extract it to a local directory, for example:

```text
C:\Users\your-name\AppData\Local\Programs\ffmpeg-7.1.1-full_build-shared
```

Point `NOTEKEEPER_FFMPEG_BIN` at the extracted `bin` directory:

```dotenv
NOTEKEEPER_FFMPEG_BIN=C:\Users\your-name\AppData\Local\Programs\ffmpeg-7.1.1-full_build-shared\bin
```

This setting lets Python load the FFmpeg DLLs required by TorchCodec. It does
not replace `NOTEKEEPER_FFMPEG_PATH` or `NOTEKEEPER_FFPROBE_PATH`, which specify
the executables used for subprocess calls. Add the `bin` directory to `PATH`, or
set those commands explicitly if they are not already available:

```dotenv
NOTEKEEPER_FFMPEG_PATH=C:\path\to\ffmpeg\bin\ffmpeg.exe
NOTEKEEPER_FFPROBE_PATH=C:\path\to\ffmpeg\bin\ffprobe.exe
```

Verify the FFmpeg installation:

```console
ffmpeg -version
```

The output should report FFmpeg 7.1.1 and shared libraries such as
`libavcodec 61`, `libavformat 61`, and `libavutil 59`.

If TorchCodec still cannot load, verify it directly from PowerShell, replacing
the example path with your installation directory:

```powershell
uv run python -c "import os; os.add_dll_directory(r'C:\Users\your-name\AppData\Local\Programs\ffmpeg-7.1.1-full_build-shared\bin'); import torchcodec; print('torchcodec ok')"
```

## Usage

### Interactive TUI

Launch the recommended interactive interface:

```console
uv run notekeeper tui
```

From the TUI, create or select a campaign, add its players and one voice sample
for each player, submit a session recording, and run the resulting processing
job. If NoteKeeper cannot confidently identify every speaker, review the
mappings when prompted. Completed jobs can be previewed or exported as Markdown
transcripts and recaps.

### Scriptable CLI

All automation-friendly commands live under `notekeeper cli`. The following
example shows the main workflow. Replace values in angle brackets with IDs
printed by previous commands.

1. Create a campaign and add a player:

   ```console
   uv run notekeeper cli campaign create "The Sunless Citadel"
   uv run notekeeper cli participant add <campaign-id> "Alice"
   ```

2. Add at least one voice sample for every player:

   ```console
   uv run notekeeper cli sample add <campaign-id> <participant-id> "C:\recordings\alice-sample.wav"
   ```

3. Submit a session recording. This registers the recording and creates a
   pending processing job:

   ```console
   uv run notekeeper cli recording submit <campaign-id> "C:\recordings\session-01.wav" --title "Session 1"
   ```

4. Run the job ID printed by the submit command:

   ```console
   uv run notekeeper cli job run <job-id>
   uv run notekeeper cli job status <job-id>
   ```

5. If the job is waiting for review, resolve every uncertain speaker. Map a
   speaker to a participant, assign a standalone guest label, or explicitly
   keep the technical label:

   ```console
   uv run notekeeper cli review submit <job-id> --mapping "SPEAKER_00=<participant-id>" --label "SPEAKER_01=Guest" --keep "SPEAKER_02"
   ```

6. Read the `transcript` and `recap` IDs from the completed job status, then
   preview or export the generated Markdown:

   ```console
   uv run notekeeper cli transcript preview <transcript-id>
   uv run notekeeper cli transcript export <transcript-id>
   uv run notekeeper cli recap preview <recap-id>
   uv run notekeeper cli recap export <recap-id>
   ```

Use the built-in help to discover all commands and options:

```console
uv run notekeeper --help
uv run notekeeper cli --help
uv run notekeeper cli <command> --help
```

Inspect the resolved runtime configuration with:

```console
uv run notekeeper cli diagnostics
```

## Development

Run the test suite:

```console
uv run pytest
```
