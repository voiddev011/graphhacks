"""Run with python -m app.cli --help. No external execution tools are exposed."""
from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from .domain import Rejected, bundle, canonical, current_inputs, ready, required, valid_bundle
from .repository import FalkorStore
from .service import Service, new_id, operation


def parser():
    p = argparse.ArgumentParser(description="Continuity: synthetic project memory and safe resumption")
    p.add_argument("--tenant", default="userA", help="Local synthetic selector, not authentication")
    p.add_argument("--project", default="apollo")
    sub = p.add_subparsers(dest="action", required=True)
    for name in ("status", "history", "requests", "doctor"):
        sub.add_parser(name)
    d = sub.add_parser("decide")
    d.add_argument("key")
    d.add_argument("value")
    d.add_argument("--request-id")
    t = sub.add_parser("task")
    t.add_argument("id")
    t.add_argument("title")
    t.add_argument("--requires", nargs="*", default=[])
    t.add_argument("--depends", nargs="*", default=[])
    t.add_argument("--procedure", nargs="*", default=[])
    t.add_argument("--request-id")
    proc = sub.add_parser("procedure")
    proc.add_argument("name")
    proc.add_argument("steps", help='JSON array of 1–10 approved step strings')
    proc.add_argument("--approve", action="store_true", required=True)
    proc.add_argument("--request-id")
    for name in ("plan", "help"):
        g = sub.add_parser(name)
        g.add_argument("text", nargs="?", default="Help me resume this project.")
        g.add_argument("--request-id")
        if name == "help":
            g.add_argument("handoff")
            g.add_argument("--owner", default="helper")
        else:
            g.add_argument("--new-task", action="store_true", help="Save your supplied description as a new task and plan it with Gemini")
    c = sub.add_parser("complete")
    c.add_argument("handoff")
    c.add_argument("outcome", help="Your actual reported outcome; the app has not independently verified it")
    c.add_argument("--request-id")
    r = sub.add_parser("review")
    r.add_argument("task")
    r.add_argument("resolution", choices=["confirm", "reopen", "replace"])
    r.add_argument("--replacement")
    r.add_argument("--rewire", nargs="*", default=[])
    r.add_argument("--confirm", action="store_true", required=True)
    r.add_argument("--request-id")
    release = sub.add_parser("release")
    release.add_argument("task")
    release.add_argument("--confirm", action="store_true", required=True)
    release.add_argument("--request-id")
    replay = sub.add_parser("replay")
    replay.add_argument("request_id")
    return p


