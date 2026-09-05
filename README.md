# NoteKeeper

NoteKeeper turns long tabletop role-playing game recordings into structured
transcripts and session recaps. It prepares audio with FFmpeg, transcribes and
diarizes speech with WhisperX, maps speakers to campaign participants, and uses
DeepSeek to generate a readable Markdown summary.

The project provides an interactive terminal interface (TUI), a scriptable CLI,
and a local versioned HTTP API. For the project's background, processing
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

## Local authentication

Authentication is disabled by default. In that mode all campaigns belong to a
built-in root user and the TUI and CLI behave as before. Enable local
authentication with:

```dotenv
NOTEKEEPER_AUTH_ENABLED=true
NOTEKEEPER_AUTH_PROVIDER=local
NOTEKEEPER_LOCAL_AUTH_USERS_PATH=data/users.json
NOTEKEEPER_CLI_AUTH_SESSION_PATH=data/auth-session.json
```

On the first login or registration, NoteKeeper creates `data/users.json` with
the built-in `root` / `root` account. Change that password through Settings or
`notekeeper cli settings user password` before using authentication. The file
deliberately uses a simple editable format:

```json
[
  {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "login": "root",
    "password": "root"
  }
]
```

Do not change a `user_id` after campaigns have been assigned to it. Logins are
unique without regard to case, while passwords are compared exactly.

The TUI opens a sign-in window and provides registration when authentication is
enabled. For CLI use, create or restore a persisted session:

```console
uv run notekeeper auth register alice
uv run notekeeper auth login alice
uv run notekeeper auth status
uv run notekeeper auth logout
```

Password prompts are hidden. Automation can pass `--password`; registration
also accepts `--password-confirmation`. The successful credentials are stored
as plain text in `data/auth-session.json` and revalidated for every CLI command.

This local provider is intended for a trusted local machine. Passwords and CLI
sessions are not encrypted or hashed, and application-level campaign isolation
does not prevent someone with operating-system access from opening the SQLite,
JSON, or artifact files directly.

## Local HTTP API

The API is a development-only adapter over the same workspace-scoped use cases
as the CLI and TUI. It uses local authentication, SQLite, filesystem artifacts,
an in-memory Bearer session store, and the local process job queue. It is not a
public Internet deployment profile.

Unlike the TUI and CLI, API mode requires authentication to be enabled:

```dotenv
NOTEKEEPER_AUTH_ENABLED=true
NOTEKEEPER_API_HOST=127.0.0.1
NOTEKEEPER_API_PORT=8000
NOTEKEEPER_API_UPLOAD_MAX_BYTES=2147483648
```

Start one local API process:

```console
uv run notekeeper api
```

The command also accepts `--host` and `--port`. Interactive OpenAPI docs are at
`http://127.0.0.1:8000/docs`, while `GET /health` is unauthenticated. Register or
log in through `/api/v1/auth/register` or `/api/v1/auth/login`, then send the
returned opaque access token as `Authorization: Bearer <token>`. Access tokens
last 15 minutes and refresh tokens last 14 days by default. All sessions are
lost when the API process restarts.

Multipart recording and voice-sample uploads are copied to server-owned
temporary files and limited to 2 GiB by default. API responses never expose
managed filesystem paths. See the complete [local API contract](docs/api.md)
for routes, response formats, and curl examples.

## Mutable settings

Platform configuration, secrets, storage paths, processing capacity, and model
allowlists remain controlled by `.env`. Workspace owners can select a model
from those allowlists, choose the transcription language and recap temperature,
rename the workspace, and manage editor/viewer access. Campaign prompts are
editable by owners and editors. Every user can change their own credentials and
default workspace.

The TUI exposes these areas under **Settings → Workspace / Campaign / User**.
The equivalent scriptable commands are:

```console
uv run notekeeper cli settings workspace show
uv run notekeeper cli settings workspace set --whisperx-model small --language ru
uv run notekeeper cli settings workspace members list
uv run notekeeper cli settings campaign show <campaign-id>
uv run notekeeper cli settings user show
```

Use `notekeeper cli --workspace <workspace-id> ...` to target an accessible
workspace explicitly. Run `notekeeper cli settings --help` for all update and
reset commands. Existing `recap-prompts show/set` commands remain supported.

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
