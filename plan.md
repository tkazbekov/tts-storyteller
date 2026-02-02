# Qwen3 Storyteller — Plan

**Goal:** a story-oriented “storyteller” product for home use (wife-first UX), built on Qwen3-TTS. Current repo is a working prototype; next steps are (1) cleanup logic, (2) move from file-based storage to Postgres, then (3) build a web app (Next.js + Tailwind + shadcn/ui).

---

## 0) Guiding principles

- **Story-first:** Stories are authored by roles, not voices; casting is a first-class concept.
- **Keep generation async:** generation stays job-based and non-blocking.
- **Determinism:** story + voice configs should produce stable outputs; incremental regeneration should be reliable.
- **Operational clarity:** strong logging, predictable error responses, and observable job states.

---

## 1) Cleanup / refactor (no feature changes)

### 1.1 Untangle API vs domain vs infrastructure

**Today:** `api/main.py` owns too much: routing, job engine, model caching, business rules.

**Target structure (suggested):**

- `api/` — FastAPI routes only
- `domain/` — pure business logic (no IO)
- `services/` — orchestration (resolve + validate + generation requests)
- `infra/` — storage (file now, db later), queue, model loading, audio concat

A minimal step without moving everything at once:
- Extract job runner + model loader into `services/`.
- Keep `lib/` as-is initially but stop importing `scripts/common.py` from server code.

### 1.2 Make generation options consistent

- Align `GenerateRequest.concat` default with server behavior (currently model default `False`, API effectively defaults `True` when missing).
- Decide and document:
  - default concat = `true` or `false`
  - what `outputPath` means when concat is false (directory vs file)

### 1.3 Standardize ID rules

- Story IDs:
  - currently derived from title, sanitized; collisions are possible.
  - Decide strategy: either (a) slug + numeric suffix, or (b) UUID internal id + display title.
- Voice IDs:
  - keep as user-chosen stable identifiers (e.g., `narrator_male`).

### 1.4 Job engine hardening (still file-based)

- Make job state transitions explicit (queued → running → succeeded/failed).
- Add timestamps: `createdAt`, `startedAt`, `finishedAt`.
- Track progress fields where possible (even coarse: “line 12/80”).

### 1.5 Testing + lint discipline

- Add unit tests for:
  - resolution order
  - validation errors
  - incremental hashing + changed-index detection
- Add a few integration tests for API endpoints.

### 1.6 Make FastAPI routes async

- Right now the database repositories still call `_run_sync` wrappers when the synchronous routes hit them. That works in CLI scripts but fails inside Uvicorn’s existing event loop (`Task … got Future … attached to a different loop`). Convert the routes (and any helpers that call them) to async so they invoke the `_async` repository methods directly, remove `_run_sync`, and keep the job worker working without extra loops.

**Deliverable for Phase 1:** refactor PR(s) with same endpoints and behavior, cleaner layout, better defaults and tests.

---

## 2) Move storage from files → Postgres

### 2.1 Decide what stays “file”

Even with Postgres, generated artifacts are large. Recommended split:

- **Postgres:** story templates, roles, lines, casting, voice configs, pools, jobs, metadata
- **Filesystem (or S3/MinIO later):** prompt `.pt`, voice ref WAVs, generated line WAVs, full WAV

You can still *index* file paths in DB.

### 2.2 Schema proposal (first pass)

**voices**
- `id (pk, text)`
- `language text`
- `instruction text`
- `sample_text text`
- `prompt_path text nullable`
- `ref_audio_path text nullable`
- `created_at`, `updated_at`
- optional: `config_hash text` (for regen decisions)

**voice_pools**
- `id (pk, uuid)`
- `name text unique`

**voice_pool_members**
- `pool_id uuid fk`
- `voice_id text fk`
- `(pool_id, voice_id)` unique

**stories**
- `id (pk, uuid)`
- `slug text unique` (optional)
- `title text`
- `language text`
- `default_voice_id text fk`
- `created_at`, `updated_at`

**story_roles**
- `id (pk, uuid)`
- `story_id uuid fk`
- `role_id int` (the author-facing number)
- `name text`
- `notes text nullable`
- unique `(story_id, role_id)`

