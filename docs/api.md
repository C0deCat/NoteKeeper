# NoteKeeper Local API

## Profile and startup

The HTTP API is a local development profile backed by `LocalAuthProvider`,
SQLite, managed filesystem artifacts, and the single-host process job queue.
It is intended for `127.0.0.1` or another trusted network boundary, not direct
Internet exposure.

Enable authentication and start one API process:

```powershell
$env:NOTEKEEPER_AUTH_ENABLED = "true"
uv run notekeeper api --host 127.0.0.1 --port 8000
```

API mode refuses to start when `NOTEKEEPER_AUTH_ENABLED=false`. OpenAPI is
available at `/openapi.json` and the interactive documentation at `/docs`.

## Authentication

The client-facing contract is independent of the configured credential
provider. The local profile validates login/password through the existing local
provider and returns opaque NoteKeeper tokens. A later backend auth adapter can
replace that provider without changing protected resource routes.

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/me
GET  /api/v1/workspaces
```

Login and registration accept JSON:

```json
{"login": "root", "password": "root"}
```

The response contains `access_token`, `refresh_token`, `token_type`,
`expires_in`, `refresh_expires_in`, and `user`. Refresh rotates both tokens and
invalidates the old pair. Logout accepts `{"refresh_token":"..."}` and revokes
the session. Tokens are stored only in memory, so a server restart requires a
new login.

Protected requests use:

```http
Authorization: Bearer nk_access_...
```

## Routes

Every user resource belongs to a workspace. A missing or foreign direct ID is
reported as `404`; an authenticated member with an insufficient role receives
`403`.

| Method | Path |
| --- | --- |
| `GET` | `/health` |
| `GET`, `POST` | `/api/v1/workspaces/{workspace_id}/campaigns` |
| `GET`, `PATCH`, `DELETE` | `/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}` |
| `GET`, `POST` | `/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/participants` |
| `PATCH`, `DELETE` | `/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/participants/{participant_id}` |
| `GET`, `POST` | `/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/participants/{participant_id}/voice-samples` |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/voice-samples/{sample_id}` |
| `GET`, `POST` | `/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/recordings` |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/recordings/{recording_id}` |
| `GET` | `/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/jobs` |
| `POST` | `/api/v1/workspaces/{workspace_id}/recordings/{recording_id}/jobs` |
| `GET`, `DELETE` | `/api/v1/workspaces/{workspace_id}/jobs/{job_id}` |
| `POST` | `/api/v1/workspaces/{workspace_id}/jobs/{job_id}/queue` |
| `POST` | `/api/v1/workspaces/{workspace_id}/jobs/{job_id}/cancel` |
| `POST` | `/api/v1/workspaces/{workspace_id}/jobs/{job_id}/restart` |
| `POST` | `/api/v1/workspaces/{workspace_id}/jobs/{job_id}/speaker-review` |
| `GET` | `/api/v1/workspaces/{workspace_id}/jobs/{job_id}/events` |
| `GET` | `/api/v1/workspaces/{workspace_id}/transcripts/{transcript_id}` |
| `GET` | `/api/v1/workspaces/{workspace_id}/recaps/{recap_id}` |

Collection responses use `{"items": [...]}` without pagination in the local
version. Transcript and recap responses use `{"id":"...","markdown":"..."}`.
Recording and sample responses contain audio metadata but never artifact URIs.

Recording upload is multipart with a required `file` and optional `title`.
It returns `201` with a normalized recording and a `pending` job. Queueing is a
separate request returning `202`; it never waits for pipeline completion.
Voice-sample upload accepts `file` and optional RFC 3339 `recorded_at`.

## Errors and request IDs

Every response includes `X-Request-ID`. Errors use one envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Resource was not found",
    "request_id": "req_...",
    "details": {}
  }
}
```

The primary statuses are `401` for an invalid session, `403` for role denial,
`404` for hidden resources, `409` for state conflicts, `413` for request size,
`415` for unsupported file extensions, `422` for validation, and `503` for an
unavailable local dependency.

## SSE progress

`GET .../jobs/{job_id}/events` returns `text/event-stream`. It emits an initial
`status` event, `progress` events, a heartbeat comment every 15 seconds, and a
final status before closing for completed, failed, canceled, or paused-for-review
jobs. Disconnecting removes the progress listener.

## Curl outline

The examples below assume the server is already running. They are intentionally
an outline: replace IDs and tokens with values returned by preceding requests.

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{"login":"root","password":"root"}'
curl.exe http://127.0.0.1:8000/api/v1/workspaces `
  -H "Authorization: Bearer <access-token>"
curl.exe -X POST http://127.0.0.1:8000/api/v1/workspaces/<workspace-id>/campaigns `
  -H "Authorization: Bearer <access-token>" `
  -H "Content-Type: application/json" `
  -d '{"name":"API demo"}'
curl.exe -X POST http://127.0.0.1:8000/api/v1/workspaces/<workspace-id>/campaigns/<campaign-id>/recordings `
  -H "Authorization: Bearer <access-token>" `
  -F "file=@sample.wav" -F "title=API recording"
curl.exe -N http://127.0.0.1:8000/api/v1/workspaces/<workspace-id>/jobs/<job-id>/events `
  -H "Authorization: Bearer <access-token>"
curl.exe -X POST http://127.0.0.1:8000/api/v1/workspaces/<workspace-id>/jobs/<job-id>/queue `
  -H "Authorization: Bearer <access-token>"
```
