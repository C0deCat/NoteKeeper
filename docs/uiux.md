# UI/UX

## CLI model

NoteKeeper exposes two command-line surfaces over the same application use cases:

- Typer commands for fast, scriptable execution of use cases, testing, and automation.
- A Textual TUI for interactive, keyboard-driven work with the same use cases.

Both surfaces are interface adapters. They must not contain business logic or create
infrastructure directly. Runtime wiring belongs in the composition layer, which passes
the required application use cases and repositories to the selected interface.

## Typer commands

Typer commands are optimized for direct actions and repeatable workflows:

- create and inspect campaigns;
- add participants and voice samples;
- submit recordings for processing;
- run or inspect processing jobs;
- review speaker mappings when automation needs explicit arguments;
- generate and export transcripts and recaps;
- support local testing, shell scripts, and future automation.

Typer should remain useful even after the TUI exists. It is the preferred surface for
CI-like checks, scripted batch processing, and precise command invocation.

## Textual TUI

The TUI is a dashboard-first interactive interface. It should support keyboard
navigation with arrow keys, selection with Enter, forms instead of parameter-heavy
commands, and explicit screens for long-running flows.

The main dashboard must show:

- the currently selected campaign and a way to switch between campaigns;
- running and recent jobs, with status and stage-based or indeterminate progress bars;
- audio recordings for the selected campaign, including title or URI, duration, job
  status, and whether transcript and recap artifacts exist;
- campaign players, including display name, whether each player has a voice sample,
  and a compact readiness signal for processing;
- pipeline warnings and job errors that need user attention.

The current domain model has `JobStatus`, but does not yet expose numeric progress.
Until a progress contract is added, the TUI should represent work using job status,
known pipeline stages, and indeterminate progress. A future implementation may add
fields such as `progress_percent` and `progress_stage` to the job-facing application
contract.

## Required TUI flows

The TUI must cover the same core use cases as Typer:

- create a campaign;
- add players to a campaign;
- add voice samples for players;
- submit a recording for processing;
- start or observe processing jobs;
- review speaker mappings when a job is `WAITING_FOR_REVIEW`;
- preview transcript and recap Markdown artifacts;
- open, export, or copy artifact paths when transcript or recap files are available.

Audio and voice sample forms should include a metadata preflight step before saving.
The preflight should display the selected path or URI, duration, format, size when
known, and any metadata-reading errors that prevent the use case from running.

Speaker mapping review is a first-class TUI flow. For jobs waiting for review, the TUI
should show unresolved anonymous speaker labels, candidate players, warnings, and a
confirmation action that submits manual mappings through the application layer.

## Diagnostics and settings

The TUI should include a read-only diagnostics/settings screen. It should display
runtime information that helps the user understand the current environment, such as:

- configured data and artifact paths;
- whether required provider configuration is present;
- selected runtime mode, for example CPU or GPU when that becomes available;
- recent pipeline warnings and job error messages.

This screen is informational only for the initial TUI contract. Editing settings remains
the responsibility of config files, environment variables, Typer commands, or future
dedicated settings work.
