"""Isolated tests only: no scripted responses are available in the live application."""
import json
import uuid
import pytest
from app.conversation import chat
from app.domain import Rejected
from app.repository import FalkorStore
from app.service import Service

class ResponseModel:
    def __init__(self, memories=(), reply="I can help.", citations=False, suggested_task=""):
        self.memories=list(memories); self.reply=reply; self.cite=citations; self.seen=[]; self.suggested_task=suggested_task
    def generate(self, role, context):
        self.seen.append(context)
        if role == "chat":
            return {"reply":self.reply,"memories":self.memories,
                "citations":[m["id"] for m in context["graph_memory"]] if self.cite else [],
                "suggested_task":self.suggested_task}
        if role == "planner":
            return {"task_id":context["eligible"][0],"objective":"Prepare the requested work"}
        return {"summary":"Suggested work using the shared facts", "steps":["Use the saved preferences."]}

def fact(relation,value,passage,kind="semantic",subject="user"):
    return dict(subject=subject,relation=relation,value=value,kind=kind,passage=passage)

def send(service,text,memories=(),**kwargs):
    return chat(service,uuid.uuid4().hex,text,model=ResponseModel(memories),**kwargs)

def test_natural_message_persists_facts_history_and_cross_agent_recall(service):
    text="My name is Jack and I own 2 restaurants."
    send(service,text,[fact("name","Jack",text),fact("restaurant_count","2",text)])
    fresh=Service(service.store)
    reader=ResponseModel(reply="Your name is Jack and you own 2 restaurants.",citations=True)
    receipt=chat(fresh,uuid.uuid4().hex,"What do you know about me?",thread="second",agent_role="Helper",model=reader)
    assert {m["value"] for m in reader.seen[0]["graph_memory"]} == {"Jack","2"}
    assert reader.seen[0]["recent_conversation"] == []
    state=service.store.read()
    turn=state["chat_turns"][receipt["turn"]]
    assert len(turn["citations"])==2 and turn["agent_role"]=="Helper"
    assert len(state["chat_turns"])==2 and not state["tasks"]
    if isinstance(service.store,FalkorStore):
        rows=service.store.graph.ro_query("MATCH (:MemorySlot)-[:CURRENT]->(m:MemoryVersion)-[:FROM_MESSAGE]->(source:Message) RETURN m.data,source.data").result_set
        assert len(rows)==2
        assert all(json.loads(source)["speaker"]=="user" for _,source in rows)

def test_correction_replaces_current_value_preserves_provenance_and_replay(service):
    first="I own 2 restaurants."
    send(service,first,[fact("restaurant_count","2",first)])
    correction="Actually I now own 3 restaurants."
    rid=uuid.uuid4().hex; model=ResponseModel([fact("restaurant_count","3",correction)])
    receipt=chat(service,rid,correction,model=model)
    before=service.store.read()
    assert chat(service,rid,correction,model=model)==receipt
    assert len(model.seen)==1 and service.store.read()==before
    current=next(iter(before["memory_slots"].values()))
    updated=before["memory_versions"][current]
    assert updated["value"]=="3"
    assert before["memory_versions"][updated["supersedes"]]["value"]=="2"
    _,retrieved=service.store.conversation_context("How many restaurants?")
    assert [m["value"] for m in retrieved]==["3"]

