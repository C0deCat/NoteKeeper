# NoteKeeper Project Overview

## What NoteKeeper Does

NoteKeeper automates the work of turning long tabletop role-playing game
recordings into useful session notes. It accepts audio from a game session,
prepares it for speech processing, produces a timestamped transcript, identifies
the people speaking, and generates a structured recap that can be reviewed or
exported as Markdown.

The application organizes recordings around campaigns and participants. Voice
samples associate known players with their speech, while a review step allows
uncertain or guest speakers to be corrected before the final recap is created.
Long-running work is represented as processing jobs with visible progress and
recoverable states.

## Motivation

NoteKeeper grew out of my hobby: I run tabletop role-playing games. A typical
game session lasts three to five hours, and turning that much play into clear,
useful notes repeatedly took a significant amount of time. I wanted to automate
that process without losing the details that make a campaign coherent from one
session to the next.

The project is intended to reduce the mechanical work of listening back,
transcribing dialogue, identifying speakers, and assembling a recap. The game
master can instead spend that time preparing future sessions and working with
the parts of the story that still benefit from human judgment.

## Processing Workflow

A typical NoteKeeper workflow consists of the following steps:

1. Create a campaign and register its participants.
2. Add a voice sample for each participant.
3. Submit one or more audio files from a game session.
4. Normalize and, when necessary, concatenate the audio with FFmpeg.
5. Transcribe, align, and diarize the recording with WhisperX.
6. Match anonymous speaker labels to known participants using voice samples.
7. Review mappings that cannot be resolved confidently.
8. Generate a session recap with DeepSeek.
9. Preview or export the transcript and recap as Markdown.

## Technology Stack

NoteKeeper is written for Python 3.11 and uses `uv` for reproducible dependency
and virtual-environment management.

- **Typer and Rich** provide the scriptable command-line interface and progress
  reporting.
- **Textual** provides the interactive terminal user interface.
- **SQLite** stores campaigns, participants, recordings, jobs, transcripts,
  speaker mappings, and recaps locally.
- **FFmpeg and FFprobe** inspect, normalize, and combine audio recordings.
- **WhisperX** performs speech transcription, timestamp alignment, and speaker
  diarization.
- **PyTorch and SpeechBrain** support the machine-learning and speaker
  identification parts of the pipeline.
- **DeepSeek**, accessed through the **OpenAI Python SDK**, generates structured
  recaps from processed transcripts.
- **Pydantic and Pydantic Settings** define validated application configuration
  loaded from environment variables and `.env` files.
- **pytest and Pyright** support automated testing and static type checking.

## Architecture

NoteKeeper follows a layered, hexagonal architecture. Business concepts and
rules are kept separate from frameworks, databases, machine-learning libraries,
and user interfaces. Dependencies point inward toward the domain, while external
systems are connected through application ports and infrastructure adapters.

The main layers are:

- `domain`: campaign models, value objects, validation, and business rules with
  no dependency on infrastructure or UI frameworks;
- `application`: use cases, commands, results, and ports that coordinate the
  domain without selecting concrete external implementations;
- `infrastructure`: adapters for SQLite, the filesystem, FFmpeg, WhisperX,
  DeepSeek, tokenization, and runtime services;
- `interfaces`: the Typer/Rich CLI and Textual TUI that translate user actions
  into application use cases;
- `composition`: configuration and dependency wiring that assemble the concrete
  application at runtime.

This separation makes the current console application an interface rather than
the center of the system. A future desktop interface can reuse the same domain
and application layers, replacing or extending only the outer interface and
composition code. The same core can also serve as the foundation for a web
application API by adding HTTP and background-worker adapters without moving
business logic into the web layer.

See [Architecture](architecture.md) for a detailed description of the layers,
dependency rules, ports, adapters, and processing jobs.
