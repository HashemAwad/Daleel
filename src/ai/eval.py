"""Eval runner (B6). Owner: B.

    PYTHONPATH=src python src/ai/eval.py [QA_FILE.jsonl] [--json OUT.json] [-v]

Runs every question through the real pipeline (safety -> redact -> route -> ground -> LLM)
and prints a pass rate. No LLM judge: checks are deterministic, so the number is repeatable.
Questions are NOT recorded to the transcripts table (we call the pipeline without `record`).

QA file = JSON Lines, one object per question (the healthcare teammate fills this in):
    {"id": "p01", "q": "كيف آخذ دوا السرطان", "lang": "ar",
     "tool": "procedure",                       # optional: expected tool
     "outcome": "answered",                     # optional: answered | unanswered | emergency | refused
     "include": ["1787", ["بطاقة", "card"]],    # optional: each item must appear; a list = any of
     "exclude": ["guess"],                      # optional: must NOT appear
     "source": "moph.gov.lb"}                   # optional: substring of some cited source URL
Default file: eval/qa.jsonl if present, else src/ai/eval_sample.jsonl (a tiny starter set).

The pass rate is only meaningful with the real model: if the LLM is the stub the runner says
so. Question text is synthetic, but never put real users' messages in the QA file.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable

if __package__ in (None, ""):                       # allow `python src/ai/eval.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.classifier import _norm                     # same Arabic normalization as the classifier
from shared.contracts import Answer, Inquiry

_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = Path(__file__).with_name("eval_sample.jsonl")


# ---------------------------------------------------------------- loading
def load_items(path: Path) -> list[dict]:
    items = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            raise SystemExit(f"{path}:{n}: not valid JSON")
        if "id" not in item or "q" not in item:
            raise SystemExit(f"{path}:{n}: needs 'id' and 'q'")
        items.append(item)
    return items


# ---------------------------------------------------------------- scoring (pure)
def _has(norm_text: str, needle) -> bool:
    options = needle if isinstance(needle, list) else [needle]
    return any(_norm(str(o)) in norm_text for o in options)


def score(item: dict, answer: Answer) -> list[str]:
    """Names of the failed checks (empty list = pass)."""
    failed: list[str] = []
    text = _norm(answer.text)
    if "tool" in item and answer.tool != item["tool"]:
        failed.append(f"tool={answer.tool} (want {item['tool']})")
    if "outcome" in item and answer.outcome != item["outcome"]:
        failed.append(f"outcome={answer.outcome} (want {item['outcome']})")
    for need in item.get("include", []):
        if not _has(text, need):
            failed.append(f"missing {need!r}")
    for bad in item.get("exclude", []):
        if _has(text, bad):
            failed.append(f"contains {bad!r}")
    if "source" in item and not any(item["source"] in (s.url or "") for s in answer.sources):
        failed.append(f"no source containing {item['source']!r}")
    return failed


# ---------------------------------------------------------------- running
def _pipeline_handler() -> Callable[[Inquiry], Answer]:
    from core import pipeline
    return pipeline._handle          # not `handle`: that would store eval questions as transcripts


def run(items: Iterable[dict], handler: Callable[[Inquiry], Answer]) -> list[dict]:
    results = []
    for it in items:
        inq = Inquiry(id=f"eval-{it['id']}", channel="web", text=it["q"],
                      lang=it.get("lang"), user_ref="eval")
        try:
            answer = handler(inq)
            failed = score(it, answer)
            tool = answer.tool
        except Exception as exc:                     # a crash is a failure, not a stop
            failed, tool = [f"crashed: {type(exc).__name__}"], "none"
        results.append({"id": it["id"], "lang": it.get("lang") or "?",
                        "tool": it.get("tool") or tool, "passed": not failed, "failed": failed})
    return results


def _pct(passed: int, total: int) -> str:
    return f"{passed}/{total} = {100 * passed / total:.1f}%" if total else "0/0"


def summarize(results: list[dict]) -> str:
    lines = []
    for key, label in (("tool", "by tool"), ("lang", "by language")):
        groups: dict[str, list[bool]] = defaultdict(list)
        for r in results:
            groups[r[key]].append(r["passed"])
        lines.append(f"  {label}: " + ", ".join(
            f"{k} {_pct(sum(v), len(v))}" for k, v in sorted(groups.items())))
    total, ok = len(results), sum(r["passed"] for r in results)
    lines.append(f"PASS RATE: {_pct(ok, total)}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    verbose = "-v" in argv
    out = None
    if "--json" in argv:
        i = argv.index("--json")
        out = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("-")]
    default = _ROOT / "eval" / "qa.jsonl"
    path = Path(args[0]) if args else (default if default.exists() else SAMPLE)
    items = load_items(path)
    if not items:
        print(f"{path}: no questions")
        return 2

    from core import providers
    llm = type(providers.llm).__name__
    print(f"file={path.name} questions={len(items)} llm={llm} "
          f"procedures={type(providers.procedures).__name__}")
    if llm == "StubLLM":
        print("WARNING: stub LLM in use - answers are placeholders, the pass rate is NOT meaningful.\n"
              "         Start Ollama (see .env.example) and re-run.")
    results = run(items, _pipeline_handler())
    for r in results:
        if verbose or not r["passed"]:
            print(f"{'PASS' if r['passed'] else 'FAIL'} {r['id']}: " + "; ".join(r["failed"]))
    print(summarize(results))
    if out:
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
