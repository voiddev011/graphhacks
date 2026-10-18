import json
from pathlib import Path
import pytest
from app.transcripts import import_chunk,answer_from_memory,memory_fingerprint
from app.domain import Rejected
from benchmarks.locomo import raw_sessions,select_questions,aggregate
from benchmarks.locomo_metrics import locomo_f1,token_f1


def example():
    return {"sample_id":"test", "conversation":{"speaker_a":"Alice","speaker_b":"Bob",
        "session_2_date_time":"2 May 2023", "session_2":[{"speaker":"Bob","dia_id":"D2:1","text":"I own a bakery."}],
        "session_1_date_time":"1 May 2023", "session_1":[{"speaker":"Alice","dia_id":"D1:1","text":"I work in Paris.","blip_caption":"FORBIDDEN_CAPTION"}]},
        "qa":[{"category":c,"question":"Question "+str(c),"answer":"FORBIDDEN_GOLD","evidence":["FORBIDDEN_HINT"]} for c in [1,2,3,4]],
        "session_summary":"FORBIDDEN_SUMMARY","observation":"FORBIDDEN_OBSERVATION"}


def test_raw_import_is_chronological_and_strips_annotations():
    chunks=raw_sessions(example())
    assert [c["session"] for c in chunks]==["session_1","session_2"]
    assert "FORBIDDEN" not in json.dumps(chunks)
    assert chunks[0]["metadata"]["turns"][0]["speaker"]=="Alice"
    assert len(select_questions(example(),1))==4

class ImportModel:
    def generate(self,role,context):
        assert role=="ingest" and "FORBIDDEN" not in json.dumps(context)
        return {"reply":"Imported transcript","memories":[
            {"subject":"Alice","relation":"works_in","value":"Paris","kind":"semantic","passage":"I work in Paris.","dialogue_id":"D1:1"},
            {"subject":"Bob","relation":"owns","value":"Paris","kind":"semantic","passage":"I work in Paris.","dialogue_id":"WRONG_ID"}],
            "citations":[],"suggested_task":""}


def test_transcript_import_uses_grounded_graph_and_preserves_speaker_date(service):
    chunk=raw_sessions(example())[0]
    receipt,detail=import_chunk(service,"transcript_1",chunk["text"],chunk["metadata"],ImportModel())
    assert len(receipt["saved"])==1 and detail["kept"]==1 and len(detail["rejected"])==1
    state=service.store.read();fact=state["memory_versions"][receipt["saved"][0]]
    assert fact["subject"]=="alice" and fact["source"]["speaker"]=="Alice"
    assert fact["source"]["session_date"]=="1 May 2023"
    assert fact["source"]["provenance"]=="external_transcript"
    _,memories=service.store.conversation_context("Where does Alice work?")
    assert memories[0]["value"]=="Paris"
    replay,detail=import_chunk(service,"transcript_1",chunk["text"],chunk["metadata"],ImportModel())
    assert replay==receipt and detail["replayed"]


def test_qa_uses_actual_retrieval_without_gold_history_or_memory_writes(service):
    chunk=raw_sessions(example())[0]
    import_chunk(service,"import_for_qa",chunk["text"],chunk["metadata"],ImportModel())
    before=memory_fingerprint(service.store.read())
    class Reader:
        def generate(self,role,context):
            assert context["recent_conversation"]==[] and "FORBIDDEN" not in json.dumps(context)
            assert context["graph_memory"][0]["value"]=="Paris"
            return {"reply":"Paris","memories":[],"citations":[context["graph_memory"][0]["id"]],"suggested_task":""}
    answer=answer_from_memory(service,"qa_1","Where does Alice work?",Reader(),"2 May 2023")
    assert answer["answer"]=="Paris" and answer["memory_unchanged"]
    assert memory_fingerprint(service.store.read())==before


def test_official_style_f1_handles_categories_and_partial_matches():
    assert locomo_f1("7 May 2023","7 May 2023",2)==1
    assert locomo_f1("Psychology","Psychology; another answer",3)==1
    assert locomo_f1("Paris, France","Paris, France",1)==1
    assert token_f1("Paris","Paris France")==pytest.approx(2/3)
    assert token_f1("unknown","Paris")==0
    assert locomo_f1("Not mentioned","",5)==1


def test_failed_answers_are_in_denominator_and_judge_failure_is_not_accuracy():
    rows=[{"method":"graph","category":4,"status":"answered","f1":1.,"elapsed_seconds":1,"context_chars":50,"correct":True},
          {"method":"graph","category":4,"status":"error","f1":0.,"elapsed_seconds":1,"context_chars":0,"judge_error":"TimeoutError"}]
    score=aggregate(rows)["graph"]
    assert score["token_f1_percent"]==50 and score["questions"]==2
    assert score["local_judge_accuracy_percent"] is None and score["answer_errors"]==1


def test_provider_diagnostics_redact_keys_and_detect_daily_quota(monkeypatch):
    from benchmarks.locomo import error_details
    monkeypatch.setenv("GOOGLE_API_KEY","private-secret")
    result=error_details(ValueError("private-secret https://example.com/key Rate limit: free-models-per-day"))
    assert "private-secret" not in result["error_detail"] and "example.com" not in result["error_detail"]
    assert result["daily_quota_exhausted"]


def test_frozen_restore_preserves_provenance_and_rejects_forgery(service):
    from benchmarks.locomo_restore import restored_state
    chunk=raw_sessions(example())[0]
    import_chunk(service,"restore_source",chunk["text"],chunk["metadata"],ImportModel())
    state=service.store.read()
    artifact={k:state.get(k,{}) for k in ["messages","memory_slots","memory_versions","chat_turns"]}
    restored=restored_state("isolated",artifact)
    assert memory_fingerprint(restored)==memory_fingerprint(state)
    fact=next(iter(artifact["memory_versions"].values()))
    fact["value"]="UNSUPPORTED INVENTION"
    with pytest.raises(ValueError,match="grounded"):
        restored_state("isolated",artifact)


@pytest.mark.integration
def test_frozen_restore_uses_real_graph_and_refuses_second_restore():
    import os,uuid
    if os.getenv("CONTINUITY_DB_TESTS")!="1":pytest.skip("Requires FalkorDB")
    from app.repository import FalkorStore,MemoryStore
    from app.service import Service
    from benchmarks.locomo_restore import restore_isolated
    original=Service(MemoryStore("test"))
    chunk=raw_sessions(example())[0]
    import_chunk(original,"original_import",chunk["text"],chunk["metadata"],ImportModel())
    state=original.store.read()
    artifact={k:state.get(k,{}) for k in ["messages","memory_slots","memory_versions","chat_turns"]}
    target=FalkorStore("locomo_"+uuid.uuid4().hex,"test")
    try:
        restore_isolated(target,artifact)
        _,facts=target.conversation_context("Where does Alice work?")
        assert facts[0]["value"]=="Paris" and facts[0]["source"]["speaker"]=="Alice"
        assert memory_fingerprint(target.read())==memory_fingerprint(state)
        with pytest.raises(ValueError,match="completely empty"):
            restore_isolated(target,artifact)
    finally:target.graph.delete()