**story_lines**
- `id (pk, uuid)`
- `story_id uuid fk`
- `line_id int` (author-facing)
- `role_id int` (references story_roles.role_id within story)
- `text text`
- `extra text nullable`
- `actor_voice_id text nullable`
- unique `(story_id, line_id)`

**story_casting**
- `story_id uuid fk`
- `role_id int`
- `voice_id text fk`
- unique `(story_id, role_id)`

**jobs**
- `id (pk, uuid)`
- `type text` (generate, voice_generate)
- `status text`
- `story_id uuid nullable`
- `voice_id text nullable`
- `message text nullable`
- `request_params jsonb`
- `output_path text nullable`
- timestamps

**story_generation_metadata**
- `story_id uuid pk`
- `language text`
- `line_hashes jsonb` (array)
- `updated_at`

### 2.3 Data migration

- Write a one-off migration script:
  - import `voices/voices.json` into `voices`
  - import `voices/pools.json` into pools + members
  - import `stories/*.json` into stories/roles/lines/casting
  - optionally: read `.voice_metadata.json` and `.generation_metadata.json` into DB tables

### 2.4 Repository interface

Introduce a repository layer (even if simple):
- `StoryRepo` (get/list/create/update)
- `VoiceRepo` (get/list/create/update/delete)
- `JobRepo` (create/update/get/list)

Then swap implementations:
- Phase 2a: keep file impl but behind repos
- Phase 2b: add Postgres impl and flip a config flag

**Deliverable for Phase 2:** API behavior preserved, storage backed by Postgres, artifacts still on disk.

---

## 3) Web app (Next.js + Tailwind + shadcn/ui)

### 3.1 UX flows (wife-first)

**Core screens**
1) **Stories**
   - list stories, create new
2) **Story editor**
   - roles panel (roleId + name)
   - casting UI (role → voice)
   - lines editor (role select + text + “extra”)
3) **Generate**
   - “Generate full story” button
   - show job progress/status
   - audio player for full wav + per-line list
4) **Voices**
   - list voices, preview (play ref audio)
   - create/update voice (instruction + sample_text)
   - show generation status for voice prompt creation

### 3.2 API needs for UI

You already have most endpoints. For a smoother UI, consider adding:
- `GET /jobs?storyId=...` and/or `GET /jobs?limit=...`
- `GET /stories/{id}/latest-job`
- `GET /stories/{id}/audio` that returns structured info (full wav exists? list of files?)

### 3.3 Auth

If it’s home-only, simplest:
- no auth on LAN + optional basic auth via reverse proxy
or
- single API key header

---

## 4) Execution order (concrete)

### Milestone A — “Clean core” (1–3 days)
- Refactor `api/main.py` into smaller modules
- Fix concat default mismatch
- Add minimal job timestamps
- Add 5–10 unit tests

### Milestone B — “DB-backed” (2–5 days)
- Add Postgres via docker-compose
- Implement repos + SQLAlchemy/SQLModel (or psycopg + pydantic)
- Write import script from existing files
- Flip API to DB repos

### Milestone C — “Web MVP” (3–7 days)
- Next.js app skeleton + shadcn
- Stories list + story editor + generate + audio playback
- Voice list + voice create/regenerate

---

## 5) Decisions I need from you

1) **Story IDs:** keep slug as primary key, or move to UUID + slug?
2) **Artifacts:** keep on local disk long-term, or plan for S3/MinIO?
3) **Concurrency:** do we ever want multiple jobs at once, or single-worker is fine?
4) **Auth:** none (LAN only) vs API key.

---

## 6) First “cleanup” tasks I’d start with (ready-to-do)

- Extract job engine from `api/main.py` into `services/jobs.py`
- Extract model loader + cache into `services/models.py`
- Create `services/story_generation.py` and `services/voice_generation.py` that call into `lib/*`
- Align `GenerateRequest.concat` default (pick one) and update README + OpenAPI if needed
- Add `GET /health` returning `{status:"ok"}` + optionally model cache state

---

When you confirm the decisions in section 5, I’ll convert this into a task-by-task implementation checklist (with exact file moves and PR-sized steps).
