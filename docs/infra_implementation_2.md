# Remaining Infrastructure Tasks for Stage 1

## Summary

This document tracks the infrastructure work still needed to complete Stage 1:
Campaign-Based Pipeline. The current infrastructure already covers SQLite
repositories, local campaign artifact storage, campaign folder scanning, local
audio metadata probing, runtime clock/id generation, and basic composition.

The remaining work is the real processing infrastructure: audio preparation,
WhisperX transcription/diarization, sample-based speaker mapping, transcript
tokenization, DeepSeek recap generation, runtime configuration, and persistence
of useful pipeline execution metadata.

Tasks are written to be as independent as possible. When a task needs a small
application/domain contract change, that dependency is called out explicitly.

## Tasks

### 1. Add FFmpeg audio preparation adapter

Implement an infrastructure adapter for the `AudioProcessor` port.

Expected adapter:

- `FfmpegAudioProcessor`
- package: `src/notekeeper/infrastructure/ffmpeg`

Responsibilities:

- Resolve input `AudioTrack` and `VoiceSample` artifacts through local artifact
  storage.
- Normalize audio into a processing-friendly format, for example 16 kHz mono WAV.
- Build the Stage 1 prepared audio by prepending or appending campaign voice
  samples to the session recording.
- Store prepared audio under a campaign-safe artifact path or temp/work path.
- Return an `ArtifactRef` for the prepared audio.
- Raise infrastructure-specific errors for missing files, unsupported formats,
  failed subprocesses, and unsafe paths.

Useful settings:

- `ffmpeg_path`
- `ffprobe_path`
- `processing_work_root`
- normalized sample rate, channels, codec/container

Contract note:

- The current `AudioProcessor.prepare_session_audio()` returns only an
  `ArtifactRef`. Stage 1 speaker mapping is easier and safer if the pipeline also
  knows where every inserted voice sample appears in the prepared audio and where
  the real session starts. Consider adding a small prepared-audio manifest/result
  DTO before relying on concatenated voice samples.

### 2. Add prepared-audio manifest storage

Persist technical metadata about prepared audio independently from the audio
processor implementation.

Expected package:

- `src/notekeeper/infrastructure/filesystem` or
  `src/notekeeper/infrastructure/ffmpeg`

Responsibilities:

- Save a JSON manifest for prepared audio.
- Include source session artifact, prepared artifact, inserted voice sample
  ranges, session offset, duration, normalization settings, ffmpeg command
  metadata, and created timestamp.
- Keep manifest URIs relative to `storage_root`.
- Make manifests readable by later processing steps and debugging tools.

Can be implemented before or after `FfmpegAudioProcessor` if the manifest schema
is agreed first.

### 3. Add WhisperX transcription adapter

Implement an infrastructure adapter for the `Transcriber` port.

Expected adapter:

- `WhisperXTranscriber`
- package: `src/notekeeper/infrastructure/whisperx`

Responsibilities:

- Load/configure WhisperX model from composition settings.
- Run ASR on the prepared audio artifact.
- Run alignment if available/configured.
- Run diarization and assign anonymous speaker labels.
- Convert WhisperX output into domain `Transcript` and `TranscriptSegment`
  objects.
- Preserve segment indexes, time ranges, speaker labels, and text.
- Surface tool failures as infrastructure errors with useful context.

Useful settings:

- WhisperX model name
- device: CPU/CUDA
- compute type
- batch size
- language
- diarization enabled flag
- Hugging Face token or diarization auth settings
- temp/cache paths

Contract note:

- If prepared audio contains voice samples, transcript timestamps may need to be
  shifted back to the original session timeline and sample-only transcript
  segments may need to be filtered. That requires the prepared-audio manifest
  from task 2.

### 4. Add raw WhisperX payload persistence

Persist raw or lightly normalized WhisperX output for reproducibility and
debugging.

Expected package:

- `src/notekeeper/infrastructure/whisperx`

Responsibilities:

- Save ASR/alignment/diarization payloads as JSON artifacts.
- Link payload artifacts to the job, transcript, or processing manifest.
- Store model/config metadata used for the run.
- Avoid putting large raw payloads directly into SQLite when artifact storage is
  a better fit.

This task is independent from the domain transcript repository if raw payloads
are stored as separate artifact files.

### 5. Add Stage 1 sample-based speaker identifier

Implement an infrastructure adapter for the `SpeakerIdentifier` port.

Expected adapter:

- `SampleBasedSpeakerIdentifier`
- package: `src/notekeeper/infrastructure/speaker_mapping`

Responsibilities:

- Use known voice sample intervals from prepared audio to infer which anonymous
  WhisperX speaker label belongs to which campaign participant.
- Produce `SpeakerMapping` objects with source `sample-based` or the closest
  available enum value.
- Mark uncertain mappings when samples do not clearly map to a single speaker
  label.
- Detect duplicate/conflicting cases where multiple participants appear mapped
  to one anonymous speaker label.
- Leave unresolved speaker labels for the existing review flow.

Contract note:

