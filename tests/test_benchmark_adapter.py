import json
from pathlib import Path

import pytest

from benchmarks import longmemeval as lme
from benchmarks.score import summarize

DATA = Path(__file__).resolve().parent / "data/longmemeval.json"


def test_history_adapter_strips_evaluator_only_metadata():
    entry = json.loads(DATA.read_text())[0]
    entry.update(answer="GOLD_CANARY", question_id="PRIVATE_ID", question_type="PRIVATE_TYPE", answer_session_ids=["PRIVATE_EVIDENCE"])
    entry["haystack_sessions"][0][0]["has_answer"] = "LABEL_CANARY"
    serialized = lme.canonical([lme.asdict(s) for s in lme.history_only(entry)])
    for hidden in ["GOLD_CANARY", "PRIVATE_ID", "PRIVATE_TYPE", "PRIVATE_EVIDENCE", "has_answer", "LABEL_CANARY"]:
        assert hidden not in serialized
    assert "SQLite" in serialized and "FalkorDB" in serialized


def test_context_budget_never_silently_truncates_full_history():
    sessions = lme.history_only(json.loads(DATA.read_text())[0])
    with pytest.raises(ValueError, match="Full history exceeds"):
        lme.fit_context(sessions, 100, full=True)
    assert lme.fit_context(sessions, 100) == []


def test_dry_run_has_no_predictions_or_provider_calls(tmp_path):
    out = tmp_path / "dry"
    report = lme.run(DATA, out, method="bm25", limit=3, dry_run=True)
    assert report["provider_calls"] == 0 and report["errors"] == 0
    assert not (out / "predictions.jsonl").exists()
    with pytest.raises(ValueError, match="completed answer runs"):
        summarize(out, "unused")


def test_reader_budget_and_judge_binding(tmp_path, monkeypatch):
    calls = []
    class StubReader:
        def __init__(self, model):
            pass
        def answer(self, question, date, context):
            calls.append(context)
            assert all("has_answer" not in str(s) for s in context)
            return "Stub prediction", [s["id"] for s in context], {"input_tokens": 1}
    monkeypatch.setattr(lme, "Reader", StubReader)
    out = tmp_path / "answers"
    report = lme.run(DATA, out, method="bm25", model="SCRIPTED_TEST_NOT_LIVE", limit=3, max_calls=1)
    assert len(calls) == 1 and report["errors"] == 2
    predictions = [json.loads(x) for x in (out / "predictions.jsonl").read_text().splitlines()]
    labels = [{**p, "autoeval_label": {"model": "SCRIPTED_JUDGE_NOT_OFFICIAL", "label": True}} for p in predictions]
    judge = tmp_path / "labels.jsonl"
    judge.write_text("\n".join(json.dumps(x) for x in labels))
    score = summarize(out, judge)
    assert score["correct"] == 1 and score["cases"] == 3
    labels[0]["hypothesis"] = "Changed after judging"
    judge.write_text("\n".join(json.dumps(x) for x in labels))
    with pytest.raises(ValueError, match="do not match"):
        summarize(out, judge)


@pytest.mark.integration
def test_graph_history_retrieves_full_sources_and_neighbors(service):
    from app.repository import FalkorStore
    if not isinstance(service.store, FalkorStore):
        pytest.skip("Requires actual FalkorDB graph traversal")
    sessions = lme.history_only(json.loads(DATA.read_text())[0])
    graph = lme.GraphHistory(sessions)
    try:
        found = graph.retrieve("Atlas database", 1)
        assert {s.id for s in found} == {s.id for s in sessions}
        text = " ".join(s.text() for s in found)
        assert "SQLite" in text and "FalkorDB" in text
    finally:
        graph.close()


def test_comparison_rejects_mismatched_fixed_models_or_methods(tmp_path, monkeypatch):
    from benchmarks.compare import compare
    class Stub:
        def __init__(self, model):
            pass
        def answer(self, question, date, context):
            return "Synthetic stub", [], {}
    monkeypatch.setattr(lme, "Reader", Stub)
    folders = []
    for index, (method, model) in enumerate([("none", "STUB_A"), ("bm25", "STUB_A"), ("none", "STUB_B")]):
        folder = tmp_path / str(index)
        lme.run(DATA, folder, method=method, model=model, limit=1, max_calls=1)
        prediction = json.loads((folder / "predictions.jsonl").read_text())
        judge = tmp_path / f"judge{index}.jsonl"
        judge.write_text(json.dumps({**prediction, "autoeval_label": {"model": "FAKE_TEST_JUDGE", "label": True}}))
        summarize(folder, judge)
        folders.append(folder)
    assert len(compare(folders[:2], "memory")["runs"]) == 2
    assert len(compare([folders[0], folders[2]], "reader")["runs"]) == 2
    with pytest.raises(ValueError, match="required fixed"):
        compare([folders[0], folders[2]], "memory")
    with pytest.raises(ValueError, match="required fixed"):
        compare(folders[:2], "reader")
