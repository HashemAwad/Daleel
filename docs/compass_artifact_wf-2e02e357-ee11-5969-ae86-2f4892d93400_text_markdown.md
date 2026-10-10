# Daleel Open-Source Accelerator Map: What to Use This Weekend for a Multilingual MoPH Health Assistant

You can build almost all of Daleel this weekend from permissively licensed parts: FastAPI + Postgres (pgvector + PostGIS + built-in full-text search), bge-m3 embeddings with bge-reranker-v2-m3, Presidio with custom Lebanese recognizers, GlotLID plus a small rule layer for Arabizi, faster-whisper for voice notes, and Langfuse + RAGAS/promptfoo for evaluation. The hard part is not software. It is Lebanese Arabizi and dialect, where no mature open Lebanese transliterator exists. Plan around that with deterministic rules, a hand-built gazetteer and an LLM fallback, and do not count on a single off-the-shelf model.

## TL;DR

- **Core stack (all permissive):** use FastAPI + Postgres with pgvector, PostGIS, pg_trgm and native `tsvector` (skip AGPL ParadeDB). Add BAAI/bge-m3 (MIT) with bge-reranker-v2-m3, Microsoft Presidio (MIT) with custom regex for Lebanese phones and IDs and CAMeL Tools NER (MIT), and GlotLID for language/script ID. Seed the directory from the Healthsites/HOT OpenStreetMap exports on HDX (ODbL, attribution and share-alike on the database) plus the HDX COD-AB caza boundaries.\[1\] Medicine data comes from MoPH's own Drugs Public Price List (updated 19/8/2026) and the National Drugs Database, which has an ATC column.\[2\]\[3\]
- **Models:** for self-hosting, Qwen3/Qwen3.5 (Apache-2.0, native tool calling in vLLM via the `hermes` parser and in Ollama) is the safest pick. Fanar-1-9B-Instruct (Apache-2.0) and Jais-2-8B/70B-Chat (Apache-2.0 but gated, needs a vLLM fork, no documented tool calling) are Arabic-strong alternatives for generation only. SILMA (Gemma terms), Llama 3.x (community license) and Cohere command-r7b-arabic (CC-BY-NC) carry license strings. Evidence for Lebanese dialect and Arabizi is weak for every model: the AladdinBench study (Al Almaoui, Bouillon & Hengchen, MT Summit 2025) found "Models struggle significantly with Arabizi," with Llama 3 and Jais weakest.
- **Avoid:** Piper ≥1.5 (now GPL-3.0), Meta MMS-TTS and Seamless (CC-BY-NC), Coqui XTTS (non-commercial CPML), Botpress v12 (AGPL and sunset), ParadeDB pg_search (AGPL), Arize Phoenix (Elastic License 2.0, not OSI), Farasa (commercial use needs permission), and HHEM-2.1-Open as an *Arabic* grounding checker (English-only). Use SILMA TTS (Apache-2.0 weights, MSA only) if you attempt TTS.\[4\]\[5\]\[6\]\[7\]\[8\]\[9\]\[10\]

## Top picks to use this weekend (shortlist)

| # | Project | License | Daleel component | Weekend effort |
|---|---|---|---|---|
| 1 | pgvector + PostGIS + pg_trgm (in one Postgres container) | PostgreSQL / GPL-2 (PostGIS, server-side use only; no copyleft impact on your app) | Vector store, geo directory, fuzzy names | 1–2 h |
| 2 | BAAI/bge-m3 + BAAI/bge-reranker-v2-m3 (FlagEmbedding) | MIT / Apache-2.0 | Embeddings + rerank | 1 h |
| 3 | Microsoft Presidio + `phonenumbers` + custom PatternRecognizers | MIT / Apache-2.0 | PII redaction | 3–4 h |
| 4 | CAMeL Tools (normalization, NER, dialect ID) | MIT | Arabic normalization, name NER | 2 h (Linux/macOS; dialect ID not on Windows) |
| 5 | GlotLID (fastText) | Open (verify on model card) | Language/script ID incl. `arb_Latn` | 30 min |
| 6 | rapidfuzz | MIT | Place-name and drug-name fuzzy matching | 30 min |
| 7 | Healthsites.io / HOT OSM Lebanon exports (HDX) + COD-AB Lebanon | ODbL / HDX terms | Directory seed data, caza polygons | 2 h |
| 8 | faster-whisper (+ Silero VAD, ffmpeg) | MIT / MIT / LGPL-GPL binary | Voice notes | 2–3 h |
| 9 | assistant-ui (documented RTL) or deep-chat / chatscope | MIT | React RTL widget | 2–3 h |
| 10 | Langfuse (self-host) + RAGAS or promptfoo | MIT core / Apache-2.0 / MIT | Eval + tracing | 2–3 h |
| 11 | twilio-python | MIT | WhatsApp sandbox | 1 h |
| 12 | APScheduler or pg_cron, slowapi | MIT / PostgreSQL / MIT | Retention job, rate limiting | 1 h |

## Key Findings

