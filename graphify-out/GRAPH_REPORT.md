# Graph Report - hack4health  (2026-10-11)

## Corpus Check
- 103 files · ~71,315 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: .csv 6, (none) 2, .example 1)

## Summary
- 1252 nodes · 2551 edges · 80 communities (57 shown, 23 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 301 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- FastAPI App & Model Load
- Ollama Local LLM
- Transcript Storage
- Directory Search
- Project Overview (CLAUDE.md)
- Pseudonymous Identity
- Channel Tests
- Tech Stack & Research
- Pipeline Orchestration
- Architecture & Workflow Docs
- Arabizi & Eval Research
- Shared Contracts
- Data E2E Tests
- Seed Loaders
- Dashboard Metrics
- Prompts & Stubs
- Medicine Lookup
- Meta WhatsApp Tests
- Medicine Tests
- Tool Router
- Seed Data Research
- Topic Classifier
- Lexical Search & AI Deps
- Hosted LLM
- Whisper Transcriber
- Voice Pipeline Tests
- Seed Builder (Drugs)
- Classifier & Eval Runner
- PII Redaction
- Voice Tests
- Twilio WhatsApp Webhook
- Schema Tests
- Procedure Ingestion
- Plan & Data Sources
- DB Access & Demo
- Privacy & Retention Design
- LLM Backend Decision
- Language Detect & Transcribe CLI
- Ingest Tests
- Demo Metrics Generator
- Test Fixtures
- Transcribe Tests
- Anthropic LLM
- LLM Failover
- Retrieval Search Tests
- Medicine Seed Enrichment
- Eval Tests
- Retention Job
- Embeddings & Retrieval
- WhatsApp Inquiry Builder
- Grounding & Determinism
- Code Audit Risks
- Demo Deployment Setup
- Lexical Ingestion
- Contract Protocols
- Retrieval DB Tests
- Twilio Signature Check
- Channel Settings
- Media Download Cap
- Metrics Tests
- Whisper Vocabulary Tests
- Demo Reset Tests
- Voice Note Fetch
- Demo Mode Failure Tests
- Laptop Setup Script
- Run Demo Script
- VM Setup Script
- Signature Test Env
- Reset Demo Script
- AWS Tunnel Script
- Page Serving Test
- Privacy Contract Test
- Small-Group Suppression Test
- Exact Totals Test
- Withheld Notice Test
- Top-N Cap Test
- Mock Topic Vocabulary Test
- Mock Caza Test
- Topic Check Constraint Test

## God Nodes (most connected - your core abstractions)
1. `Inquiry` - 41 edges
2. `Answer` - 39 edges
3. `get_conn()` - 31 edges
4. `record()` - 30 edges
5. `TranscriberImpl` - 24 edges
6. `_handle()` - 23 edges
7. `Daleel Open-Source Accelerator Map` - 23 edges
8. `_inq()` - 21 edges
9. `ToolResult` - 19 edges
10. `_inq()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `One anonymous Metadata row per turn (data.transcripts.record)` --references--> `record()`  [EXTRACTED]
  CLAUDE.md → src/data/transcripts.py
- `Channel privacy rules (ignore ProfileName, log lengths only)` --semantically_similar_to--> `Privacy by design (redact before model call, temporary transcripts, salted user_ref)`  [INFERRED] [semantically similar]
  src/channels/README.md → CLAUDE.md
- `Small-group suppression: groups under k merged as Other` --semantically_similar_to--> `Privacy by design (redact before model call, temporary transcripts, salted user_ref)`  [INFERRED] [semantically similar]
  web/dashboard.html → CLAUDE.md
- `Privacy by design (redact before model call, temporary transcripts, salted user_ref)` --references--> `redact()`  [EXTRACTED]
  CLAUDE.md → src/ai/redaction.py
- `ProcedureSearchImpl` --implements--> `shared.contracts Protocols (module contract)`  [EXTRACTED]
  src/ai/retrieval.py → CLAUDE.md

## Import Cycles
- 3-file cycle: `src/ai/transcribe.py -> src/core/pipeline.py -> src/core/providers.py -> src/ai/transcribe.py`
- 4-file cycle: `src/ai/transcribe.py -> src/core/pipeline.py -> src/core/safety.py -> src/core/providers.py -> src/ai/transcribe.py`
- 4-file cycle: `src/ai/transcribe.py -> src/core/pipeline.py -> src/core/router.py -> src/core/providers.py -> src/ai/transcribe.py`
- 4-file cycle: `src/ai/transcribe.py -> src/core/pipeline.py -> src/data/transcripts.py -> src/core/providers.py -> src/ai/transcribe.py`

## Hyperedges (group relationships)
- **Independent parallel dev via contracts, stubs and folder ownership** — docs_contracts_contracts_py_source, docs_contracts_providers_try_import, docs_workflow_own_folder_rule, docs_plan_sprint0_shared [INFERRED 0.85]
- **Privacy pipeline: redact before model, record one metadata row, retention deletes text** — docs_contracts_redact_fn, docs_contracts_metadata, docs_tickets_dev_d_d5_retention_job, docs_open_items_a12_single_metadata_writer, docs_architecture_privacy_by_design [INFERRED 0.85]
- **Grounded answer path: deterministic safety/routing/retrieval, model only phrases, fallback to hotline** — docs_handbook_golden_rule, docs_llm_model_never_chooses_facts, docs_tickets_dev_a_a3_grounding_gate, docs_compass_artifact_wf_2e02e357_ee11_5969_ae86_2f4892d93400_text_markdown_two_layer_grounding, docs_code_audit_deterministic_responses [INFERRED 0.75]
- **Privacy-by-design pipeline (redact, record anonymous metadata, delete transcripts)** — claude_privacy_requirements, src_ai_redaction_redact, src_channels_identity_user_ref, src_data_transcripts_record, src_data_retention, web_dashboard_privacy_suppression [INFERRED 0.85]
- **Module implementations of shared contracts wired via providers** — claude_shared_contracts, src_ai_retrieval_proceduresearchimpl, src_ai_transcribe_transcriberimpl, src_data_directory_directorysearchimpl, src_data_medicine_medicinelookupimpl [EXTRACTED 1.00]
- **Chat, dashboard and WhatsApp join pages sharing one design system** — web_index, web_dashboard, web_join, web_olive_beige_design_system [EXTRACTED 1.00]

## Communities (80 total, 23 thin omitted)

### Community 0 - "FastAPI App & Model Load"
Cohesion: 0.06
Nodes (18): _paths(), register(), _warm_voice(), join_link(), qr_svg(), sandbox_number(), _segno(), whatsapp_info() (+10 more)

### Community 1 - "Ollama Local LLM"
Cohesion: 0.06
Nodes (25): OllamaLLM, _inq(), test_advice_refused(), test_arabizi_closest_followup_requests_one(), test_arabizi_hospital_spelling_keeps_hospital_kind(), test_directory_followup_keeps_hospital_and_requests_one(), test_emergency(), test_grounding_fallback() (+17 more)

### Community 2 - "Transcript Storage"
Cohesion: 0.11
Nodes (36): kind(), record(), scrub(), session_key(), _storable(), topic(), _age(), _ans() (+28 more)

### Community 3 - "Directory Search"
Cohesion: 0.06
Nodes (25): _caza(), build_towns(), DirectorySearchImpl, _facility(), _haversine_km(), _load(), order(), rank() (+17 more)

### Community 4 - "Project Overview (CLAUDE.md)"
Cohesion: 0.06
Nodes (36): Pull request template, CLAUDE.md (agent instructions), Daleel health assistant (MoPH, WhatsApp + web, ar/arabizi/fr/en), Four question types: procedures, directory, medicines, hotlines, One anonymous Metadata row per turn (data.transcripts.record), One owner per folder (A core, B ai, C channels/web, D data/infra), Phase 1 chatbot / Phase 2 ministry dashboard, shared.contracts Protocols (module contract) (+28 more)

### Community 5 - "Pseudonymous Identity"
Cohesion: 0.07
Nodes (17): new_web_session(), salt_is_weak(), user_ref(), chunk(), for_whatsapp(), sources_lines(), _auth_headers(), build_inquiry() (+9 more)

### Community 6 - "Channel Tests"
Cohesion: 0.06
Nodes (21): form(), _krow(), signed(), test_directory_answers_do_not_append_dataset_credit(), test_empty_answer_still_sends_something(), test_inquiry_carries_no_raw_phone(), test_kind_breakdown_uses_the_same_small_group_suppression(), test_kinds_are_listed_per_topic_and_only_for_topics_that_have_them() (+13 more)

### Community 7 - "Tech Stack & Research"
Cohesion: 0.08
Nodes (28): Tech stack (FastAPI, Postgres+pgvector, LLMClient, Twilio+React widget), In-process 5-minute conversation memory (single worker only), Arabic RAG study (Alsubhi et al., arXiv 2506.06339), bge-m3 embeddings + bge-reranker-v2-m3, CAMeL Tools (normalization, NER, dialect ID), Core permissive stack (FastAPI, Postgres pgvector/PostGIS/pg_trgm, bge-m3, Presidio, GlotLID, faster-whisper), promptfoo/RAGAS/Langfuse eval and tracing, Hybrid FTS + vector fused by Reciprocal Rank Fusion (+20 more)

### Community 8 - "Pipeline Orchestration"
Cohesion: 0.16
Nodes (20): of(), _apply_directory_followup(), _apply_pending_town(), _ask_facility_type(), _ask_town(), _cannot_read(), _ensure_text(), _fallback() (+12 more)

### Community 9 - "Architecture & Workflow Docs"
Cohesion: 0.10
Nodes (24): Four question types (procedures, directory, medicines, hotlines), Layout and folder ownership (A/B/C/D + healthcare), Per-turn flow (normalize, safety, redact, route, ground, reply), AI-driven dev: per-role agent kickoff prompt, Daily git flow (feat/<you>/<ticket>, PR, squash), One-time setup (venv, .env, docker compose, uvicorn, pytest), Architecture diagram (channels, pipeline, router, tools, DB, model), Build log (A complete, D ~70%, C mostly done, B just started) (+16 more)

### Community 10 - "Arabizi & Eval Research"
Cohesion: 0.09
Nodes (28): Phase 1 chatbot / Phase 2 ministry dashboard, Phonetic fallback for Arabizi tokens, AladdinBench Lebanese Arabizi eval set, Arabic LLM alternatives (Fanar, Jais-2, Falcon-H1, ALLaM, SILMA) with license strings, No production-grade Lebanese Arabizi transliterator exists, Streamlit dashboard over anonymous events table, Daleel Open-Source Accelerator Map, 48-item eval set (promptfoo) with adversarial items (+20 more)

### Community 11 - "Shared Contracts"
Cohesion: 0.12
Nodes (26): Shared contracts table, Own pre-LLM multilingual emergency matcher (no LLM), Answer model, src/shared/contracts.py single source of truth, DirectorySearch protocol, CONTRACTS.md (integration contracts), Doc model, DrugRecord model (+18 more)

### Community 12 - "Data E2E Tests"
Cohesion: 0.11
Nodes (15): _ask(), _rows(), session(), test_a_whole_conversation_is_recorded_scrubbed_then_deleted(), test_directory_outage_gives_the_hotline_not_an_endless_town_question(), down(), test_directory_question_in_arabizi_returns_real_aley_pharmacies(), test_directory_question_without_a_place_asks_for_the_town() (+7 more)

### Community 13 - "Seed Loaders"
Cohesion: 0.13
Nodes (19): caza_alias_rows(), add(), ingredient_key(), load(), _rows(), _true(), _v(), place_key() (+11 more)

### Community 14 - "Dashboard Metrics"
Cohesion: 0.12
Nodes (13): _days(), _demo_wanted(), _fetch_rows(), _float_env(), metrics(), summarise(), _tally(), _targets() (+5 more)

### Community 15 - "Prompts & Stubs"
Cohesion: 0.13
Nodes (13): build_context(), stub_classify(), StubDirectory, DirectorySearch, Facility, Hotline, Metadata, Source (+5 more)

### Community 16 - "Medicine Lookup"
Cohesion: 0.15
Nodes (12): StubMedicine, match(), MedicineLookupImpl, name_words(), _num(), numbers(), _record(), _strength_value() (+4 more)

### Community 17 - "Meta WhatsApp Tests"
Cohesion: 0.15
Nodes (15): _meta_env(), payload(), post(), signed(), test_accepts_valid_signature(), test_answers_a_text_message(), test_batched_messages_all_handled(), test_delivery_receipt_is_ignored_with_200() (+7 more)

### Community 18 - "Medicine Tests"
Cohesion: 0.12
Nodes (16): test_register_is_idempotent(), app(), lookup(), _names(), test_a_number_is_a_strength_only_with_a_unit_or_right_after_the_name(), test_alias_maps_arabic_spelling_to_brand(), test_builtin_panadol_arabic_alias(), test_chat_end_to_end() (+8 more)

### Community 19 - "Tool Router"
Cohesion: 0.16
Nodes (13): _arabizi_facility_kind(), choose_tool(), directory_followup_action(), _directory_kind(), _fuzzy_token(), _resolve_caza(), route(), route_keywords() (+5 more)

### Community 20 - "Seed Data Research"
Cohesion: 0.17
Nodes (18): DB schema contract (schema.sql, 6 contract tables + helpers), data.build_seeds regeneration command, DATA_RESEARCH.md (10 Oct 2026 seed data research), drugs_new.csv (5,021 rows), facilities_new.csv (1,234 rows), Free medicines lists (three MoPH spreadsheets, no flag set), Hotline purpose discrepancy (1787, 1214 vs live seed), hotlines_new.csv (5 rows) (+10 more)

### Community 21 - "Topic Classifier"
Cohesion: 0.15
Nodes (14): classify(), detail(), _topic(), _no_db(), test_detail_is_none_for_topics_without_kinds_and_stays_in_the_closed_vocabulary(), test_detail_kinds(), test_detail_never_returns_any_of_the_question_text(), test_emergency_sets_outcome() (+6 more)

### Community 22 - "Lexical Search & AI Deps"
Cohesion: 0.13
Nodes (9): lexical_search(), src/ai README (Member B), requirements-ai.txt (AI module dependencies), camel-tools + sentence-transformers (Arabic NLP and embeddings), faster-whisper + av (local Whisper voice transcription), ProcedureSearchImpl, StubProcedureSearch, StubTranscriber (+1 more)

### Community 23 - "Hosted LLM"
Cohesion: 0.14
Nodes (5): HostedLLM, last_directory_kind(), remember_directory_kind(), remember_pending_town(), take_pending_town()

### Community 24 - "Whisper Transcriber"
Cohesion: 0.14
Nodes (7): _max_seconds(), TranscriberImpl, FakeWhisper, test_audio_reaches_the_model_in_memory_only(), test_long_note_stops_at_the_cap(), test_misdetected_language_falls_back_to_likeliest_supported_without_a_wasted_pass(), test_misdetection_with_no_probabilities_falls_back_to_arabic()

### Community 25 - "Voice Pipeline Tests"
Cohesion: 0.16
Nodes (12): hears(), RecordingLLM, _slow_pipeline(), test_a_crash_in_the_turn_is_a_reply_not_a_500(), test_a_voice_turn_stores_only_scrubbed_text(), test_emergency_voice_note_gets_140_and_stores_no_text(), test_gibberish_transcript_still_gets_a_reply(), test_in_budget_reply_is_not_sent_twice() (+4 more)

### Community 26 - "Seed Builder (Drugs)"
Cohesion: 0.26
Nodes (8): _cell(), _drug_rows(), moph_drugs(), moph_drugs_all(), moph_facilities(), _no_owner(), _table_rows(), write()

### Community 27 - "Classifier & Eval Runner"
Cohesion: 0.21
Nodes (9): _norm(), _has(), load_items(), main(), _pct(), _pipeline_handler(), run(), score() (+1 more)

### Community 28 - "PII Redaction"
Cohesion: 0.22
Nodes (11): _mask_ana(), _mask_intro(), redact(), test_email_masked(), test_idempotent_and_empty(), test_names_masked(), test_national_id_masked(), test_non_pii_untouched() (+3 more)

### Community 29 - "Voice Tests"
Cohesion: 0.15
Nodes (8): _broken_whisper(), _channel(), test_a_phone_number_spoken_as_words_is_masked(), test_a_strength_or_a_small_count_is_not_mistaken_for_a_phone_number(), test_health_reports_a_model_that_cannot_load(), test_missing_model_is_loud_and_never_downloads_at_runtime(), test_real_clip(), test_unusable_voice_note_gets_the_cannot_read_reply()

### Community 30 - "Twilio WhatsApp Webhook"
Cohesion: 0.19
Nodes (6): _can_send_later(), _media_auth(), _send_later(), twiml(), whatsapp_webhook(), work()

### Community 31 - "Schema Tests"
Cohesion: 0.16
Nodes (8): apply_schema(), conn(), test_apply_schema_is_idempotent(), test_metadata_rejects_free_text(), test_metadata_rejects_out_of_vocabulary_values(), test_transcripts_is_unlogged_and_schema_reapply_keeps_it(), test_transcripts_role_is_checked(), test_normalize_unifies_arabic_variants()

### Community 32 - "Procedure Ingestion"
Cohesion: 0.18
Nodes (8): chunk_text(), clean_text(), fetch_page(), ingest_text(), ingest_url(), main(), page_title(), _word_count()

### Community 33 - "Plan & Data Sources"
Cohesion: 0.16
Nodes (15): MoPH Drugs Public Price List + National Drugs Database; show list_date, Places gazetteer with Arabizi aliases (rapidfuzz, pg_trgm), P2 problems (per-laptop DB, local Ollama, no public deploy), Deployment notes (MacBook demo, AWS VM fallback, reset_demo), Dependency map (hard S0 vs soft deps), PLAN.md (sprint plan), MVP priority order (one procedure on web first), Sprint 0 shared moment: contracts.py + schema.sql (+7 more)

### Community 34 - "DB Access & Demo"
Cohesion: 0.21
Nodes (5): get_conn(), _pick(), reset(), sample_rows(), test_sample_rows_are_deterministic_and_closed_vocabulary()

### Community 35 - "Privacy & Retention Design"
Cohesion: 0.20
Nodes (11): Dashboard deterministic topics vs AI classifier vocabulary mismatch, No application-level rate limiter, P1 important limitations, Retention job via APScheduler every 15 min, Topic classification with fixed enum (LLM classify, SetFit, mDeBERTa zero-shot), classify(transcript) function, Metadata model (only thing that survives a conversation), Masking limits: bare names, addresses, spelled-out numbers not masked (+3 more)

### Community 36 - "LLM Backend Decision"
Cohesion: 0.24
Nodes (11): QIMMA Arabic LLM leaderboard (TII), Qwen3/Qwen3.5 as default self-hosted pick (Apache-2.0, tool calling), LLMClient protocol, Anthropic backend (not used), LLM.md (LLM backends), Groq llama-3.3-70b-versatile reliability fallback, Hosted backend (bridge, dev only), Larger models post-demo evaluation (q8_0, Fanar-2-27B, Jais-30B) (+3 more)

### Community 37 - "Language Detect & Transcribe CLI"
Cohesion: 0.15
Nodes (3): detect_lang(), _main(), _matches()

### Community 38 - "Ingest Tests"
Cohesion: 0.19
Nodes (5): _sentences(), test_arabic_and_other_boundaries_split(), test_chunks_end_on_sentence_boundaries(), test_chunks_respect_size_bounds(), test_ingest_text_inserts_and_is_idempotent()

### Community 39 - "Demo Metrics Generator"
Cohesion: 0.21
Nodes (5): demo_rows(), _pick(), today_beirut(), test_demo_rows_carry_kinds_from_the_closed_vocabulary(), test_demo_rows_use_only_the_metadata_columns_and_closed_topics()

### Community 40 - "Test Fixtures"
Cohesion: 0.19
Nodes (4): db_ready(), _hermetic_llm(), _hermetic_transcriber(), SilentTranscriber

### Community 41 - "Transcribe Tests"
Cohesion: 0.21
Nodes (6): FakeModel, test_empty_audio_skips_model(), test_joins_segments_and_maps_lang(), test_real_arabic_clip(), test_supported_langs(), test_unsupported_detection_retries_as_arabic()

### Community 44 - "Retrieval Search Tests"
Cohesion: 0.27
Nodes (7): _fake_embed(), _rows(), test_k_limits_results(), test_lang_does_not_filter(), test_nearest_doc_first_with_source_and_score(), test_weak_matches_are_dropped(), _vec()

### Community 45 - "Medicine Seed Enrichment"
Cohesion: 0.20
Nodes (7): add_list_dates(), key(), dedupe_drugs(), osm_facilities(), xlsx_drugs(), normalize(), test_normalize()

### Community 46 - "Eval Tests"
Cohesion: 0.27
Nodes (7): ans(), test_all_checks_pass(), test_arabic_normalization_in_include(), test_each_check_reports_failure(), test_no_checks_always_passes(), test_run_counts_and_survives_crash(), handler()

### Community 47 - "Retention Job"
Cohesion: 0.33
Nodes (4): _interval(), main(), run_once(), status()

### Community 48 - "Embeddings & Retrieval"
Cohesion: 0.20
Nodes (4): embed_texts(), normalize_for_embedding(), count_procedures(), ping()

### Community 49 - "WhatsApp Inquiry Builder"
Cohesion: 0.20
Nodes (5): build_inquiry(), _coords(), _first_media(), _safe_lang(), _turn()

### Community 50 - "Grounding & Determinism"
Cohesion: 0.28
Nodes (5): Deterministic directory and medicine responses, Fixed during audit, HHEM-2.1-Open is English-only (unsuitable for Arabic grounding), mDeBERTa-v3 multilingual NLI grounding checker, No-model fallback: render retrieved facts directly

### Community 51 - "Code Audit Risks"
Cohesion: 0.29
Nodes (7): CODE_AUDIT.md (risk register 11 Oct 2026), Facility data needs human spot-check (OSM lacks ownership/hours), Narrow knowledge coverage (two procedure sources), P0 demo blockers, Verification evidence (313 passed, 8/8 eval), 40-60 question labelled evaluation set, Phase 1 quality upgrade (bigger model, semantic retrieval, eval set)

### Community 52 - "Demo Deployment Setup"
Cohesion: 0.25
Nodes (8): infra/SETUP.md (running Daleel for a demo), AWS server fallback (vm_setup.sh, qwen3:4b, Caddy), AWS front door with SSH tunnel to laptop (stable Twilio webhook URL), Demo laptop deployment (Docker, Ollama, run_demo.sh), Demo .env settings (retention, signatures, Twilio), Self-hosted Ollama model (DALEEL_MODEL), Showing the privacy flow (transcripts deleted after idle window), Twilio signature verification policy (REQUIRE_TWILIO_SIGNATURE)

### Community 53 - "Lexical Ingestion"
Cohesion: 0.32
Nodes (3): detect_lang(), ingest_lexical(), main()

### Community 54 - "Contract Protocols"
Cohesion: 0.29
Nodes (3): MedicineLookup, ProcedureSearch, Transcriber

### Community 56 - "Twilio Signature Check"
Cohesion: 0.33
Nodes (3): parse_form(), signature_ok(), webhook_url()

### Community 59 - "Metrics Tests"
Cohesion: 0.33
Nodes (6): _row(), test_days_fill_gaps_and_report_the_real_period(), test_demo_flag_from_environment(), test_headline_numbers_and_outcome_table_share_one_source(), test_one_day_of_data_has_a_period_and_one_point(), test_targets_are_absent_unless_configured()

### Community 60 - "Whisper Vocabulary Tests"
Cohesion: 0.33
Nodes (3): _raises(), test_whisper_is_given_the_vocabulary_hints(), transcribe()

### Community 63 - "Demo Mode Failure Tests"
Cohesion: 0.50
Nodes (3): test_demo_mode_serves_synthetic_rows_and_never_touches_the_database(), test_voice_note_download_failure_is_graceful(), boom()

## Knowledge Gaps
- **33 isolated node(s):** `reset_demo.sh script`, `run_demo.sh script`, `PYTHONPATH`, `tunnel_to_aws.sh script`, `Settings` (+28 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 388 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_conn()` connect `DB Access & Demo` to `Procedure Ingestion`, `Transcript Storage`, `Directory Search`, `Seed Loaders`, `Dashboard Metrics`, `Retention Job`, `Embeddings & Retrieval`, `Medicine Lookup`, `Lexical Ingestion`, `Lexical Search & AI Deps`, `Schema Tests`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `Inquiry` (e.g. with `_pipeline_handler()` and `chat()`) actually correct?**
  _`Inquiry` has 24 INFERRED edges - model-reasoned connections that need verification._
- **What connects `reset_demo.sh script`, `run_demo.sh script`, `PYTHONPATH` to the rest of the system?**
  _33 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `FastAPI App & Model Load` be split into smaller, more focused modules?**
  _Cohesion score 0.06033182503770739 - nodes in this community are weakly interconnected._
- **Why does `TranscriberImpl` connect `Whisper Transcriber` to `FastAPI App & Model Load`, `Project Overview (CLAUDE.md)`, `Language Detect & Transcribe CLI`, `Transcribe Tests`, `Lexical Search & AI Deps`, `Whisper Vocabulary Tests`, `Voice Tests`, `Twilio WhatsApp Webhook`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `Answer` (e.g. with `_pipeline_handler()` and `run()`) actually correct?**
  _`Answer` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Should `Ollama Local LLM` be split into smaller, more focused modules?**
  _Cohesion score 0.05725490196078432 - nodes in this community are weakly interconnected._