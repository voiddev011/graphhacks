"""Fixtures for isolated automated tests only. Never loaded by the live app."""
from app.domain import canonical
from app.service import operation


def seed(service):
    def decision(key, value):
        text = f"Set {key} to {value}."
        msg = service.message(text, request_id="seed_" + key)
        return service.command("decision", {"key": key, "value": value, "message": msg, "passage": text}, operation("seed", key))

    decision("interface_framework", "React")
    decision("database_engine", "FalkorDB")
    decision("response_style", "simple")
    steps = ["Check current decisions.", "Perform the task.", "Verify the result and report what actually happened."]
    text = "I approve this procedure: " + canonical(steps)
    message = service.message(text, request_id="seed_procedure")
    service.command("procedure", {"name": "build", "steps": steps, "approved": True, "message": message, "passage": text}, operation("seed", "procedure"))
    for t in [
        {"id": "interface", "title": "Build a tiny study interface", "requires": ["interface_framework"], "procedures": ["build"]},
        {"id": "storage", "title": "Save a synthetic study preference", "requires": ["database_engine"], "procedures": ["build"]},
        {"id": "deploy", "title": "Run the study app end to end", "prerequisites": ["interface", "storage"]},
        {"id": "readme", "title": "Write the local setup instructions"},
    ]:
        service.command("task", t, operation("seed", "task_" + t["id"]))
    return {"seeded": True, "project": service.store.read()["id"]}
