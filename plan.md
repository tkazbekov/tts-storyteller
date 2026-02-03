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

Phase 1 is finished: the job engine, model loader, and metadata resolver now live in `services/`, the FastAPI routes and helper services await the async repositories, `_run_sync` is gone, and the tooling/docs describe the async-first posture. What remains in this slice is ordinary maintenance (tests, lint, docs) while Phase 2 and Phase 3 move forward.

---

## 2) Move storage from files → Postgres

Phase 2 is done: the migrations, data import, and Postgres-backed repositories are live, and the Makefile/README describe the `apply-migrations`/`migrate-legacy` helpers plus `.env` loading so you can reprovision the schema on demand. Artifacts such as prompts and wavs stay on local disk per the home-project direction.

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