1. **No production-grade Lebanese Arabizi→Arabic transliterator exists in open source.** The open options target other dialects: Jordanian (Atar, a 25k-pair corpus at 79% accuracy),\[11\] Egyptian (CAMeL Lab's seq2seq tool, the BOLT data, and the stdlib-only `arabizi-toolkit`) and Moroccan (`novagiosAI/arabizi`).\[12\]\[13\]\[14\] For Lebanon there is SenZi (a Lebanese Arabizi sentiment lexicon) and AladdinBench, whose Hugging Face card describes "real-world Arabizi messages collected from native speakers across Lebanon, Egypt, and Algeria" (31 participants, per the paper), including 268 Lebanese segments. AladdinBench is the best ready-made evaluation set for Daleel's Arabizi path.
2. **Multilingual embedders beat Arabic-specific ones for Arabic RAG.** A systematic Arabic RAG study by Alsubhi et al. (Naseej Innovation Lab and the University of Jeddah, arXiv 2506.06339, June 2025) tested "six diverse Arabic datasets, evaluating four chunking strategies, six embedding models, one reranking model, and two large language models," and found "BGE-M3 and Multilingual-E5-large emerge as the most effective embedding models." It reported a mean RAGAS score of 70.99 for bge-m3, rising to 74.15 with bge-reranker-v2-m3.\[15\] The tests were on MSA only, so dialect and Arabizi retrieval are unproven.\[16\]
3. **The Arabic LLM landscape is crowded, but licenses and tool calling decide the choice.** On TII's QIMMA leaderboard (April 2026), Qwen3.5-397B leads with a 68.06 average, then Karnak at 66.20 and Jais-2-70B-Chat at 65.81.\[17\] Only the Qwen family pairs Apache-2.0, first-class tool calling in vLLM and Ollama, and small sizes that fit a hackathon GPU.\[18\]\[19\]\[20\]
4. **Several popular speech and TTS components have quietly become license traps.** Piper moved to GPL-3.0 (piper-tts 1.8.0 on PyPI is GPL-3.0-or-later; GitHub shows the MIT rhasspy/piper repo "was archived by the owner on Oct 6, 2025," with development moved to OHF-Voice/piper1-gpl). MMS-TTS Arabic is CC-BY-NC 4.0, and Phoenix is under ELv2.\[21\]\[22\]
5. **MoPH already publishes most of what the medicines and directory tools need.** That includes the Drugs Public Price List 2026 (several XLSX/PDF updates, latest 19/8/2026, prices "based on the exchange rate No. 2026/2/25489 issued on 11/8/2026"), the Lebanon National Drugs Database (HTML with ATC, name, B/G, ingredients, dosage, form and price columns), and a Health Facility Locator.\[2\]\[3\]\[23\] Scraping these beats any third-party drug database.

## Details by Daleel Component

### 1. Language identification (Arabic vs Arabizi vs French vs English, code-switching)

| Project | Link | License | Status | Weekend fit | Notes |
|---|---|---|---|---|---|
| **GlotLID v3** | github.com/cisnlp/GlotLID; HF `cis-lmu/glotlid` | Open (check model card before shipping) | Active; v3 has 2102 labels | ★★★★★ – one `fasttext.load_model` | Script-aware labels (`arb_Arab` vs `arb_Latn`) give you an "Arabic in Latin script" signal. Restrict labels to {arb_Arab, apc/ajp_Arab if present, arb_Latn, fra_Latn, eng_Latn} with its documented `CustomLID` limiter.\[24\]\[25\]\[26\] |
| fastText lid.176 | fasttext.cc | CC-BY-SA 3.0 (share-alike on the model) | Stable, unmaintained | ★★★★ | Fast, but no Arabizi class: Arabizi tends to come out as English/French or noise. |
| lingua-py | github.com/pemistahl/lingua-py | Apache-2.0 | Active | ★★★★ | Good on short texts (EN/FR/AR); no Arabizi. |
| CAMeL Tools dialect ID | github.com/CAMeL-Lab/camel_tools | MIT | Last update Oct 2025 | ★★★ | 25-city + MSA model (MADAR) includes Beirut (`BEI`). Arabic script only; not available on Windows.\[27\]\[28\]\[29\] |
| NADI shared-task models | aclanthology NADI 2020–2024 | Varies | Research | ★★ | Country-level F1 is low (NADI 2020 best 26.78; NADI 2022 winning Subtask-1 F1 27.06), so don't rely on it for routing.\[30\]\[31\] |

**Recommendation:** run a 3-stage detector. (1) Use the script ratio: Arabic code points vs Latin. (2) For Latin text, apply an **Arabizi heuristic**: digits 2/3/5/7/8/9 inside alphabetic tokens (`3ale`, `2arib`, `7ake`), plus a 200–400-word Lebanese Arabizi lexicon (`bade`, `badde`, `shu`, `kif`, `mn`, `3am`, `hayda`, `saydaliyye`, `mosta2fa`). (3) Use GlotLID only to split French from English. Detect code-switching per token, and reply in the *majority script of the user's message*. The digit-in-word heuristic is the single most reliable Arabizi signal; borrow the approach from `arabizi-toolkit`'s `detect` and novagiosAI's word-level code-switching detector, both of which are dependency-free.\[13\]\[14\]

### 2. Arabizi→Arabic transliteration, Arabic normalization, cross-script place matching

| Project | Link | License | Status | Fit | Daleel use |
|---|---|---|---|---|---|
| CAMeL Tools `utils.normalize` / dediac | camel_tools | MIT | Active | ★★★★★ | Alef/ya/ta-marbuta unification, diacritic and tatweel removal before embedding and FTS. |
| CAMeL-Lab/codafication (`arat5-coda-did`) | github.com/CAMeL-Lab/codafication | MIT | Jul 2024 | ★★★ | Dialectal→CODA spelling normalization with dialect-ID conditioning; it has a Beirut phrase in its dialect map.\[32\] GPU recommended. |
| CAMeL-Lab seq2seq-transliteration-tool | github.com/CAMeL-Lab/seq2seq-transliteration-tool | Check repo | Research (2020) | ★★ | Unified Arabizi detection + transliteration,\[33\] trained on Egyptian. |
| Atar (bashartalafha/Arabizi-Transliteration) | github | No explicit license seen; treat as all-rights-reserved | Stale | ★★ | Jordanian corpus (25k pairs, 79% accuracy);\[11\] closest dialect to Lebanese. Use only as reference or eval. |
| arabizi-toolkit (Kazenubis) | github | Check repo | New, small | ★★★ | Egyptian rules, stdlib-only.\[13\] Fork the mapping table (3→ع, 7→ح, 2→ء/ق, 5→خ, 9→ص) and add Lebanese words. |
| novagiosAI/arabizi | github | Check repo | New | ★★★ | Moroccan, but its lookup-table-first design is exactly what you should copy.\[14\] |
| AladdinBench | HF `palmaoui/AladdinBench` | Check card | 2025 | ★★★★ (eval) | 268 Lebanese WhatsApp Arabizi segments (North/South).\[34\] Use them for your test set. |

**Place names (Aley / عاليه / 3ale / Aaley):** build a `places` table with columns `name_ar`, `name_en`, `name_fr` and `aliases[]`. Seed it from OSM `name:ar`/`name:en` tags and the COD-AB gazetteer. Hand-add Arabizi variants for the roughly 26 cazas and the top ~100 towns. Match with `rapidfuzz.process.extractOne` over a normalized key: lowercase, strip vowels, map digits to letters. Use `pg_trgm` as the SQL fallback. Sources disagree on the caza count: Localiban lists 25 districts in 8 governorates, while the Lebanese Arabic Institute lists 26 districts and notes a ninth governorate.\[35\]\[36\] Load the COD-AB file as ground truth and note the discrepancy in your docs.

### 3. Arabic NLP toolkits and NER (for name redaction)

| Project | License | Status | Fit | Notes |
|---|---|---|---|---|
| **CAMeL Tools** (NER via CAMeLBERT, morphology, sentiment, DID) | MIT | Active (updated Oct 26, 2025) | ★★★★ | NER is trained on ANERcorp with 4 classes (PERS/LOC/ORG/MISC), MSA-leaning.\[27\]\[37\] Install the "light" data package to save time. |
| Stanza (Arabic) | Apache-2.0 | Active | ★★★ | Presidio has a `StanzaRecognizer`, so it plugs in natively. |
| hatmimoha/arabic-ner; boda/ANER (50 entity types) | Check model cards | Older | ★★★ | Compared in "Comparing Open Arabic NER Tools" (arXiv 2205.05857).\[38\]\[39\] |
| ANER (Arabic **and Arabizi** NER) | arXiv 2308.14669 | Research | ★★ | Claims Arabizi support;\[37\] weights availability unverified. |
| spaCy | MIT | Active | ★★ | No official trained Arabic pipeline; use only as the Presidio wrapper for EN/FR (`en_core_web_sm`, `fr_core_news_sm`). |
| Farasa | **Research-free; commercial use requires permission** | Maintained by QCRI | ★ | ⚠ Restrictive. Avoid for a ministry deliverable. |

### 4. PII detection and redaction (before any hosted LLM call)

- **Microsoft Presidio** (github.com/microsoft/presidio, MIT, active). It has predefined and custom recognizers using NER, regex, rule logic and checksums.\[40\] It ships no Lebanese recognizers, so you write `PatternRecognizer`s:
  - **Lebanese phones:** `(?:\+|00)?961[\s-]?(?:3|70|71|76|78|79|81)[\s-]?\d{3}[\s-]?\d{3}` for mobiles, plus landlines `0?[1-9][\s-]?\d{6}`. Validate with `phonenumbers` (Python port of libphonenumber, Apache-2.0) using `region="LB"`. Normalize Eastern Arabic digits (٠-٩) to ASCII first, or the regex misses Arabic-script numbers.
  - **Lebanese ID / registry numbers:** there is no public checksum spec. Use a context-boosted regex for 8–12 digit runs near `هوية`, `ID`, `carte`, `sijill`/`سجل`, `ra2m`. Over-redact; it's safer.
  - **Names:** chain CAMeL NER (Arabic script), spaCy/Stanza EN/FR (Latin), and a **first-name deny-list** (top Lebanese given names in Arabic and Latin/Arabizi spellings) for Arabizi, where no NER works reliably.
  - **Reference implementation:** `novagiosAI/presidio-mena` shows exactly how to package MENA recognizers with multilingual context words (e.g., `حساب`, `compte`) for Presidio 2.2+. Copy its structure and swap Moroccan formats for Lebanese ones. Note its caveat: Presidio's context enhancer only matches single-token lemmas.\[41\]
- Replace entities with typed placeholders (`<PHONE_1>`, `<PERSON_1>`) and keep the mapping in request memory only. That way tool calls such as directory lookups still work without names leaving your server.

### 5. Speech (WhatsApp voice notes, stretch goal)

| Project | License | Status | Fit | Notes |
|---|---|---|---|---|
| **faster-whisper** (CTranslate2) | MIT | Active | ★★★★★ | Built-in Silero VAD filter; its README says it is "up to 4 times faster than openai/whisper for the same accuracy while using less memory" (large-v2 GPU benchmark: 4m30s vs 54s). Use `large-v3-turbo` on GPU, `small`/`medium` int8 on CPU. |
| openai/whisper weights | MIT | Stable | ★★★★ | Base for all fine-tunes. |
| whisper.cpp | MIT | Active | ★★★★ | CPU-only fallback. |
| WhisperX | BSD-2 | Active | ★★★ | Diarization pulls gated pyannote models, which you don't need. |
| oddadmix/whisper-large-v3-turbo-arabic-dialectal | Check card (dataset is private) | 2026 | ★★★★ | Multi-dialect including Lebanese/Syrian; WER 0.344, CER 0.115.\[42\] Best documented dialect fine-tune found. |
| HebArabNlpProject/WhisperLevantine | Check card | 2024–25 | ★★★ | large-v3, ~1,200 h, mostly Israeli Levantine, WER 33%; already converted for faster-whisper.\[43\] |
| hassanayoub85/lebanese-asr-demo (HF Space) | Unstated | 2025–26 | ★★ | A Lebanese whisper-small fine-tune shown against the base model.\[44\] Inspect it, but treat it as unverified. |
| MohamedRashad/Arabic-Whisper-CodeSwitching-Edition | Check card | 2024 | ★★★ | Arabic with embedded English;\[45\] Egyptian-leaning. |
| Silero VAD | MIT | Active | ★★★★★ | Trims silence before ASR. |
| ffmpeg (+ `pydub` MIT or `ffmpeg-python`) | LGPL/GPL binary | Active | ★★★★★ | `ffmpeg -i in.ogg -ar 16000 -ac 1 out.wav` decodes WhatsApp OGG/Opus. Call the binary as a subprocess so no linking issues arise. |
| NVIDIA NeMo (Arabic FastConformer) | Apache-2.0 toolkit; check model card | Active | ★★ | Heavy install; MSA-focused. Skip this weekend. |
| Meta MMS ASR / SeamlessM4T | **CC-BY-NC** | — | ✗ | Non-commercial. |

**TTS:** **SILMA TTS v1** (`silma-ai/silma-tts`) is 150M parameters, F5-TTS architecture, with MIT code and Apache-2.0 weights. It is bilingual Arabic (MSA) and English, `pip install silma-tts`.\[4\]\[46\] It is the only clean-license Arabic TTS found, but it speaks MSA, not Lebanese. For French, Piper voices would work, but the engine is GPL-3.0 from v1.5.0. Either pin MIT `piper-tts==1.2.0` (archived) or keep TTS out of scope.\[47\]\[48\] **Recommendation:** text replies only to voice notes for the demo; TTS is a "Phase 3" slide.

### 6. LLMs (Arabic/dialect quality, licenses, serving, tool calling)

| Model | License (verified on card) | Tool calling | Arabic evidence | Verdict |
|---|---|---|---|---|
| **Qwen3 (0.6B–235B) / Qwen3.5 (0.8B–397B)** | Apache-2.0 | vLLM `--enable-auto-tool-choice --tool-call-parser hermes` (Qwen3); Ollama tags `tools` | Qwen3.5-397B #1 on QIMMA (68.06); Qwen3-235B best open model on HELM Arabic (0.786)\[17\]\[18\]\[20\]\[49\]\[50\]\[51\] | ✅ **Default self-hosted pick** (Qwen3-8B or Qwen3.5-9B on one GPU) |
| Fanar-1-9B-Instruct (QCRI) | Apache-2.0\[52\] | Not documented | Arabic/English, 4K context | ✅ Arabic generation; ⚠ short context for RAG\[53\] |
| Jais-2-8B/70B-Chat (Inception) | Apache-2.0, **gated** | None documented; needs Jais-2 vLLM fork | Jais-2-70B #3 on QIMMA (65.81); top on ArabicMMLU/ArabCulture\[17\]\[54\] | ⚠ Strong Arabic, weak integration |
| Falcon-H1-Arabic 3B/7B/34B (TII) | Falcon-LLM License (Apache-based + AUP); repo not directly verified | None documented; vLLM supports architecture | TII claims 7B 71.47% and 34B 75.36% on OALL\[55\]\[56\] | ⚠ Promising, read the AUP |
| ALLaM-7B-Instruct-preview (SDAIA/HUMAIN) | Frontmatter says Apache-2.0, but "see LICENSE file" points to a file that doesn't exist | No | Strong ArabicMMLU | ⚠ License ambiguity\[57\]\[58\] |
| SILMA-9B-Instruct; SILMA-Kashif-2B (RAG) | **Gemma terms** | Via Gemma templates | Was #1 on OALL v1\[52\] | ⚠ Usage policy applies\[58\]\[59\] |
| Llama 3.1/3.3 | **Llama Community License** ("Built with Llama", AUP, 700M MAU clause) | vLLM `llama3_json`; Ollama `tools` | AladdinBench: weakest on Arabizi\[34\]\[60\]\[61\] | ⚠ License strings; weak Arabizi |
| Cohere command-r7b-arabic | **CC-BY-NC 4.0** | Yes | RAG-optimized\[52\] | ✗ Non-commercial |
| AceGPT | Llama-2 derived license | No | Older | ✗ Superseded |

**Dialect/Arabizi evidence is thin everywhere.**
- **AraDiCE** (COLING 2025): MSA, Levantine and Egyptian benchmarks. Finds multilingual models show "a substantial deficiency" on Levantine, and Arabic-centric Jais/AceGPT do better on dialect.\[62\]
- **DialectalArabicMMLU** (arXiv 2510.27543): a 3K-question Syrian/Levantine split.\[63\]
- **AladdinBench** (Al Almaoui, Bouillon & Hengchen, MT Summit 2025): the paper describes "a comparative evaluation of five LLMs" on direct Arabizi translation (secondary summaries list up to seven, including GPT-4o, Claude 3.5 Sonnet, Llama-3.3-70B and Jais-30B). "Models struggle significantly with Arabizi"; Mistral Large and Gemma are moderate, Llama 3 and Jais weakest.
- **Conclusion:** for the demo, use a frontier hosted API with tool calling behind your redaction layer, and show Qwen3-8B on vLLM/Ollama as the sovereign swap. Measure both on *your own* Lebanese and Arabizi test items; don't cite leaderboards as proof of Lebanese quality.

**Serving:** vLLM (Apache-2.0) for an OpenAI-compatible server with tool parsers. Ollama (MIT) for laptops. llama.cpp (MIT) for CPU. TGI (Apache-2.0) is now in maintenance mode, so prefer vLLM. Wrap all of them, plus the hosted API, behind LiteLLM (MIT core) or your own `generate/classify/embed` protocol class.

### 7. RAG frameworks, retrieval and ingestion

**Frameworks:** for a 36-hour build, **skip heavy platforms** and write ~150 lines of retrieval SQL. If you want a framework:

| Project | License | Fit | Note |
|---|---|---|---|
| LlamaIndex | MIT | ★★★★ | Has PGVectorStore with hybrid search. |
| Haystack 2.x | Apache-2.0 | ★★★★ | Clean pipelines; pgvector document store. |
| LangChain / LangGraph | MIT | ★★★ | Heavy abstraction churn. |
| txtai | Apache-2.0 | ★★★ | All-in-one, lightweight. |
| RAGFlow | Apache-2.0 | ★★ | Separate stack (Elasticsearch/Infinity), so it won't sit inside your FastAPI. |
| Kotaemon | Apache-2.0 | ★★ | UI-centric. |
| Dify | **"Dify Open Source License" = Apache-2.0 + extra conditions** (multi-tenant and branding restrictions) | ★★ | ⚠ Not pure OSS. |
| Flowise | Apache-2.0 (enterprise folder separate) | ★★ | Low-code; poor fit for custom safety rails. |

**Retrieval components:**
- **pgvector** (PostgreSQL license): HNSW index on 1024-dim bge-m3 vectors.
- **Postgres native FTS:** `to_tsvector('simple', normalized_text)`. PostgreSQL ships an `arabic` Snowball stemmer config in recent versions (verify with `\dF`). Run CAMeL normalization *before* indexing, and use `simple` for Arabizi/French/English mixed text. Fuse with vector results via Reciprocal Rank Fusion in SQL.
- **ParadeDB pg_search:** BM25, but **AGPL-3.0**.\[64\] Native FTS + RRF is enough for ~hundreds of MoPH pages.
- **bge-reranker-v2-m3** (Apache-2.0): cross-encoder; rerank the top 20 to the top 4. The Arabic RAG study measured a gain from 70.99 to 74.15 RAGAS.\[15\]
- **bge-m3** (MIT): it also emits sparse lexical weights, a second hybrid signal. **multilingual-e5-large** (MIT) is the lighter fallback.\[65\]\[66\]
- **Chunking:** sentence-aware chunking scored best in the Arabic RAG study.\[15\] Split on `. ؟ ! ؛` and Arabic comma `،`, with ~300–500 tokens per chunk, and keep the page URL and title as metadata for citations.

**Ingestion:**

| Project | License | Use |
|---|---|---|
| **Trafilatura** | Apache-2.0 (since v1.8; older versions GPL) | Main-text extraction from moph.gov.lb HTML pages |
| BeautifulSoup / `pandas.read_html` / `openpyxl` | MIT / BSD / MIT | Drug list HTML tables and XLSX |
| **Docling** (IBM) | MIT | PDFs (e.g., LNDI PDF, circulars) with table structure |
| Unstructured (OSS) | Apache-2.0 | Alternative partitioner |
| Tesseract (`ara` traineddata) | Apache-2.0 | OCR for scanned Arabic circulars |
| PaddleOCR | Apache-2.0 | Better Arabic OCR than Tesseract on some scans |
| Marker / Surya | **GPL-3.0 code + restricted model weights** | ⚠ Avoid for a government deliverable |

### 8. Guardrails and safety

| Project | License | Fit | Daleel use |
|---|---|---|---|
| **Your own pre-LLM emergency matcher** | — | ★★★★★ | Multilingual keyword and regex list (Arabic, Arabizi, FR, EN) → deterministic routing to 140 / 1787 / 1214 / 1564. Normalize first. Arabizi examples: `ma3ad fini etnaffas`, `nazif`, `bade e2tol 7ale`, `jalta`. Must run before redaction-dependent steps and never call the LLM. |
| NeMo Guardrails | Apache-2.0 | ★★★ | Colang flows for "no diagnosis/dosing" refusals; adds latency and a learning curve. |
| Guardrails AI | Apache-2.0 | ★★★ | Validators (some hub validators carry their own licenses). |
| LLM Guard (Protect AI) | MIT | ★★★ | Prompt-injection, PII and toxicity scanners. Its injection model is English-centric, so test on Arabic. |
| Llama Guard 3 | **Llama license** | ★★ | Multilingual safety classifier; license strings apply. |
| ShieldGemma | **Gemma terms** | ★★ | English-focused. |
| **HHEM-2.1-Open** (Vectara) | Apache-2.0 | ★★ for Arabic | 110M, CPU-friendly grounding scorer, but **English-only**. Vectara's Arabic-capable HHEM-2.3 is commercial-API-only.\[7\]\[67\]\[68\] |
| MiniCheck | Check per checkpoint (some NC) | ★★ | Fact-checking grounding; English. |
| mDeBERTa-v3-base-xnli (multilingual NLI) | MIT | ★★★★ | **Use this for Arabic/French grounding**: NLI entailment between each answer sentence and the retrieved chunks (100+ languages).\[69\] |

**Grounding recommendation:** take a two-layer approach. (a) Structural: tool-type answers (directory, medicine, hotline) are **rendered from templates** filled with DB rows, so they cannot hallucinate. (b) RAG answers carry required citations. Each answer sentence must reach entailment ≥0.5 against a cited chunk with multilingual NLI, or have high bge-m3 similarity; otherwise return "I don't know" plus the 1214 hotline.

### 9. Conversational frameworks, WhatsApp, human handoff, reference projects

| Project | License | Status | Verdict |
|---|---|---|---|
| **twilio-python** | MIT | Active | ✅ Webhook → FastAPI `POST /whatsapp`; use `RequestValidator` for signature checks; `MediaUrl0` for voice notes. |
| PyWa / heyoo (WhatsApp Cloud API) | Check repos (MIT-style) | Active-ish | ✅ For post-hackathon migration off the Twilio sandbox. |
| Rasa Open Source 3.x | Apache-2.0 (Rasa Pro/CALM proprietary; Rasa now pushes a "Free Developer Edition") | Slowing | ⚠ Overkill; you already have deterministic routing. |
| **Botpress v12** | **AGPL-3.0**, self-hosted v12 **sunset** | Dead | ✗ Avoid.\[5\]\[70\] |
| Typebot | Moved to a source-available license (verify) | Active | ⚠ Avoid. |
| Chatwoot | MIT core (enterprise folder separate) | Active | ✅ Phase 2 human handoff to MoPH agents (has WhatsApp inbox). |
| RapidPro / TextIt (UNICEF) | AGPL-3.0 | Active | ⚠ Great reference for government SMS/WhatsApp flows; AGPL if you fork. |
| Glific (Indian NGO WhatsApp platform) | AGPL-3.0 | Active | ⚠ Reference for multilingual NGO helpdesks. |
| Jugalbandi / OpenNyAI | Check repos | Variable | Reference design: government-scheme RAG over WhatsApp in Indic languages, the closest analogue to Daleel. Study the architecture rather than the code. |

### 10. Web chat widget with RTL

- **assistant-ui** (MIT, active): the only library found with an official **RTL guide**. `npx shadcn@latest add @assistant-ui/direction` adds a Radix `DirectionProvider`. Components use logical Tailwind classes (`ms-*`, `pe-*`, `text-start`). The docs warn that mixed LTR/RTL text "relies on the browser's bidi algorithm."\[71\]
- **deep-chat** (MIT): a single web component, easiest to embed on any MoPH page. RTL is via CSS (`direction`).
- **@chatscope/chat-ui-kit-react** (MIT): classic bubble UI; apply `dir` yourself.
- **Vercel ai-chatbot** (Apache-2.0): Next.js template; heavier than needed.
- **Whatever you choose:** set `dir="auto"` on every message bubble and on the input, plus `unicode-bidi: plaintext`. Force `dir="ltr"` on phone numbers, URLs and drug names. Load Noto Sans Arabic or Cairo.\[72\]\[73\]\[74\] These are the same fixes being requested across other chat UIs (openclaw, chatbox, Claude Code issues), which shows that per-message direction detection breaks on Arabizi/Arabic mixes.\[72\]\[73\]\[75\]

### 11. Geo and directory

| Resource | License | Fit | Use |
|---|---|---|---|
| **HDX "Lebanon Health Facilities (OpenStreetMap Export)"** (HOT) | ODbL | ★★★★★ | Monthly; hospital, clinic, pharmacy, doctors, dentist, `healthcare=*`; includes `name:ar`. GeoJSON/SHP/CSV.\[1\] |
| **HDX "Lebanon Healthsites"** (Global Healthsites Mapping Project) | ODbL | ★★★★ | Quarterly; 258 KB CSV, last modified 10 April 2025.\[76\] |
| healthsites.io API + code | Data ODbL; code BSD-3 | ★★★ | API alternative.\[77\] |
| **HDX COD-AB Lebanon (admin 0–3)** | HDX terms (check dataset page) | ★★★★★ | Caza/governorate polygons + P-codes; last reviewed Nov 2024, flagged "requires improvements"; Beirut admin-4.\[78\] Load with `shp2pgsql` or `ogr2ogr`. |
| Geofabrik Lebanon extract + `osm2pgsql` | ODbL / GPL-2 tool | ★★★ | If you want all POIs. |
| Overpass API | ODbL data | ★★★ | Quick ad-hoc pulls; respect rate limits. |
| Nominatim | GPL-2 software; public instance has a **1 req/s usage policy** | ★★ | Prefer your own gazetteer table; don't geocode user text live. |
| **MoPH Health Facility Locator / PHC list** | MoPH site (official) | ★★★★★ | The authoritative source for *public* hospitals and PHCs. Merge it over OSM and tag `source=MoPH`. |

**ODbL obligation:** credit "© OpenStreetMap contributors." If you publicly distribute a derived database, it must stay ODbL.\[77\]\[79\] That's fine for a ministry, but tell them.

**Query pattern:** `ST_DWithin(geom::geography, :pt, 5000) ORDER BY geom <-> :pt LIMIT 5`. When there is no GPS, resolve the caza via the gazetteer and `ST_Within(facility.geom, caza.geom)`.

### 12. Medicine data

- **Primary:** MoPH Drugs Public Price List 2026 and the Lebanon National Drugs Database. Scrape the paginated HTML (`/en/Drugs/index/...`) with `httpx` + `pandas.read_html` into a `drugs` table (atc, name, brand_generic, ingredients, dosage, form, price_lbp, list_date). Store `list_date` and show it in every answer, because prices change with exchange-rate decisions several times a year.\[2\]\[80\] The 2015 LNDI PDF also documents NSSF coverage and refrigeration flags.\[81\]
- **Generic matching:** group by ATC code + ingredient string to answer "cheaper generic of X". Use `rapidfuzz` (MIT) with `token_set_ratio` on ingredient names, and an Arabizi/Arabic brand alias table (e.g., `panadol`/`بنادول`).
- **Open terminologies:** WHO ATC structure (the codes are already in the MoPH data; the WHO ATC/DDD index has its own terms). RxNorm (NLM, mostly free but needs a UMLS license for some sources, and is US-centric, so of limited value). There are no open Lebanese drug-list scrapers worth reusing; the only GitHub hits are unrelated US price scrapers.\[82\]
- **Chronic-disease free medicines:** these come from MoPH/YMCA chronic-medication program pages. Ingest them as RAG documents, not as a table, unless MoPH gives you the list.

### 13. Topic classification and dashboard (Phase 2)

| Project | License | Fit | Use |
|---|---|---|---|
| Your LLM's `classify()` with a fixed enum | — | ★★★★★ | Cheapest path: classify the *redacted* transcript into ~15 topics, then delete. |
| MoritzLaurer mDeBERTa-v3 multilingual NLI (zero-shot) | MIT | ★★★★ | Self-hosted zero-shot topic labels in AR/FR/EN. |
| SetFit | Apache-2.0 | ★★★★ | Few-shot (8–16 examples per topic) on a multilingual sentence model. |
| BERTopic | MIT | ★★★ | Discover emerging topics in *unanswered* questions (on redacted text). |
| **Apache Superset** | Apache-2.0 | ★★★ | Permissive BI. |
| **Streamlit** | Apache-2.0 | ★★★★★ | Fastest dashboard for a demo, reading the anonymous `events` table. |
| Evidence.dev | MIT | ★★★★ | SQL + Markdown reports. |
| Metabase | **AGPL-3.0** (OSS edition) | ★★★★ | Unmodified internal use is fine; flag it to MoPH legal. |
| Grafana | **AGPL-3.0** | ★★★ | Same caveat. |

### 14. Evaluation and observability

| Project | License | Fit | Note |
|---|---|---|---|
| **promptfoo** | MIT | ★★★★★ | YAML test cases × 4 languages, `contains`/`llm-rubric`/`javascript` asserts, CI pass-rate. Best fit for the "run after every change" requirement. |
| **RAGAS** | Apache-2.0 | ★★★★ | Faithfulness, answer relevancy, context precision. Its LLM-judge prompts are English, so keep the judge model strong. |
| DeepEval | Apache-2.0 | ★★★★ | Pytest-style; nice for FastAPI teams. |
| TruLens | MIT | ★★★ | Feedback functions. |
| **Langfuse** (self-host) | MIT core (`ee/` separate) | ★★★★★ | Tracing, datasets, prompt versions. Self-hosting keeps transcripts in your control. Mask PII *before* sending traces. ClickHouse's acquisition was announced 16 January 2026 alongside its $400M Series D (SiliconANGLE); Langfuse says there are "no planned changes to licensing," and the repo LICENSE now reads "Copyright (c) 2023-2026 ClickHouse, Inc." |
| Arize Phoenix | **Elastic License 2.0** (source-available) | ★★★ | ⚠ Not OSI; fine internally, but avoid if MoPH wants pure OSS.\[83\]\[84\] |
| Comet Opik | Apache-2.0 | ★★★ | Clean-license alternative to Phoenix.\[85\] |

**Arabic eval data:**
- **QIMMA** includes MedArabiQ and MedAraBench (Arabic medical QA). Qwen3.5-397B scored 47.30 on MedArabiQ, Jais-2-70B 52.79.\[17\] That shows how hard Arabic medical QA still is, and supports Daleel's refusal-of-diagnosis design.
- **AraDiCE** (Levantine) and **AladdinBench** (Lebanese Arabizi) are for dialect robustness checks.
- **Build your own 48-item set:** 12 per question type × the language mix (≈15 Arabic MSA/Lebanese, 12 Arabizi, 10 French, 11 English). Include 6 adversarial items: dosing requests, diagnosis requests, prompt injection and emergencies. **Pass criteria:** correct tool/route, correct language/script, cited URL present, no dosing advice, and emergencies always routed.

### 15. Plumbing: scheduling, rate limiting, secrets, containers

- **Retention job:** APScheduler (MIT) in-process `AsyncIOScheduler` every 15 min: classify → write `events(session_hash, topic, lang, escalated, answered, ts)` → `DELETE` transcripts older than N hours. pg_cron (PostgreSQL license) is an alternative for the pure-SQL delete. Celery (BSD) is overkill.
- **Session hashing:** `hmac.new(SECRET_SALT, phone_e164, sha256)`, with the salt rotated monthly. That makes hashes unlinkable across periods.
- **Rate limiting:** slowapi (MIT), keyed by session hash.
- **Secrets:** `pydantic-settings` (MIT) + `.env` for the demo; Docker secrets or SOPS (MPL-2.0) later.
- **Container:** start from the official `postgis/postgis:16-3.4` image and `apt-get install postgresql-16-pgvector` in a 3-line Dockerfile. This is more reliable than hunting for a community image that combines both. Enable `pg_trgm`.

### 16. Arabic/Lebanese health and dialect datasets

- **MedArabiQ, MedAraBench:** Arabic medical QA, used inside QIMMA. Use for a *refusal* eval, not for answers.
- **AraDiCE** (HF `QCRI/AraDiCE`): Levantine variants of standard benchmarks, plus AraDiCE-Culture\[17\]\[62\] (Lebanese among the Levantine set).
- **DialectalArabicMMLU:** Syrian (Levantine) 3K items.\[63\]
- **AladdinBench:** Lebanese WhatsApp Arabizi.
- **SenZi:** Lebanese Arabizi sentiment lexicon,\[12\] useful as an Arabizi vocabulary seed for your detector.
- **NNLP-IL/Arabic-Resources:** a curated index of Arabic corpora with license notes (e.g., BOLT Egyptian Arabizi has custom terms, and NileULex needs permission for commercial use).\[12\]
- **A cultural benchmark with a Lebanese dialogue set** (arXiv 2605.00119) and a dialect health-claims benchmark (Saudi, Egyptian, Lebanese, Moroccan) exist.\[86\]\[87\] Treat both as unverified leads.

## Things to Avoid

| Trap | Why |
|---|---|
| **Piper TTS ≥1.5 / OHF-Voice/piper1-gpl** | GPL-3.0-or-later (piper-tts 1.8.0, published September 4, 2026). The MIT rhasspy/piper is archived. Per-voice licenses vary as well. |
| **Meta MMS-TTS (`facebook/mms-tts-ara`), MMS ASR, SeamlessM4T** | CC-BY-NC 4.0, non-commercial.\[21\]\[88\] |
| **Coqui XTTS-v2** | Coqui Public Model License (non-commercial); the company shut down, so there's no one to sell you a license. |
| **Cohere command-r7b-arabic** | CC-BY-NC 4.0.\[52\] |
| **Botpress v12** | AGPL-3.0 and officially sunset; new Botpress is cloud-only.\[5\]\[89\] |
| **ParadeDB pg_search** | AGPL-3.0; native Postgres FTS suffices.\[90\] |
| **Arize Phoenix** | Elastic License 2.0; not OSI open source.\[9\] |
| **Dify** | Modified Apache with extra conditions. |
| **Marker / Surya OCR** | GPL-3.0 + restricted weights. |
| **Farasa** | Commercial use requires permission. |
| **Llama 3.x, Llama Guard, Gemma/SILMA/ShieldGemma** | Not "open source" licenses: AUPs, attribution and termination clauses.\[52\]\[60\] Usable, but document it. |
| **ALLaM-7B** | License ambiguity (frontmatter Apache-2.0, LICENSE file missing).\[58\] |
| **Jais-2** | Apache-2.0 but gated, needs a forked vLLM,\[54\] no tool calling. Don't make it the tool-calling brain. |
| **HHEM-2.1-Open for Arabic grounding** | English-only.\[7\] |
| **fastText lid.176 for Arabizi** | No Arabizi class, and CC-BY-SA share-alike on the model. |
| **NADI-style dialect ID for routing** | Country-level F1 ~27%; unreliable.\[30\]\[31\] |
| **Atar and other repos with no LICENSE file** | Legally all-rights-reserved; use only as reference or eval. |
| **Public Nominatim for live geocoding** | 1 req/s policy, and poor at Arabizi. |
| **Old TGI** | Maintenance mode; prefer vLLM. |
| **Leaderboard claims of "best Arabic LLM"** | Vendor blogs (e.g., SiliconFlow's guide) and aggregator posts are marketing. OALL v1 was gameable because its test set is public.\[91\]\[92\] Re-test on Lebanese and Arabizi items yourself. |

## Recommendations (weekend build order)

1. **Sat 10:00–13:00:** one Postgres container (PostGIS + pgvector + pg_trgm). Load COD-AB cazas plus the HOT/Healthsites CSVs, and scrape the MoPH drug DB and price XLSX. Build the gazetteer with Arabizi aliases.
2. **Sat 13:00–17:00:** ingest MoPH procedure pages with Trafilatura → CAMeL normalize → sentence chunk → bge-m3 → pgvector plus a `tsvector` column. Add the RRF hybrid query and the bge-reranker-v2-m3 rerank.
3. **Sat 17:00–21:00:** build the pipeline as language/script detector → emergency matcher → Presidio redaction → router (hotline / directory / medicine / RAG) → hosted LLM with tool calls → NLI grounding check → reply in the original script.
4. **Sat night:** Twilio webhook, assistant-ui widget with `dir="auto"`, and APScheduler retention.
5. **Sun 08:00–12:00:** run the 48-item promptfoo suite on every commit and trace in Langfuse. Add a Streamlit dashboard over `events`. Do faster-whisper voice notes only if the core pass rate is ≥85%.
6. **Sun 12:00–14:00:** demo script with one example per language/script, plus an emergency in Arabizi. Add a slide on the license audit and the sovereign Qwen3 swap.

## Caveats

- **Lebanese dialect and Arabizi quality is unproven for every component:** LID, NER, ASR, LLMs and embeddings. All the quantitative evidence above is MSA, Levantine-adjacent (Syrian, Jordanian, Israeli Levantine), or Egyptian/Moroccan Arabizi. Your own test set is the only valid evidence.
- **Some licenses were taken from model cards or secondary sources, not the LICENSE file:** GlotLID, the Whisper dialect fine-tunes, AladdinBench, arabizi-toolkit, novagiosAI, PyWa/heyoo, Typebot, Jugalbandi, MiniCheck and the HDX COD-AB terms. Falcon-H1-Arabic's license was inferred from the sibling Falcon-H1 cards.\[93\]\[94\] One third-party page lists some Qwen3.5 sizes under a "Qwen License", but the Hugging Face repos checked (0.8B, 9B, 35B-A3B) say Apache-2.0.\[18\]\[49\]\[95\]\[96\] Check the 122B and 397B cards if you use them.
- **Leaderboard numbers come from the publishers' own posts:** TII's QIMMA blog, TII's Falcon-H1-Arabic claims and Stanford's HELM Arabic.\[17\]\[51\]\[97\] Some benchmark figures (e.g., Falcon-H1-Arabic OALL scores) came via aggregator articles and are vendor claims.\[56\]
- **The MoPH data is official, but its reuse terms are not stated on the pages reviewed.** Confirm with the MoPH team that scraping and redisplaying prices is acceptable, and always show the list date.

## Sources

1. [Lebanon Health Facilities (OpenStreetMap Export)](https://data.humdata.org/dataset/hotosm_lbn_health_facilities)
2. [Drugs Public Price List 2026](https://moph.gov.lb/en/Pages/3/3101/drugs-public-price-list-)
3. [Lebanon National Drugs Database](https://www.moph.gov.lb/en/Drugs/index/0/10256/page:140/sort:Drug.b_g/direction:asc)
4. [silma-ai/silma-tts · Hugging Face](https://huggingface.co/silma-ai/silma-tts)
5. [Rasa vs Botpress: Enterprise Agent Platform Comparison (2026)](https://rasa.com/blog/rasa-vs-botpress)
6. [ParadeDB: Postgres Full-Text Search & Analytics](https://dev.co/databases/open-source/paradedb)
7. [updated files for hhem-2.1-open · vectara/hallucination\_evaluation\_model at e2b6d9e](https://huggingface.co/vectara/hallucination_evaluation_model/commit/e2b6d9ec13ef307933e82ed6a7ca13ca77fee2d1)
8. [MMS-TTS Arabic Speech Synthesis Model](https://www.promptlayer.com/models/mms-tts-ara/)
9. [Arize Phoenix Alternatives 2026: Top 7 for Agent Observability](https://laminar.sh/article/arize-phoenix-alternatives-2026)
10. [Releases · OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl/releases)
11. [GitHub - bashartalafha/Arabizi-Transliteration · GitHub](https://github.com/bashartalafha/Arabizi-Transliteration)
12. [GitHub - NNLP-IL/Arabic-Resources: A comprehensive list of Arabic NLP resources. · GitHub](https://github.com/NNLP-IL/Arabic-Resources)
13. [GitHub - Kazenubis/arabizi-toolkit: A stdlib-only library and CLI for normalizing Arabic text and transliterating Egyptian Franco-Arabic (Arabizi) into Arabic script. · GitHub](https://github.com/Kazenubis/arabizi-toolkit)
14. [GitHub - novagiosAI/arabizi: Moroccan Arabizi transliteration, Arabic normalization and word-level code-switching detection · GitHub](https://github.com/novagiosAI/arabizi)
15. [BGE-M3 Embedding Model](https://www.emergentmind.com/topics/bge-m3-embedding-model-3ae9be85-46f0-4bec-be49-80d85554d4a6)
16. [BGE-M3: Multilingual Bi-Encoder Model](https://www.emergentmind.com/topics/bge-m3-model)
17. [QIMMA قِمّة ⛰: A Quality-First Arabic LLM Leaderboard](https://huggingface.co/blog/tiiuae/qimma-arabic-leaderboard)
18. [Qwen/Qwen3.5-0.8B · Hugging Face](https://huggingface.co/Qwen/Qwen3.5-0.8B)
19. [Function Calling - Qwen](https://qwen.readthedocs.io/en/latest/framework/function_call.html)
20. [library](https://ollama.com/library)
21. [facebook/mms-tts-ara · Hugging Face](https://huggingface.co/facebook/mms-tts-ara)
22. [License - Phoenix](https://arize.com/docs/phoenix/self-hosting/license)
23. [Pharmaceuticals - moph](https://www.moph.gov.lb/en/Pages/3/3010/pharmaceuticals)
24. [FineWeb2: One Pipeline to Scale Them All — Adapting Pre-Training Data Processing to Every Language](https://arxiv.org/html/2506.20920v1)
25. [GitHub - cisnlp/GlotLID: \[EMNLP 2023\] 💬 Language Identification with Support for More Than 2000 Labels](https://github.com/cisnlp/GlotLID)
26. [cis-lmu/glotlid · Hugging Face](https://huggingface.co/cis-lmu/glotlid)
27. [CAMeL-Lab repositories · GitHub](https://github.com/orgs/CAMeL-Lab/repositories)
28. [camel\_tools/camel\_tools/dialectid/\_\_init\_\_.py at master · CAMeL-Lab/camel\_tools](https://github.com/CAMeL-Lab/camel_tools/blob/master/camel_tools/dialectid/__init__.py)
29. [pypi.org](https://pypi.org/project/camel-tools/1.0.0)
30. [(PDF) NADI 2022: The Third Nuanced Arabic Dialect Identification Shared Task](https://www.researchgate.net/publication/364440865_NADI_2022_The_Third_Nuanced_Arabic_Dialect_Identification_Shared_Task)
31. [NADI 2020: The First Nuanced Arabic Dialect Identification ...](https://aclanthology.org/2020.wanlp-1.9.pdf)
32. [GitHub - CAMeL-Lab/codafication: Code, models, and data for "Exploiting Dialect Identification in Automatic Dialectal Text Normalization". ArabicNLP 2024, ACL. · GitHub](https://github.com/CAMeL-Lab/codafication)
33. [A Unified Model for Arabizi Detection and Transliteration ...](https://aclanthology.org/2020.wanlp-1.15.pdf)
34. <https://aclanthology.org/2025.mtsummit-2.4.pdf>
35. [Territorial administration of Lebanon - Localiban](http://www.localiban.org/territorial-administration-of-lebanon)
36. [Administrative Divisions of Lebanon - Lebanese Arabic Institute](https://www.lebanesearabicinstitute.com/administrative-divisions-lebanon/)
37. [ANER: Arabic and Arabizi Named Entity Recognition using Transformer-Based Approach](https://arxiv.org/pdf/2308.14669)
38. [GitHub - bodasadallah/Arabic-NER: Arabic Named Entity Recognizer model deployed to a website. · GitHub](https://github.com/bodasadallah/Arabic-NER)
39. [Comparing Open Arabic Named Entity Recognition Tools](https://arxiv.org/pdf/2205.05857)
40. [GitHub - data-privacy-stack/presidio: An open-source framework for detecting, redacting, masking, and anonymizing sensitive data (PII) across text, images, and structured data. Supports NLP, pattern matching, and customizable pipelines. · GitHub](https://github.com/microsoft/presidio)
41. [GitHub - novagiosAI/presidio-mena: Microsoft Presidio recognizers for MENA identifiers: Moroccan CIN, RIB, ICE, IBAN and phone numbers, with check-digit validation · GitHub](https://github.com/novagiosAI/presidio-mena)
42. [oddadmix/whisper-large-v3-turbo-arabic-dialectal · Hugging Face](https://huggingface.co/oddadmix/whisper-large-v3-turbo-arabic-dialectal)
43. [HebArabNlpProject/WhisperLevantine · Hugging Face](https://huggingface.co/HebArabNlpProject/WhisperLevantine)
44. [Lebanese ASR - a Hugging Face Space by hassanayoub85](https://huggingface.co/spaces/hassanayoub85/lebanese-asr-demo)
45. [MohamedRashad/Arabic-Whisper-CodeSwitching-Edition · Hugging Face](https://huggingface.co/MohamedRashad/Arabic-Whisper-CodeSwitching-Edition)
46. [SILMA TTS: A Lightweight Open Bilingual Text to Speech Model](https://huggingface.co/blog/silma-ai/opensource-arabic-english-text-to-speech-model)
47. [Arabic to Opus-MT, Piper pinned to MIT: the two licence blockers by techiemaya-admin · Pull Request #55 · techiemaya-admin/lad-translate](https://github.com/techiemaya-admin/lad-translate/pull/55)
48. [Piper TTS Review: Fast Local Neural TTS](https://www.promptquorum.com/power-local-llm/piper-tts-review)
49. [Qwen/Qwen3.5-9B · Hugging Face](https://huggingface.co/Qwen/Qwen3.5-9B)
50. [vLLM - Qwen](https://qwen.readthedocs.io/en/latest/deployment/vllm.html)
51. [HELM Arabic](https://crfm.stanford.edu/2025/12/18/helm-arabic.html)
52. [Arabic LLM Models](https://huggingface.co/blog/silma-ai/arabic-llm-models-list)
53. [QCRI/Fanar-1-9B-Instruct · Hugging Face](https://huggingface.co/QCRI/Fanar-1-9B-Instruct)
54. [inceptionai/Jais-2-8B-Chat · Hugging Face](https://huggingface.co/inceptionai/Jais-2-8B-Chat)
55. [Falcon](https://nextomoro.com/falcon/)
56. [Arabic LLM Leaderboard 2026: Falcon, ALLaM & Fanar](https://annota8.ai/blog/arabic-llm-benchmark-landscape-2026.html)
57. [humain-ai/ALLaM-7B-Instruct-preview · Hugging Face](https://huggingface.co/humain-ai/ALLaM-7B-Instruct-preview)
58. [Arabic LLMs Compared: Jais, ALLaM, Fanar, Falcon - MentronX](https://mentronx.com/learn/the-arabic-language-models)
59. [silma-ai/SILMA-9B-Instruct-v1.0 · Hugging Face](https://huggingface.co/silma-ai/SILMA-9B-Instruct-v1.0)
60. [meta-llama/Llama-3.3-70B-Instruct · Hugging Face](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)
61. [LICENSE · NousResearch/Meta-Llama-3-70B-Instruct at main](https://huggingface.co/NousResearch/Meta-Llama-3-70B-Instruct/blob/main/LICENSE)
62. <https://aclanthology.org/2025.coling-main.283.pdf>
63. <https://arxiv.org/pdf/2510.27543>
64. [pg\_search 0.22.5: Full text search for PostgreSQL using BM25 / PostgreSQL Extension Network](https://pgxn.org/dist/pg_search/0.22.5/)
65. [GitHub - FlagOpen/FlagEmbedding: Retrieval and Retrieval-augmented LLMs · GitHub](https://github.com/flagopen/flagembedding)
66. [Best Embedding Models for Arabic-English RAG (2026)](https://hosn.om/blog/bilingual-rag-embeddings-arabic-english.html)
67. [hallucination\_evaluation\_model](https://www.promptlayer.com/models/hallucinationevaluationmodel/)
68. [Hallucination Detection: Commercial vs Open Source - A Deep Dive](https://www.vectara.com/blog/hallucination-detection-commercial-vs-open-source-a-deep-dive)
69. [Confabulations from ACL Publications (CAP): A Dataset for Scientific Hallucination Detection](https://arxiv.org/pdf/2510.22395)
70. [GitHub - botpress/v12: Botpress OSS](https://github.com/botpress/v12)
71. [RTL Support · assistant-ui](https://www.assistant-ui.com/docs/rtl)
72. [Control UI chat: paragraph-level (auto) RTL direction for mixed Persian/Arabic + English messages · Issue #147732 · openclaw/openclaw](https://github.com/openclaw/openclaw/issues/147732)
73. [feat: Add comprehensive RTL and BiDi support for Persian and Arabic languages (+ Full Persian Translation) by emadpsoft · Pull Request #3865 · chatboxai/chatbox](https://github.com/chatboxai/chatbox/pull/3865)
74. [Right-to-Left (RTL) Support: A Practical CSS and React Implementation Guide](https://better-i18n.com/en/blog/rtl-support-css-react-guide/)
75. [Add RTL (Right-to-Left) Support and Improve Arabic Language Compatibility · Issue #11050 · anthropics/claude-code](https://github.com/anthropics/claude-code/issues/11050)
76. [Lebanon Healthsites](https://data.humdata.org/dataset/lebanon-healthsites)
77. [GitHub - healthsites/healthsites: Building an open data commons of health facility data with OpenStreetMap · GitHub](https://github.com/healthsites/healthsites)
78. [Lebanon - Subnational Administrative Boundaries](https://data.humdata.org/dataset/cod-ab-lbn)
79. [Metadata last updated on Jan 18, 2023](https://datacatalog.worldbank.org/search/dataset/0061355/ukraine-health-facilities)
80. [Drugs Public Price List 2024](https://www.moph.gov.lb/en/Pages/0/77612/drugs-public-price-list-2024)
81. [lebanon national drug index](https://www.moph.gov.lb/userfiles/files/HealthCareSystem/Pharmaceuticals/LNDI/LNDI-2015.pdf)
82. [GitHub - rafmsou/scrape-rx: Scrape prescription drugs offers with puppeteer](https://github.com/rafmsou/scrape-rx)
83. [Arize Phoenix vs Langfuse (2026): Self-Host, OTel, and Event Caps Settled](https://www.morphllm.com/comparisons/arize-phoenix-vs-langfuse)
84. [Langfuse vs Arize (2026): LLM Observability Compared](https://www.kosmoy.com/resources/blog/langfuse-vs-arize/)
85. [Arize Phoenix vs Opik: License, Tracing, and Agent Evals](https://www.agenticwire.news/article/arize-phoenix-vs-opik)
86. [The Need for Robust and Inclusive Benchmarks in Evaluating LLMs on Arabic Text](https://aclanthology.org/2025.icnlsp-1.20.pdf)
87. [Cultural Benchmarking of LLMs in Standard and Dialectal Arabic Dialogues](https://arxiv.org/html/2605.00119v1)
88. [mms-tts](https://www.promptlayer.com/models/mms-tts/)
89. [Langchain integration, own openai api key and max length adjustment Botpress #🤝help](https://discord.botpress.com/t/13161539/hello-is-it-possible-to-add-npm-package-to-botpress-can-we-u)
90. [pg\_search: One Postgres for your application data, full-text search, vector retrieval, and aggregations / PostgreSQL Extension Network](https://pgxn.org/dist/pg_search/)
91. [Ultimate Guide - Best Open Source LLM for Arabic in 2026](https://www.siliconflow.com/articles/en/best-open-source-LLM-for-Arabic)
92. [CamelEval: Advancing Culturally Aligned Arabic Language Models and Benchmarks](https://arxiv.org/pdf/2409.12623)
93. [tiiuae/Falcon-H1-1.5B-Instruct · Hugging Face](https://huggingface.co/tiiuae/Falcon-H1-1.5B-Instruct)
94. [tiiuae/Falcon-H1-34B-Instruct · Hugging Face](https://huggingface.co/tiiuae/Falcon-H1-34B-Instruct)
95. [Qwen/Qwen3.5-35B-A3B · Hugging Face](https://huggingface.co/Qwen/Qwen3.5-35B-A3B)
96. [Model Licenses](https://help.arena.ai/articles/4171906875-model_licenses)
97. [TII Unveils Falcon-H1 Arabic: World’s Top Arabic AI Model](https://www.atrc.gov.ae/news/abu-dhabis-tii-launches-falcon-h1-arabic-establishing-the-worlds-leading-arabic-ai-model)
