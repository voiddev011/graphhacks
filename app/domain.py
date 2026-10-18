"""Pure rules. No network, model calls, or database code here."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone


class Rejected(ValueError):
    """The command was not accepted; no successful write is implied."""


class Conflict(Rejected):
    pass


class MemoryGroundingRejected(Rejected):
    """One proposed fact lacks valid source grounding; other facts may be valid."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise Rejected("Use an ID of 1–80 letters, digits, underscores or hyphens.")
    return value


def empty_project(project):
    return {"id": identifier(project), "revision": 0, "messages": {}, "decisions": {},
            "versions": {}, "tasks": {}, "results": {}, "reviews": {}, "procedures": {},
            "handoffs": {}, "attempts": {}, "requests": {}, "operations": {}}


def required(mapping, key):
    if key not in mapping:
        raise Rejected(f"Unknown or out-of-scope reference: {key}")
    return mapping[key]


def current_inputs(s, task):
    return {key: required(s["decisions"], key) for key in task["requires"]}


def satisfied(s, task_id, trail=()):
    if task_id in trail:
        raise Rejected("Prerequisite cycle.")
    task = required(s["tasks"], task_id)
    result = s["results"].get(task.get("result"))
    if task["status"] != "completed" or not result or result["review_state"] != "valid":
        return False
    coverage = dict(result["based_on"])
    for review_id in result["reviews"]:
        coverage.update(s["reviews"][review_id]["validated_against"])
    if coverage != current_inputs(s, task):
        return False
    return all(satisfied(s, dep, (*trail, task_id)) for dep in task["prerequisites"])


def ready(s):
    return [t["id"] for t in s["tasks"].values()
            if t["status"] == "pending"
            and all(k in s["decisions"] for k in t["requires"])
            and all(satisfied(s, p) for p in t["prerequisites"])
            and all(k in s["procedures"] for k in t["procedures"])]


def bundle(s, task_id):
    t = required(s["tasks"], task_id)
    return {"task": task_id, "task_version": t["version"], "decisions": current_inputs(s, t),
            "procedures": {k: required(s["procedures"], k)["id"] for k in t["procedures"]},
            "prerequisites": {p: {"version": s["tasks"][p]["version"],
                                  "result": s["tasks"][p].get("result"),
                                  "valid": satisfied(s, p)} for p in t["prerequisites"]}}


def valid_bundle(s, b, execution_version=None):
    try:
        fresh = bundle(s, b["task"])
    except Rejected:
        return False
    expected = copy.deepcopy(b)
    if execution_version is not None:
        expected["task_version"] = execution_version
    return fresh == expected and all(p["valid"] for p in fresh["prerequisites"].values())


def source(s, message_id, passage, user=True):
    m = required(s["messages"], message_id)
    if user and m["speaker"] != "user":
        raise Rejected("This change needs an explicit user source.")
    if not isinstance(passage, str) or not passage.strip() or passage not in m["text"]:
        raise Rejected("The exact source passage must occur in the supplied message.")
    if user and re.search(r"\b(maybe|perhaps|might|could|consider|suggest|what if)\b|\?", passage, re.I):
        raise Rejected("Speculative wording needs a new explicit confirmation.")
    return {"message": message_id, "passage": passage, "provenance": m["provenance"]}


ALLOWED = {"interface_framework": {"React", "Streamlit"},
           "database_engine": {"FalkorDB", "SQLite", "PostgreSQL"},
           "response_style": {"short", "simple", "detailed"}}


def transition(state, kind, payload, operation_id):
    """Compute against one immutable snapshot. Repository CAS guards final commit."""
    s = copy.deepcopy(state)
    opkey = f"{kind}:{identifier(operation_id)}"
    fingerprint = digest(payload)
    old = s["operations"].get(opkey)
    if old:
        if old["hash"] != fingerprint:
            raise Conflict("Operation ID already has a different payload.")
        return s, old["result"], False
    result, visible = apply(s, kind, payload, operation_id)
    if visible:
        s["revision"] += 1
    receipt = {"kind": kind, "operation_id": operation_id, **result}
    s["operations"][opkey] = {"hash": fingerprint, "result": receipt}
    return s, receipt, True


