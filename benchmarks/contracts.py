"""Small synthetic business-contract evaluation, NOT an external memory benchmark."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from app.domain import Conflict, Rejected, bundle, current_inputs, digest, ready, satisfied, valid_bundle
from tests.fixtures import seed
from app.repository import FalkorStore
from app.service import Service


def run_checks(store=None):
    owned = store is None
    store = store or FalkorStore("eval_" + uuid.uuid4().hex, "checks")
    service = Service(store)
    rows = []
    started = time.perf_counter()

    def check(name, condition, detail):
        rows.append({"check": name, "passed": bool(condition), "detail": detail})

    def finish(tid):
        h = service.command("handoff", {"objective": "Synthetic evaluation task", "bundle": bundle(store.read(), tid)})["handoff"]
        c = service.command("claim", {"handoff": h, "owner": "evaluator"})
        text = "The evaluator supplies a synthetic user-reported outcome."
        msg = service.message(text)
        payload = {"handoff": h, "claim": c["claim"], "execution_version": c["execution_version"],
                   "outcome": text, "message": msg, "passage": text}
        receipt = service.command("complete", payload, "complete_" + tid)
        return receipt, payload

    try:
        seed(service)
        s = store.read()
        original = s["decisions"]["interface_framework"]
        check("Current decision has an exact source", s["versions"][original]["source"]["passage"] == "Set interface_framework to React.", "Factual memory retains its user assertion.")
        check("Unfinished prerequisites block deployment", "deploy" not in ready(s), "Deployment requires accepted interface and storage results.")
        finish("storage")
        b = bundle(store.read(), "interface")
        hid = service.command("handoff", {"objective": "Resume interface", "bundle": b})["handoff"]
        fresh = Service(store)
        check("A new service can load the handoff", fresh.store.read()["handoffs"][hid]["bundle"] == b, "This checks a new service object; process restart is a separate integration check.")
        text = "Set response_style to short."
        msg = service.message(text)
        service.command("decision", {"key": "response_style", "value": "short", "message": msg, "passage": text})
        check("Presentation changes preserve technical validity", valid_bundle(store.read(), b), "Only declared implementation inputs invalidate work.")
        c = service.command("claim", {"handoff": hid, "owner": "evaluator"})
        check("Claim uses its new execution version", valid_bundle(store.read(), b, c["execution_version"]), "Claiming does not invalidate itself.")
        service.command("draft", {"handoff": hid, "claim": c["claim"], "execution_version": c["execution_version"], "draft": "Synthetic proposed steps."})
        check("A draft does not complete a task", store.read()["tasks"]["interface"]["result"] is None, "Assistant suggestions remain drafts.")
        text = "Synthetic user reports interface work checked."
        msg = service.message(text)
        payload = {"handoff": hid, "claim": c["claim"], "execution_version": c["execution_version"], "outcome": text, "message": msg, "passage": text}
        receipt = service.command("complete", payload, "interface_complete")
        before = store.read()
        check("Valid completed prerequisites unblock deployment", "deploy" in ready(before), "Both prerequisites now have accepted user-reported outcomes.")
        service.command("complete", payload, "interface_complete")
        check("Retry has one logical effect", store.read() == before, "Same operation ID/hash returns the old receipt without another version bump.")
        rejected = False
        try:
            service.command("complete", {**payload, "outcome": "Different"}, "interface_complete")
        except Conflict:
            rejected = True
        check("Changed retry payload is rejected", rejected and store.read() == before, "ID reuse cannot change the accepted command.")
        text = "Set interface_framework to Streamlit."
        msg = service.message(text)
        service.command("decision", {"key": "interface_framework", "value": "Streamlit", "message": msg, "passage": text})
        s = store.read()
        result = s["results"][receipt["result"]]
        check("Correction preserves prior decision history", original in s["versions"] and s["versions"][s["decisions"]["interface_framework"]]["supersedes"] == original, "React remains historical; Streamlit is current.")
        check("Affected result requires review", result["review_state"] == "requires_review", "The old result is retained.")
        check("Review-required prerequisite blocks deployment", "deploy" not in ready(s), "A changed decision cannot silently validate earlier work.")
        text = "The synthetic user confirms the existing result remains compatible."
        msg = service.message(text)
        task = s["tasks"]["interface"]
        service.command("review", {"task": "interface", "action": "confirm", "confirmed": True, "task_version": task["version"],
                                   "decisions": current_inputs(s, task), "message": msg, "passage": text})
        s = store.read()
        check("Explicit compatibility review unblocks deployment", "deploy" in ready(s), "A user judgment validates compatibility; it does not claim a rebuild.")
        check("Review preserves original result inputs", s["results"][receipt["result"]]["based_on"]["interface_framework"] == original, "Review coverage is appended separately from the original evidence.")
    except Exception as exc:
        # Store a safe diagnostic, never a connection URL/provider payload.
        rows.append({"check": "Evaluation execution", "passed": False, "detail": str(exc) if isinstance(exc, Rejected) else type(exc).__name__})
    finally:
        if owned:
            store.graph.delete()
    passed = sum(r["passed"] for r in rows)
    return {"suite": "continuity-contracts-v1", "kind": "synthetic deterministic contract checks",
            "external_benchmark": False, "model_calls": 0, "backend": "FalkorDB" if owned or isinstance(store, FalkorStore) else "RAM test adapter",
            "recorded_at": datetime.now(timezone.utc).isoformat(), "planned_checks": 14,
            "passed": passed, "executed": len(rows), "pass_rate": passed / 14,
            "elapsed_seconds": round(time.perf_counter() - started, 3), "checks": rows}


if __name__ == "__main__":
    import json
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()
    report = run_checks()
    Path("reports").mkdir(exist_ok=True)
    Path("reports/scenario-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] == 14 else 1)