def test_semantic_episodic_procedural_and_graph_connections(service):
    for text,proposal in [
        ("I own Bistro Blue.",fact("owns","Bistro Blue","I own Bistro Blue.")),
        ("Bistro Blue is in Mumbai.",fact("located_in","Mumbai","Bistro Blue is in Mumbai.",subject="Bistro Blue")),
        ("Yesterday I reviewed the budget.",fact("reviewed","the budget","Yesterday I reviewed the budget.",kind="episodic")),
        ("Always explain in short steps.",fact("explanation_routine","short steps","Always explain in short steps.",kind="procedural")),
    ]: send(service,text,[proposal])
    _,memories=service.store.conversation_context("Where is my restaurant?")
    assert {m["kind"] for m in memories}=={"semantic","episodic","procedural"}
    assert {m["value"] for m in memories}>={"Bistro Blue","Mumbai"}
    if isinstance(service.store,FalkorStore):
        rows=service.store.graph.ro_query("MATCH (:MemorySlot)-[:CURRENT]->(a:MemoryVersion)-[:OBJECT]->(entity:Entity)<-[:SUBJECT]-(b:MemoryVersion)<-[:CURRENT]-(:MemorySlot) RETURN a.data,b.data").result_set
        assert any(json.loads(a)["value"]=="Bistro Blue" and json.loads(b)["value"]=="Mumbai" for a,b in rows)

@pytest.mark.parametrize("text,proposal",[
    ("Could I own 2 restaurants?",fact("restaurant_count","2","I own 2 restaurants")),
    ("My name is Jack.",fact("name","Alice","My name is Jack.")),
    ("I do not own 2 restaurants.",fact("restaurant_count","2","own 2 restaurants")),
])
def test_questions_inventions_and_negation_do_not_become_memories(service,text,proposal):
    receipt=send(service,text,[proposal])
    state=service.store.read()
    assert not state.get("memory_slots") and not receipt["saved"]
    assert state["chat_turns"][receipt["turn"]]["memory_warnings"]

def test_next_work_question_does_not_create_fake_task(service):
    send(service,"What should I work on next?")
    assert not service.store.read()["tasks"]

def test_chat_context_and_history_do_not_cross_project_boundaries(service):
    send(service,"My name is Jack.",[fact("name","Jack","My name is Jack.")])
    if isinstance(service.store,FalkorStore):
        foreign=FalkorStore(service.store.tenant,"private_other_project")
        _,facts=foreign.conversation_context("What is my name?")
        assert facts==[] and not foreign.read().get("chat_turns")


def test_planner_and_helper_consume_same_current_shared_memory(service):
    from app import actions
    text="I own 2 restaurants."
    send(service,text,[fact("restaurant_count","2",text)])
    planner=ResponseModel()
    plan=actions.plan_new_task(service,uuid.uuid4().hex,"Prepare a weekly budget",model=planner)
    assert planner.seen[0]["shared_memory"][0]["value"]=="2"
    text="I now own 3 restaurants."
    send(service,text,[fact("restaurant_count","3",text)])
    helper=ResponseModel()
    draft=actions.workflow(service,uuid.uuid4().hex,"helper","Help with the budget",handoff=plan["handoff"],model=helper)
    assert draft["accepted"] and not draft["completed"]
    assert helper.seen[0]["shared_memory"][0]["value"]=="3"
    attempt=service.store.read()["attempts"][draft["attempt"]]
    assert attempt["memory_inputs"]


def test_existing_evidence_changes_during_chat_are_rejected(service):
    text="My name is Jack."
    send(service,text,[fact("name","Jack",text)])
    class Racing(ResponseModel):
        def generate(self,role,context):
            send(service,"My name is Jane.",[fact("name","Jane","My name is Jane.")])
            return super().generate(role,context)
    with pytest.raises(Rejected,match="no longer current"):
        chat(service,uuid.uuid4().hex,"What is my name?",model=Racing(citations=True))
    assert len(service.store.read()["chat_turns"])==2