- This adapter needs prepared-audio sample ranges. If the current port remains
  `identify(campaign, transcript)`, the ranges must be recoverable from stored
  manifests or transcript metadata. Passing a prepared-audio context explicitly
  would be cleaner.

### 6. Add speaker mapping metadata persistence

Persist automatic and manual speaker mapping decisions for each processing job.

Expected package:

- `src/notekeeper/infrastructure/sqlite`

Responsibilities:

- Store anonymous label, participant id, named label, confidence, source, status,
  and related warning/diagnostic details.
- Allow listing mappings by job or transcript.
- Preserve automatic mappings that led to `WAITING_FOR_REVIEW`.
- Preserve manual mappings applied during review.

This may require adding an application port if mappings should be first-class
application data rather than embedded job metadata.

### 7. Add tokenizer adapter

Implement an infrastructure adapter for the `Tokenizer` port.

Expected adapter:

- `TiktokenTranscriptTokenizer`
- package: `src/notekeeper/infrastructure/tokenization`

Responsibilities:

- Render transcript segments into stable text chunks.
- Split transcripts around the Stage 1 target of about 25-35k tokens.
- Prefer segment boundaries over arbitrary text cuts.
- Preserve `time_range` and `source_segment_indexes` in each `TranscriptChunk`.
- Handle very long individual segments predictably.

Useful settings:

- tokenizer/model encoding name
- target token count
- maximum token count
- optional overlap size

This task is independent from DeepSeek if it only implements the tokenizer port.

### 8. Add DeepSeek recap generator

Implement an infrastructure adapter for the `RecapGenerator` port.

Expected adapter:

- `DeepSeekRecapGenerator`
- package: `src/notekeeper/infrastructure/deepseek`

Responsibilities:

- Call DeepSeek API for each transcript chunk.
- Generate partial recap Markdown for `generate_chunk()`.
- Combine partial recaps into final Markdown for `combine_chunks()`.
- Include prompts suitable for tabletop role-playing session notes.
- Handle API errors, retries, rate limits, timeouts, and empty responses.
- Keep the application layer independent from API client details.

Useful settings:

- API key
- base URL
- model name
- temperature
- timeout
- retry count/backoff
- prompt templates or prompt file paths

### 9. Add LLM request/response artifact logging

Persist recap-generation diagnostics without coupling application logic to the
DeepSeek client.

Expected package:

- `src/notekeeper/infrastructure/deepseek`

Responsibilities:

- Save prompt metadata, model settings, request ids, token estimates, chunk
  indexes, and response metadata.
- Store full prompts/responses only when configured, because transcripts may be
  sensitive.
- Link diagnostics to recap chunks or recap id where possible.

This task can be implemented after the DeepSeek adapter, or as a no-op logger
interface first.

### 10. Extend composition settings for processing adapters

Extend `NoteKeeperSettings` and `build_infrastructure()` to support real Stage 1
processing adapters.

Expected files:

- `src/notekeeper/composition/settings.py`
- `src/notekeeper/composition/factory.py`

Responsibilities:

- Add ffmpeg, WhisperX, tokenizer, DeepSeek, and processing work directory
  settings.
- Instantiate the concrete infrastructure adapters.
- Keep optional heavy dependencies lazy where practical.
- Expose the adapters in `InfrastructureBundle` so interfaces can wire
  `RunProcessingJob`, `ReviewSpeakerMappings`, and `GenerateRecap`.

This task can be split into smaller wiring patches as each adapter lands.

### 11. Add processing error handling and job failure persistence

Make infrastructure failures visible through job metadata.

Expected area:

- application processing use cases
- infrastructure error types
- SQLite job repository

Responsibilities:

- Convert adapter exceptions into failed job state.
- Save `error_message` and update `updated_at`.
- Preserve warnings generated before failure where useful.
- Avoid losing partial transcript or raw artifact data that may help recovery.

Contract note:

- `ProcessingJob.error_message` already exists, and SQLite persists it. The
  processing use case currently does not wrap infrastructure failures into a
  failed job state.

### 12. Add end-to-end infrastructure smoke tests with fakes or fixtures

Add tests that exercise infrastructure wiring without requiring a real 3-5 hour
recording.

Expected tests:

- FFmpeg adapter test with generated tiny WAV files.
- Tokenizer test with deterministic transcript segments.
- DeepSeek adapter test with a fake HTTP/client transport.
- WhisperX adapter conversion test using a saved sample payload or monkeypatched
  WhisperX runner.
- Composition test proving all Stage 1 adapters can be built from settings.

Tests should avoid GPU and network requirements unless explicitly marked as
integration tests.

## Suggested Implementation Order

The tasks are intentionally separable, but this order minimizes contract churn:

1. Prepared-audio manifest contract and storage.
2. FFmpeg audio preparation.
3. WhisperX payload conversion and transcriber adapter.
4. Sample-based speaker identifier.
5. Tokenizer.
6. DeepSeek recap generator.
7. Composition wiring.
8. Mapping/diagnostic persistence.
9. Job failure handling.
10. Broader smoke/integration tests.

