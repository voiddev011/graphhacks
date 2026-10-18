"""Service-owned scope, request identity, evidence bundles, and provider budgets."""
from __future__ import annotations

import json
import threading
import uuid

from .domain import Rejected, bundle, digest, ready, required, valid_bundle


def new_id():
    return uuid.uuid4().hex


def operation(request_id, stage):
    return digest([request_id, stage])


class Service:
    def __init__(self, store):
        self.store = store
        # One local process. DB CAS still guards concurrent direct clients.
        self.lock = threading.RLock()

    def command(self, kind, payload, operation_id=None):
        if len(json.dumps(payload, ensure_ascii=False)) > 32000:
            raise Rejected("Command exceeds the prototype's 32,000-character ceiling.")
        return self.store.execute(kind, payload, operation_id or new_id())

    def message(self, text, speaker="user", request_id=None):
        rid = request_id or new_id()
        mid = "msg_" + digest([rid, "source"])[:40]
        self.command("message", {"id": mid, "speaker": speaker, "text": text}, operation(rid, "message"))
        return mid

    def begin(self, request_id, role, text, handoff=None, owner=None, focus_task=None):
        inputs = {"role": role, "text": text, "handoff": handoff, "owner": owner}
        if focus_task is not None:
            inputs["focus_task"] = focus_task
        self.command("request", {"id": request_id, "input": inputs}, operation(request_id, "request"))

    def context(self, snapshot=None):
        s = snapshot if snapshot is not None else self.store.read()
        available = ready(s)
        return {"project": s["id"], "revision": s["revision"], "eligible": available,
                "tasks": [s["tasks"][t] for t in available],
                "decisions": {k: s["versions"][v] for k, v in s["decisions"].items()},
                "procedures": s["procedures"]}

    def generate(self, request_id, model, role, context):
        if len(json.dumps(context)) > 24000:
            raise Rejected("Required context exceeds the prototype ceiling; narrow the project.")
        # Persist budget BEFORE dispatch; a killed process still consumed an attempt.
        def reserve():
            # Every actual dispatch reserves a NEW slot. A receipt for a previous
            # dispatch must never authorize a second provider call on retry.
            with self.lock:
                self.command("attempt_call", {"request": request_id}, operation(request_id, "call_" + new_id()))
        if callable(getattr(model, "generate_with_budget", None)):
            return model.generate_with_budget(role, context, reserve)
        reserve()
        return model.generate(role, context)

    def accept_envelope(self, request_id, kind, payload):
        envelope = {"kind": kind, "payload": payload, "operation_id": operation(request_id, "accepted_" + kind)}
        self.command("envelope", {"request": request_id, "envelope": envelope}, operation(request_id, "envelope"))
        return envelope

    def replay(self, request_id):
        r = required(self.store.read()["requests"], request_id)
        e = r["envelope"]
        if not e:
            return None
        return self.command(e["kind"], e["payload"], e["operation_id"])

    def planning_snapshot(self):
        s = self.store.read()
        return self.context(s), {tid: bundle(s, tid) for tid in ready(s)}

    def shared_memory(self, text):
        return self.store.conversation_context(text)[1]

    def helper_context(self, handoff, claim):
        initial = required(self.store.read()["handoffs"], handoff)
        s, connected = self.store.task_context(initial["bundle"]["task"])
        h = required(s["handoffs"], handoff)
        t = required(s["tasks"], h["bundle"]["task"])
        if t["claim"] != claim["claim"] or not valid_bundle(s, h["bundle"], claim["execution_version"]):
            raise Rejected("Inputs changed before generation. Replan; no model call made.")
        return {"handoff": h, **connected,
                "procedures": {k: s["procedures"][k] for k in h["bundle"]["procedures"]}}