def apply(s, kind, p, oid):
    if kind == "chat_turn":
        from .conversation import ChatResponse, TranscriptResponse, slot_key
        m = required(s["messages"], p["message"])
        imported = m["speaker"] == "transcript"
        response = (TranscriptResponse if imported else ChatResponse).model_validate(p["response"])
        request = required(s["requests"], p["request"])
        if m["speaker"] not in {"user", "transcript"} or request["input"]["text"] != m["text"]:
            raise Rejected("Conversation memories require the current user's message.")
        identifier(p["thread"])
        known = {s.get("memory_slots", {}).get(key) for key in s.get("memory_slots", {})}
        if not set(p["retrieved"]) <= known or not set(response.citations) <= set(p["retrieved"]):
            raise Rejected("Conversation evidence is no longer current.")
        slots = s.setdefault("memory_slots", {})
        versions = s.setdefault("memory_versions", {})
        saved, seen = [], set()
        for fact in response.memories:
            try:
                src = source(s, p["message"], fact.passage, user=not imported)
            except Rejected as exc:
                raise MemoryGroundingRejected(str(exc)) from exc
            if imported:
                turn = next((t for t in m.get("metadata", {}).get("turns", []) if t["dia_id"] == fact.dialogue_id), None)
                if not turn or fact.passage not in turn["text"]:
                    raise Rejected("Imported memory must cite an exact original dialogue turn.")
                if fact.subject.casefold() == "user":
                    raise Rejected("Imported speakers cannot be merged into the local user's identity.")
                src.update(dialogue_id=fact.dialogue_id, speaker=turn["speaker"],
                           session_date=m["metadata"]["session_date"])
            # Validate the containing sentence, not a conveniently selected fragment
            # of a question or hypothetical. This is conservative by design.
            start = m["text"].find(fact.passage)
            left = max((m["text"].rfind(c, 0, start) for c in ".!?;\n"), default=-1) + 1
            ends = [m["text"].find(c, start + len(fact.passage) - 1) for c in ".!?;\n"]
            end = min((x for x in ends if x >= 0), default=len(m["text"]) - 1) + 1
            sentence = m["text"][left:end]
            if re.search(r"\?|\b(maybe|perhaps|might|could|what if|suppose|imagine)\b", sentence, re.I):
                raise MemoryGroundingRejected("A question or hypothetical cannot become an asserted memory.")
            if fact.value.casefold() not in fact.passage.casefold():
                raise MemoryGroundingRejected("Memory value must occur in its exact user source.")
            if fact.kind != "procedural" and re.search(r"\b(not|never|don't|do not|no longer)\b", sentence, re.I):
                raise MemoryGroundingRejected("Negated statements need a clear positive correction before storing a fact.")
            subject = " ".join(fact.subject.casefold().split())
            relation = "_".join(fact.relation.casefold().split())
            if fact.memory_key:
                old_id = required(slots, fact.memory_key)
                old_fact = versions[old_id]
                if old_id not in p["retrieved"] or old_fact["kind"] != fact.kind:
                    raise Rejected("A correction must reference a retrieved memory of the same type.")
                key = fact.memory_key
                subject, relation = old_fact["subject"], old_fact["relation"]
            else:
                key = slot_key(subject, relation, fact.kind, p["message"], fact.cardinality, fact.value)
            if key in seen:
                raise Rejected("Only one new value per memory slot may be saved in a turn.")
            seen.add(key)
            previous = slots.get(key)
            if previous != p["expected"].get(key):
                raise Rejected("This memory changed while answering. Send the correction again with a new request.")
            if previous and versions[previous]["value"].casefold() == fact.value.casefold():
                continue
            vid = "fact_" + digest([oid, key])[:40]
            versions[vid] = {"id": vid, "slot": key, "subject": subject, "relation": relation,
                "value": fact.value, "kind": fact.kind, "source": src, "supersedes": previous,
                "cardinality": fact.cardinality,
                "recorded_at": now()}
            slots[key] = vid
            saved.append(vid)
        turn_id = "turn_" + oid
        warnings=p.get("memory_warnings",[])
        if not isinstance(warnings,list) or len(warnings)>8 or any(not isinstance(w,str) or len(w)>800 for w in warnings):
            raise Rejected("Invalid memory warning metadata.")
        s.setdefault("chat_turns", {})[turn_id] = {"id": turn_id, "thread": p["thread"],
            "agent_role": p["agent_role"], "message": p["message"], "reply": response.reply,
            "citations": response.citations, "retrieved": p["retrieved"], "saved": saved,
            "suggested_task": response.suggested_task, "provider": p["provider"],
            "memory_warnings": warnings,
            "recorded_at": now(), "handoff": None}
        return {"turn": turn_id, "saved": saved}, True

    if kind == "chat_link":
        turn = required(s.get("chat_turns", {}), p["turn"])
        required(s["handoffs"], p["handoff"])
        if turn["handoff"] and turn["handoff"] != p["handoff"]:
            raise Conflict("This conversation already has a saved plan.")
        turn["handoff"] = p["handoff"]
        return {"handoff": p["handoff"]}, True

    if kind == "message":
        mid = identifier(p["id"])
        if p["speaker"] not in {"user", "assistant", "transcript"} or not p["text"].strip():
            raise Rejected("A nonempty user or assistant message is required.")
        m = {"id": mid, "text": p["text"], "speaker": p["speaker"], "recorded_at": now(),
             "provenance": {"user":"user_assertion", "assistant":"assistant_suggestion", "transcript":"external_transcript"}[p["speaker"]]}
        if "metadata" in p:
            m["metadata"] = p["metadata"]
        if mid in s["messages"]:
            existing = s["messages"][mid]
            if (existing["text"], existing["speaker"]) != (p["text"], p["speaker"]):
                raise Conflict("Message identity conflict.")
            if existing.get("metadata", {}) != p.get("metadata", {}):
                raise Conflict("Message source metadata conflict.")
        else:
            s["messages"][mid] = m
        return {"message": mid}, False

    if kind == "decision":
        key, value = p["key"], p["value"]
        if key not in ALLOWED or value not in ALLOWED[key]:
            raise Rejected("Decision key/value is outside the configured schema.")
        src = source(s, p["message"], p["passage"])
        if key not in p["passage"] or value not in p["passage"]:
            raise Rejected("For typed writes, explicitly name the decision key and value in the source.")
        previous = s["decisions"].get(key)
        if previous and s["versions"][previous]["value"] == value:
            return {"decision": previous, "unchanged": True}, False
        did = "decision_" + oid
        s["versions"][did] = {"id": did, "key": key, "value": value, "source": src,
                                 "supersedes": previous, "recorded_at": now()}
        s["decisions"][key] = did
        affected = []
        for t in s["tasks"].values():
            if key not in t["requires"] or t["status"] != "completed":
                continue
            r = s["results"][t["result"]]
            r["review_state"] = "requires_review"
            t["version"] += 1
            affected.append(t["id"])
        return {"decision": did, "review_tasks": affected}, True

    if kind == "task":
        tid = identifier(p["id"])
        if tid in s["tasks"]:
            raise Rejected("Task ID already exists.")
        deps, keys, procs = sorted(set(p.get("prerequisites", []))), sorted(set(p.get("requires", []))), sorted(set(p.get("procedures", [])))
        for dep in deps:
            required(s["tasks"], dep)
        if any(k not in ALLOWED or k == "response_style" for k in keys):
            raise Rejected("Declare only configured implementation inputs.")
        for proc in procs:
            required(s["procedures"], proc)
        if not p["title"].strip():
            raise Rejected("Task title is required.")
        s["tasks"][tid] = {"id": tid, "title": p["title"], "status": "pending", "version": 1,
                             "requires": keys, "procedures": procs, "prerequisites": deps, "result": None, "claim": None}
        return {"task": tid}, True

    if kind == "procedure":
        src = source(s, p["message"], p["passage"])
        if p.get("approved") is not True or not p["steps"] or len(p["steps"]) > 10 or any(not x.strip() for x in p["steps"]):
            raise Rejected("Explicit approval and 1–10 nonempty steps are required.")
        if canonical(p["steps"]) not in p["passage"]:
            raise Rejected("Approval source must include the exact JSON steps array.")
        name = identifier(p["name"])
        proc = {"id": "procedure_" + oid, "name": name, "steps": p["steps"], "source": src, "approved": True,
                "trigger": "Before performing a task that explicitly declares this procedure."}
        # Preserve every version in a separate immutable history map.
        s.setdefault("procedure_versions", {})[proc["id"]] = proc
        s["procedures"][name] = proc
        return {"procedure": proc["id"]}, True

    if kind == "handoff":
        b = p["bundle"]
        if any(s.get("memory_slots", {}).get(k) != v for k,v in p.get("memory_inputs", {}).items()):
            raise Rejected("Shared memories changed during planning. Start a new request.")
        if b["task"] not in ready(s) or not valid_bundle(s, b):
            raise Rejected("Planning inputs changed or task is not eligible. Replan.")
        hid = "handoff_" + oid
        s["handoffs"][hid] = {"id": hid, "objective": p["objective"], "bundle": b,
                                 "status": "saved", "draft": None, "claim": None,
                                 "memory_inputs": p.get("memory_inputs", {})}
        return {"handoff": hid}, True

    if kind == "claim":
        h = required(s["handoffs"], p["handoff"])
        b = h["bundle"]
        t = required(s["tasks"], b["task"])
        if t["status"] != "pending" or not valid_bundle(s, b) or h["status"] != "saved":
            raise Rejected("Handoff is stale or already claimed. Replan or explicitly release.")
        claim = {"id": "claim_" + oid, "owner": identifier(p["owner"])}
        t.update(status="in_progress", claim=claim, version=t["version"] + 1)
        h.update(status="claimed", claim=claim, execution_version=t["version"])
        return {"handoff": h["id"], "claim": claim, "execution_version": t["version"]}, True

    if kind in {"draft", "complete"}:
        h = required(s["handoffs"], p["handoff"])
        t = required(s["tasks"], h["bundle"]["task"])
        # Caller must submit the exact claim and execution version it received.
        owns = t["claim"] is not None and t["claim"] == p["claim"] and h["claim"] == p["claim"]
        good = owns and h.get("execution_version") == p["execution_version"] and t["status"] == "in_progress" and valid_bundle(s, h["bundle"], p["execution_version"])
        good = good and all(s.get("memory_slots", {}).get(k) == v for k,v in p.get("memory_inputs", {}).items())
        if kind == "complete":
            evidence = source(s, p["message"], p["passage"])
            if not p["passage"].strip() or not p["outcome"].strip():
                raise Rejected("A user-reported outcome and source evidence are required.")
            if p["outcome"] not in p["passage"]:
                raise Rejected("Reported outcome must occur in the exact evidence passage.")
        else:
            evidence = {"provenance": "assistant_draft"}
        aid = "attempt_" + oid
        s["attempts"][aid] = {"id": aid, "task": t["id"], "handoff": h["id"],
                                 "content": p.get("draft", p.get("outcome", "")), "source": evidence,
                                 "stale": not good, "bundle": copy.deepcopy(h["bundle"]),
                                 "memory_inputs": p.get("memory_inputs", {})}
        if not good:
            # Do not clear a newer owner's claim.
            if owns:
                t.update(status="pending", claim=None, version=t["version"] + 1)
                h["status"] = "stale"
            return {"accepted": False, "stale": True, "attempt": aid, "reason": "Inputs or claim changed; replan."}, True
        if kind == "draft":
            h["draft"] = aid
            return {"accepted": True, "attempt": aid, "completed": False}, True
        rid = "result_" + oid
        s["results"][rid] = {"id": rid, "task": t["id"], "outcome": p["outcome"],
                                "source": {**evidence, "provenance": "user_reported_outcome"},
                                "based_on": copy.deepcopy(h["bundle"]["decisions"]),
                                "input_bundle": copy.deepcopy(h["bundle"]),
                                "review_state": "valid", "reviews": []}
        t.update(status="completed", result=rid, claim=None, version=t["version"] + 1)
        h["status"] = "completed"
        return {"accepted": True, "result": rid, "attempt": aid}, True

    if kind == "release":
        t = required(s["tasks"], p["task"])
        src = source(s, p["message"], p["passage"])
        if p.get("confirmed") is not True or not t["claim"] or p["claim"] != t["claim"]:
            raise Rejected("Explicit confirmation and the current claim are required.")
        for h in s["handoffs"].values():
            if h["claim"] == t["claim"]:
                h["status"] = "released"
        t.update(status="pending", claim=None, version=t["version"] + 1)
        return {"released": t["id"], "source": src}, True

    if kind == "review":
        t = required(s["tasks"], p["task"])
        r = required(s["results"], t.get("result"))
        src = source(s, p["message"], p["passage"])
        if p.get("confirmed") is not True or t["status"] != "completed":
            raise Rejected("An explicit user resolution of completed work is required.")
        if p.get("task_version") != t["version"] or p.get("decisions") != current_inputs(s, t):
            raise Rejected("Review inputs changed since confirmation. Inspect current evidence and confirm again with a new request ID.")
        action = p["action"]
        if action == "confirm":
            review_id = "review_" + oid
            s["reviews"][review_id] = {"id": review_id, "result": r["id"], "source": src,
                                           "validated_against": current_inputs(s, t)}
            r["reviews"].append(review_id)
            r["review_state"] = "valid"
        elif action == "reopen":
            t.update(status="pending", result=None)
        elif action == "replace":
            new_id = identifier(p["replacement"])
            if new_id in s["tasks"]:
                raise Rejected("Replacement task ID already exists.")
            dependents = sorted(x["id"] for x in s["tasks"].values() if t["id"] in x["prerequisites"])
            if sorted(p["rewire"]) != dependents:
                raise Rejected("Explicitly confirm the exact dependent task IDs to rewire.")
            replacement = copy.deepcopy(t)
            replacement.update(id=new_id, title=p.get("title", t["title"]), status="pending", result=None, version=1, claim=None, replaces=t["id"])
            s["tasks"][new_id] = replacement
            for dep in dependents:
                dt = s["tasks"][dep]
                dt["prerequisites"] = sorted(new_id if x == t["id"] else x for x in dt["prerequisites"])
                dt["version"] += 1
        else:
            raise Rejected("Choose confirm, reopen or replace.")
        t["version"] += 1
        return {"task": t["id"], "resolution": action, "source": src}, True

    if kind == "request":
        rid = identifier(p["id"])
        existing = s["requests"].get(rid)
        if existing and existing["input_hash"] != digest(p["input"]):
            raise Conflict("Request ID has a different input.")
        if not existing:
            s["requests"][rid] = {"id": rid, "input_hash": digest(p["input"]), "input": p["input"], "calls": 0, "envelope": None}
        return {"request": rid}, False

    if kind == "attempt_call":
        request = required(s["requests"], p["request"])
        if request["calls"] >= 3:
            raise Rejected("Provider-attempt budget exhausted (3 per request, including failures).")
        request["calls"] += 1
        return {"calls": request["calls"]}, False

    if kind == "envelope":
        request = required(s["requests"], p["request"])
        if request["envelope"] and request["envelope"] != p["envelope"]:
            raise Conflict("Accepted request envelope is immutable; use a new request to replan.")
        request["envelope"] = p["envelope"]
        return {"envelope": request["envelope"]}, False
    raise Rejected("Unknown command.")