@pytest.mark.parametrize("same_slot",[False,True])
def test_concurrent_memories_merge_or_reject_conflicting_updates(service,same_slot):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    barrier=threading.Barrier(2)
    proposals=[("My name is Jack.",fact("name","Jack","My name is Jack.")),
        ("My name is Jane.",fact("name","Jane","My name is Jane.")) if same_slot else
        ("I own 2 restaurants.",fact("restaurant_count","2","I own 2 restaurants."))]
    class Concurrent(ResponseModel):
        def generate(self,role,context):
            result=super().generate(role,context)
            barrier.wait(15)
            return result
    def attempt(pair):
        text,proposal=pair
        try:
            chat(Service(service.store),uuid.uuid4().hex,text,model=Concurrent([proposal]))
            return True
        except Rejected:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        accepted=list(pool.map(attempt,proposals))
    state=service.store.read()
    assert sum(accepted)==(1 if same_slot else 2)
    assert len(state["memory_slots"])==(1 if same_slot else 2)


def test_invalid_extraction_is_skipped_and_accepted_turn_replays(service):
    rid=uuid.uuid4().hex
    bad=ResponseModel([fact("name","Alice","My name is Jack.")])
    receipt=chat(service,rid,"My name is Jack.",model=bad)
    assert not receipt["saved"] and not service.store.read().get("memory_slots")
    assert service.store.read()["chat_turns"][receipt["turn"]]["memory_warnings"]
    assert chat(service,rid,"My name is Jack.",model=bad)==receipt
    assert len(bad.seen)==1 and service.store.read()["requests"][rid]["calls"]==1


def test_bad_memory_does_not_discard_grounded_facts_or_reply(service):
    text="i own a chinese and mexican estaurant"
    proposals=[fact("restaurant_cuisine","chinese",text),fact("restaurant_count","2",text)]
    proposals[0]["cardinality"]="many"
    receipt=send(service,text,proposals)
    state=service.store.read();turn=state["chat_turns"][receipt["turn"]]
    assert len(receipt["saved"])==1 and len(turn["memory_warnings"])==1
    assert state["memory_versions"][receipt["saved"][0]]["value"]=="chinese"
    assert turn["reply"]=="I can help."


def test_assertion_before_question_still_has_valid_source(service):
    text="My name is Jack. Can you help?"
    receipt=send(service,text,[fact("name","Jack","My name is Jack.")])
    assert len(receipt["saved"])==1


def test_explicit_correction_key_handles_different_model_relation_wording(service):
    text="I own 2 restaurants."
    send(service,text,[fact("restaurant_count","2",text)])
    slot=next(iter(service.store.read()["memory_slots"]))
    proposal=fact("number_of_restaurants","3","I now own 3 restaurants.")
    proposal["memory_key"]=slot
    send(service,"I now own 3 restaurants.",[proposal])
    state=service.store.read()
    assert len(state["memory_slots"])==1
    assert state["memory_versions"][state["memory_slots"][slot]]["value"]=="3"


def test_two_named_restaurants_are_separate_graph_relationships(service):
    for name in ["Bistro Blue","Cafe Green"]:
        text="I own "+name+"."
        proposal=fact("owns",name,text)
        proposal["cardinality"]="many"
        send(service,text,[proposal])
    _,facts=service.store.conversation_context("Which restaurants do I own?")
    assert {f["value"] for f in facts}=={"Bistro Blue","Cafe Green"}


def test_chat_history_is_chronological_not_snapshot_dictionary_order(service):
    from app.conversation import ordered_turns
    send(service,"First message.")
    send(service,"Second message.")
    state=service.store.read()
    turns=ordered_turns(state,"main")
    state["chat_turns"]={t["id"]:t for t in reversed(turns)}
    assert [state["messages"][t["message"]]["text"] for t in ordered_turns(state,"main")]==["First message.","Second message."]
    model=ResponseModel()
    chat(service,uuid.uuid4().hex,"Third message.",model=model)
    assert [t["user"] for t in model.seen[0]["recent_conversation"]]==["First message.","Second message."]


def test_cli_chat_and_memory_commands_parse():
    from app.cli import parser
    args=parser().parse_args(["--project","chat_project","chat","Hello","--thread","new","--agent","Helper"])
    assert args.action=="chat" and args.thread=="new" and args.agent=="Helper"
    assert parser().parse_args(["memories"]).action=="memories"
