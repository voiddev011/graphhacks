"""UI actions reuse the business service, stable requests, and guarded envelopes."""
from __future__ import annotations

from .domain import Rejected, canonical, current_inputs, required, digest
from .models import Gemini, ModelRouter
from .repository import FalkorStore
from .service import Service, operation
from .workflow import build


def connect(tenant, project):
    return Service(FalkorStore(tenant, project))


def get_model(preferred_provider=None, model_name=None):
    if not preferred_provider and not model_name:
        return Gemini()
    return ModelRouter(model_name=model_name, preferred_provider=preferred_provider)


def error_message(exc):
    if isinstance(exc, Rejected):
        return str(exc)
    detail = str(exc)
    if "DEADLINE_EXCEEDED" in detail or type(exc).__name__ in {"ReadTimeout", "ConnectTimeout"}:
        return "Model request timed out. Retrying with standby model..."
    if "RESOURCE_EXHAUSTED" in detail or "429" in detail:
        return "Primary model rate limited. Standby model will automatically serve subsequent requests."
    if "API_KEY_INVALID" in detail or "UNAUTHENTICATED" in detail:
        return "Authentication error with primary model. Please verify API keys in .env."
    return "Request did not finish. Check provider availability and retry the same request; no completion was recorded."


def workflow(service, rid, role, text, handoff=None, model=None):
    m = model or Gemini()
    return build(service, m).invoke({
        "request_id": rid, "role": role, "text": text, "handoff": handoff,
        "owner": "helper" if role == "helper" else None})["receipt"]


def resume_helper(service, saved, model=None):
    m = model or Gemini()
    return build(service, m).invoke(saved)["receipt"]


def plan_new_task(service, rid, text, requires=(), prerequisites=(), procedures=(), model=None):
    if not text.strip():
        raise Rejected("Describe the task you want help with.")
    task_id = "work_" + digest(rid)[:20]
    service.begin(rid, "planner", text, focus_task=task_id)
    service.message(text, request_id=rid)
    service.command("task", {"id": task_id, "title": text.strip(), "requires": list(requires),
                             "prerequisites": list(prerequisites), "procedures": list(procedures)}, operation(rid, "user_task"))
    m = model or Gemini()
    return build(service, m).invoke({"request_id": rid, "role": "planner", "text": text,
                                     "focus_task": task_id, "handoff": None, "owner": None})["receipt"]


def mutate(service, rid, kind, data):
    # Resolve and freeze UI data before dispatch. On replay use the saved envelope.
    service.begin(rid, kind, canonical(data))
    old = service.replay(rid)
    if old:
        return old
    p = dict(data)
    if kind == "decision":
        text = f"Set {p['key']} to {p['value']}."
    elif kind == "complete":
        text = p["outcome"]
    elif kind == "review":
        text = f"I confirm {p['action']} for task {p['task']}; decisions={canonical(p['decisions'])}."
    elif kind == "release":
        text = "I confirm release of task " + p["task"]
    elif kind == "procedure":
        text = "I approve this procedure: " + canonical(p["steps"])
    else:
        text = None
    if text is not None:
        p.update(message=service.message(text, request_id=rid), passage=text)
    e = service.accept_envelope(rid, kind, p)
    return service.command(kind, p, e["operation_id"])


def helper_request(service, handoff):
    """Find the original request for a claimed handoff, including interrupted calls."""
    s = service.store.read()
    h = required(s["handoffs"], handoff)
    for rid, request in s["requests"].items():
        inputs = request["input"]
        if inputs["role"] != "helper" or inputs.get("handoff") != handoff:
            continue
        receipt = s["operations"].get("claim:" + operation(rid, "claim"), {}).get("result", {})
        if receipt.get("claim") == h["claim"]:
            return {"request_id": rid, "role": "helper", "text": inputs["text"],
                    "handoff": handoff, "owner": inputs["owner"]}
    raise Rejected("The original Helper request was not found. Explicitly release this task before replanning.")
