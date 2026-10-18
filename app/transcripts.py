"""Speaker-aware transcript import and read-only QA over the application's memory.

Import reuses the same MemoryProposal, grounded domain transition, FalkorDB graph
projection and retrieval as chat. Batch filtering is explicit and auditable.
"""
from __future__ import annotations

from .conversation import ChatResponse, TranscriptResponse, slot_key
from .domain import canonical, digest, transition
from .service import operation


def import_chunk(service, request_id, text, metadata, model):
    service.begin(request_id, "transcript", text, owner="Importer", focus_task="import")
    mid = service.message(text, speaker="transcript", request_id=request_id, metadata=metadata)
    old = service.replay(request_id)
    if old:
        return old, {"replayed": True}
    snapshot, memories = service.store.conversation_context(text)
    context = {"current_message":text, "graph_memory":memories,
               "session_date":metadata["session_date"], "speakers":metadata["speakers"]}
    proposal = TranscriptResponse.model_validate(service.generate(request_id, model, "ingest", context))
    kept, rejected = [], []
    op = operation(request_id, "accepted_chat_turn")

    def payload(facts):
        keys = set()
        for f in facts:
            keys.add(f.memory_key or slot_key(" ".join(f.subject.casefold().split()),
                "_".join(f.relation.casefold().split()), f.kind, mid, f.cardinality, f.value))
        expected = {k:snapshot.get("memory_slots", {})[k] for k in keys if k in snapshot.get("memory_slots", {})}
        return {"request":request_id, "thread":"import", "agent_role":"Importer", "message":mid,
            "expected":expected, "response":{"reply":"Imported transcript", "memories":[f.model_dump() for f in facts],
            "citations":[], "suggested_task":""}, "retrieved":[m["id"] for m in memories],
            "provider":getattr(model,"last_served_by",type(model).__name__)}

    # One bad proposal must not discard an entire imported multi-speaker session.
    # Both the filter and final atomic commit use the actual application's rules.
    for fact in proposal.memories:
        try:
            transition(snapshot, "chat_turn", payload(kept + [fact]), op)
            kept.append(fact)
        except ValueError as exc:
            rejected.append({"dialogue_id":fact.dialogue_id, "reason":str(exc)[:250]})
    data = payload(kept)
    envelope = service.accept_envelope(request_id,"chat_turn",data)
    receipt = service.command("chat_turn",data,envelope["operation_id"])
    return receipt, {"proposed":len(proposal.memories),"kept":len(kept),"rejected":rejected}


def memory_fingerprint(state):
    return digest({k:state.get(k,{}) for k in ["memory_slots","memory_versions","chat_turns","messages"]})


def answer_from_memory(service, request_id, question, model, question_date, method="graph"):
    """No STM, memory writes, reference answers or preceding QA answers enter QA."""
    before = memory_fingerprint(service.store.read())
    service.begin(request_id,"qa",question,owner="Helper",focus_task=method)
    memories = service.shared_memory(question) if method == "graph" else []
    context = {"current_message":question, "agent_role":"Helper", "graph_memory":memories,
        "recent_conversation":[], "tasks":[], "decisions":{}, "read_only_qa":True,
        "question_date":question_date}
    answer = ChatResponse.model_validate(service.generate(request_id,model,"chat",context))
    known = {m["id"] for m in memories}
    if not set(answer.citations) <= known:
        raise ValueError("Answer cited an unknown memory")
    if memory_fingerprint(service.store.read()) != before:
        raise ValueError("Question answering modified frozen conversation memory")
    return {"answer":answer.reply, "citations":answer.citations, "context":memories,
            "context_chars":len(canonical(memories)), "memory_unchanged":True}
