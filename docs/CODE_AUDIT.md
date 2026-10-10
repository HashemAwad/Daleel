# Daleel code audit — 11 October 2026

This is the current risk register after a repository-wide audit. It separates
demo blockers from honest product limitations so the team fixes the right things.

## P0 — resolve before the final demo

1. **Knowledge coverage is still narrow.** Only two distinct verified procedure
   sources are loaded. The eight-question starter evaluation is green, but it is
   synthetic and cannot support a broad accuracy claim. Add the healthcare
   teammate's 5–8 priority procedures and a reviewed 40–60 question set.
2. **Facility data needs human spot-checking.** OSM/HOT supplies coordinates and
   types, but not ministry approval, ownership, opening hours or pharmacy stock.
   Spot-check the names/types used in the scripted demo. Never call a hospital
   public/private unless a verified ownership field is added.
3. **Choose the demo model by measurement.** Compare Gemini, `qwen2.5:7b` and
   `qwen3.5:9b-q8_0` on the same reviewed Arabic/Arabizi/French/English questions.
   Record accuracy, wrong-language rate and median response time. Newer/larger
   does not automatically win the live-demo slot.
4. **Production-like environment check.** Set a strong `SESSION_HASH_SALT`, use
   real WhatsApp credentials, enable webhook signature enforcement, start the
   retention loop, verify geolocation over HTTPS, and run `infra/reset_demo.sh`
   before rehearsal.
5. **Restart after frontend changes.** The widget is now served with
   `Cache-Control: no-store`; an already-running pre-fix server must still be
   stopped and restarted once.

## P1 — important, but not required for a controlled demo

1. `/docs`, `/openapi.json`, and `/health/channels` expose API/provider details.
   Disable or token-protect them in production.
2. CORS currently allows every origin. Restrict it to the deployed web origin.
3. Conversation memory is an in-process five-minute dictionary. It works with a
   single worker only; use Redis or Postgres before multi-worker deployment.
4. No PHC dataset is loaded. Facility records generally lack phone numbers and
   opening hours. Ownership (`private`/`public`) is not present.
5. Voice transcription exists but needs an actual Arabic/Arabizi WhatsApp voice
   rehearsal on the demo machine; model download and first-load latency matter.
6. The dashboard uses deterministic per-turn topics, while the richer AI
   classifier is not part of the runtime retention path. Align vocabularies
   before presenting detailed policy insights.
7. The public API has no application-level rate limiter. Add one before exposing
   a non-demo deployment to control spam and model cost.
8. Dependencies use broad `>=` ranges and there is no GitHub Actions workflow.
   Freeze a known-good lock file and add CI after the demo.

## Fixed during this audit

- Ambiguous Arabic/Arabizi/French/English wording is mapped through constrained
  semantic labels; the model can choose intent/facility type but never facts.
- A phonetic fallback matches Arabizi tokens to one canonical concept instead of
  maintaining an endless spelling list, so offline/self-host startup still works.
- Short follow-ups preserve the structured previous facility type and understand
  “closest one” semantically; unknown types trigger a clarification, not pharmacy.
- Public/private follow-ups explain the missing field without an unrelated source
  or a misleading “No official source” badge.
- Directory and medicine responses are deterministic rather than model-rewritten.
- OpenStreetMap credit is not appended to chat responses; attribution appears once
  outside the conversation.
- Anonymous API calls receive unique non-storable session identifiers.
- `/chat` limits text to 2,000 characters and validates latitude/longitude.
- Arabizi price terms route to medicine lookup; medicine strengths such as “5 mg”
  no longer trigger the dosing refusal by themselves.
- Missing prices are represented as unavailable, never `None` or zero.
- Unanswered results retain their original tool/topic for useful analytics.
- Provider import failures are logged and data stubs return no fabricated facts.
- Redaction handles repeated separators, underscores and invisible direction marks.
- Frontend responses are served with `Cache-Control: no-store`.

## Verification evidence

- Full database-backed suite: **313 passed, 2 skipped** before the final
  presentation-only improvements; rerun before committing.
- Starter evaluation: **8/8**, across Arabic, Arabizi and English.
- `pip check`: no broken installed requirements.
- No tracked API keys or private key files found by the repository scan.
- `ruff` and `pip-audit` are not installed, so lint and dependency-CVE scanning
  remain unperformed.