def run(args):
    s = Service(FalkorStore(args.tenant, args.project))
    state = s.store.read()
    if args.action == "doctor":
        return {"database": "connected", "graph": s.store.graph_name, "project": args.project,
                "checkpoint": "Deferred: durable business handoffs, fresh workflow sessions only.",
                "note": "Use README persistence commands to verify AOF and volume separately."}
    if args.action == "status":
        return {"project": args.project, "revision": state["revision"], "eligible": ready(state),
                "tasks": state["tasks"], "handoffs": state["handoffs"], "results": state["results"], "attempts": state["attempts"]}
    if args.action == "history":
        return {"current": state["decisions"], "versions": state["versions"], "reviews": state["reviews"]}
    if args.action == "requests":
        return state["requests"]
    if args.action == "replay":
        return s.replay(args.request_id) or {"accepted": False, "reason": "Request has no accepted envelope; resume plan/help with its original input and ID."}
    rid = getattr(args, "request_id", None) or new_id()
    # Print before any dispatch: retain this ID to retry after a lost response.
    print("Request ID: " + rid, file=sys.stderr)
    if args.action in {"task", "procedure", "review", "release"}:
        ui_input = {k: v for k, v in vars(args).items() if k != "request_id"}
        s.begin(rid, args.action, canonical(ui_input))
        replay = s.replay(rid)
        if replay:
            return replay

    def accept(kind, payload):
        e = s.accept_envelope(rid, kind, payload)
        return s.command(kind, payload, e["operation_id"])

    if args.action == "task":
        return accept("task", {"id": args.id, "title": args.title, "requires": args.requires,
                               "prerequisites": args.depends, "procedures": args.procedure})
    if args.action == "procedure":
        steps = json.loads(args.steps)
        if not isinstance(steps, list) or any(not isinstance(x, str) for x in steps):
            raise Rejected("Steps must be a JSON array of strings.")
        text = "I approve this procedure: " + canonical(steps)
        msg = s.message(text, request_id=rid)
        return accept("procedure", {"name": args.name, "steps": steps, "approved": args.approve,
                                    "message": msg, "passage": text})
    if args.action == "decide":
        text = f"Set {args.key} to {args.value}."
        s.begin(rid, "decision", text)
        replay = s.replay(rid)
        if replay:
            return replay
        msg = s.message(text, request_id=rid)
        p = {"key": args.key, "value": args.value, "message": msg, "passage": text}
        return accept("decision", p)
    if args.action in {"plan", "help"}:
        from .models import Gemini
        from .workflow import build
        print("LIVE GEMINI", file=sys.stderr)
        if args.action == "plan" and args.new_task:
            if args.text == "Help me resume this project.":
                raise Rejected("Supply your own task description with --new-task.")
            from .actions import plan_new_task
            return plan_new_task(s, rid, args.text)
        result = build(s, Gemini()).invoke({
            "role": "planner" if args.action == "plan" else "helper", "request_id": rid,
            "text": args.text, "handoff": getattr(args, "handoff", None), "owner": getattr(args, "owner", None)})
        receipt = result["receipt"]
        if receipt.get("attempt"):
            receipt = {**receipt, "draft": s.store.read()["attempts"][receipt["attempt"]]["content"]}
        return receipt
    if args.action == "complete":
        s.begin(rid, "complete", args.outcome, args.handoff)
        replay = s.replay(rid)
        if replay:
            return replay
        h = required(state["handoffs"], args.handoff)
        msg = s.message(args.outcome, request_id=rid)
        p = {"handoff": h["id"], "claim": h["claim"], "execution_version": h.get("execution_version"),
             "outcome": args.outcome, "message": msg, "passage": args.outcome}
        e = s.accept_envelope(rid, "complete", p)
        return s.command("complete", p, e["operation_id"])
    if args.action == "review":
        text = f"I confirm {args.resolution} for task {args.task}; replacement={args.replacement}; rewire={args.rewire}."
        msg = s.message(text, request_id=rid)
        t = required(state["tasks"], args.task)
        return accept("review", {"task": args.task, "action": args.resolution, "confirmed": args.confirm,
                                    "replacement": args.replacement, "rewire": args.rewire,
                                    "task_version": t["version"], "decisions": current_inputs(state, t),
                                    "message": msg, "passage": text})
    if args.action == "release":
        text = "I confirm release of task " + args.task
        msg = s.message(text, request_id=rid)
        t = required(state["tasks"], args.task)
        return accept("release", {"task": args.task, "claim": t["claim"], "confirmed": args.confirm,
                                  "message": msg, "passage": text})


def main():
    load_dotenv()
    args = parser().parse_args()
    try:
        print(json.dumps(run(args), indent=2, ensure_ascii=False))
    except Exception as exc:
        # Avoid displaying connection URLs, credentials, provider payloads, or keys.
        message = str(exc) if isinstance(exc, (Rejected, ValueError)) else "Database/provider call failed; no success is claimed. Retry using the same request ID."
        if "DEADLINE_EXCEEDED" in str(exc) or type(exc).__name__ in {"ReadTimeout", "ConnectTimeout"}:
            message = "Gemini request timed out; no AI result was accepted. Retry the original command with its printed --request-id."
        print(f"{type(exc).__name__}: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
