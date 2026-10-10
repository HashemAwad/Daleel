"""B6: eval scoring + runner logic (fake handler, no DB/LLM needed)."""
import json
from ai import eval as ev
from shared.contracts import Answer, Source


def ans(text="ok", tool="procedure", outcome="answered", urls=()):
    return Answer(text=text, tool=tool, outcome=outcome, sources=[Source(title="t", url=u) for u in urls])


def test_all_checks_pass():
    item = {"tool": "procedure", "outcome": "answered", "include": ["card", ["بطاقة", "carte"]],
            "exclude": ["guess"], "source": "moph.gov.lb"}
    a = ans("Get the Card, voir la carte", urls=["https://www.moph.gov.lb/x"])
    assert ev.score(item, a) == []


def test_each_check_reports_failure():
    item = {"tool": "directory", "outcome": "emergency", "include": ["1787"],
            "exclude": ["card"], "source": "moph.gov.lb"}
    failed = ev.score(item, ans("your card"))
    assert len(failed) == 5


def test_arabic_normalization_in_include():
    assert ev.score({"include": ["الأدوية"]}, ans("هذه الادويه")) == []


def test_no_checks_always_passes():
    assert ev.score({}, ans()) == []


def test_run_counts_and_survives_crash():
    items = [{"id": "a", "q": "x", "tool": "procedure"}, {"id": "b", "q": "y"}, {"id": "c", "q": "z"}]

    def handler(inq):
        if inq.text == "z":
            raise RuntimeError("boom")
        return ans(tool="directory" if inq.text == "y" else "procedure")

    res = ev.run(items, handler)
    assert [r["passed"] for r in res] == [True, True, False]
    assert "crashed: RuntimeError" in res[2]["failed"][0]
    assert "PASS RATE: 2/3 = 66.7%" in ev.summarize(res)


def test_load_items_skips_comments_and_validates(tmp_path):
    p = tmp_path / "qa.jsonl"
    p.write_text('# comment\n\n' + json.dumps({"id": "1", "q": "hi"}) + "\n", encoding="utf-8")
    assert ev.load_items(p) == [{"id": "1", "q": "hi"}]
    p.write_text('{"id": "1"}\n', encoding="utf-8")
    try:
        ev.load_items(p)
        assert False
    except SystemExit:
        pass


def test_sample_file_is_valid():
    items = ev.load_items(ev.SAMPLE)
    assert len(items) >= 5 and len({i["id"] for i in items}) == len(items)
