"""Explicit LangGraph retrieval -> bounded generation -> guarded commit.

Checkpoint recovery is deferred. Durable business requests/handoffs are always
loaded from FalkorDB when starting a new conversation/process.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .domain import Rejected, required
from .models import Help, Plan
from .service import operation


class State(TypedDict, total=False):
    request_id: str
    role: str
    text: str
    handoff: str
    owner: str
    context: dict
    bundles: dict
    claim: dict
    envelope: dict
    receipt: dict
    focus_task: str


def build(service, model):
    def retrieve(st):
        service.begin(st["request_id"], st["role"], st["text"], st.get("handoff"), st.get("owner"), st.get("focus_task"))
        service.message(st["text"], request_id=st["request_id"])
        replay = service.replay(st["request_id"])
        if replay:
            return {"receipt": replay}
        if st["role"] == "planner":
            context, bundles = service.planning_snapshot()
            if not context["eligible"]:
                raise Rejected("No eligible pending task. Inspect decisions and prerequisites.")
            return {"context": context, "bundles": bundles}
        claim = service.command("claim", {"handoff": st["handoff"], "owner": st["owner"]}, operation(st["request_id"], "claim"))
        return {"claim": claim}

    def generate(st):
        # Revalidate here too: this node must be safe even if a future checkpoint
        # implementation resumes directly here without running retrieve again.
        replay = service.replay(st["request_id"])
        if replay:
            return {"receipt": replay}
        if st["role"] == "planner":
            context, bundles = service.planning_snapshot()
            if not bundles:
                raise Rejected("No task is eligible before generation.")
            if st.get("focus_task"):
                focus = st["focus_task"]
                if focus not in bundles:
                    raise Rejected("This task is waiting for its required decisions or prerequisites.")
                context["eligible"] = [focus]
                context["tasks"] = [t for t in context["tasks"] if t["id"] == focus]
                bundles = {focus: bundles[focus]}
            context["user_request"] = st["text"]
            context["shared_memory"] = service.shared_memory(st["text"])
            proposal = Plan.model_validate(service.generate(st["request_id"], model, "planner", context))
            if proposal.task_id not in bundles:
                raise Rejected("Planner selected an unknown or ineligible task.")
            payload = {"objective": proposal.objective, "bundle": bundles[proposal.task_id]}
            kind = "handoff"
        else:
            context = service.helper_context(st["handoff"], st["claim"])
            context["user_request"] = st["text"]
            context["shared_memory"] = service.shared_memory(st["text"] + " " + context["task"]["title"])
            proposal = Help.model_validate(service.generate(st["request_id"], model, "helper", context))
            payload = {"handoff": st["handoff"], "claim": st["claim"]["claim"],
                       "execution_version": st["claim"]["execution_version"],
                       "draft": proposal.model_dump_json()}
            kind = "draft"
        payload["memory_inputs"] = {m["slot"]: m["id"] for m in context["shared_memory"]}
        return {"envelope": service.accept_envelope(st["request_id"], kind, payload)}

    def commit(st):
        if st.get("receipt"):
            return {}
        e = st["envelope"]
        return {"receipt": service.command(e["kind"], e["payload"], e["operation_id"])}

    g = StateGraph(State)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_node("guarded_commit", commit)
    g.add_edge(START, "retrieve")
    g.add_conditional_edges("retrieve", lambda s: "done" if s.get("receipt") else "generate", {"done": END, "generate": "generate"})
    g.add_edge("generate", "guarded_commit")
    g.add_edge("guarded_commit", END)
    return g.compile()
