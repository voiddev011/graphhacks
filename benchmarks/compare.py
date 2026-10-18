"""Compare scored local runs only when their evaluation protocols match."""
import argparse
import json
from pathlib import Path
from statistics import mean


def compare(directories, varying="memory"):
    if len(directories) < 2:
        raise ValueError("Provide at least two scored runs.")
    rows, reference = [], None
    for directory in directories:
        folder = Path(directory)
        m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        score = json.loads((folder / "score.json").read_text(encoding="utf-8"))
        if m["dry_run"] or score["dataset_sha256"] != m["dataset_sha256"] or score["selected_ids"] != m["selected_ids"]:
            raise ValueError("Score provenance does not match this answer run.")
        if score["reader"] != m["model"] or score["method"] != m["method"] or score["cases"] != m["cases"]:
            raise ValueError("Score configuration does not match its manifest.")
        protocol = {k: m[k] for k in ["adapter", "dataset_sha256", "selected_ids", "context_chars", "temperature", "max_output_tokens", "max_retries", "top_k", "timeout_seconds", "thinking"]}
        protocol.update(judge=score["judge"], scoring=score.get("scoring"))
        protocol["fixed_reader" if varying == "memory" else "fixed_memory"] = m["model"] if varying == "memory" else m["method"]
        if reference is not None and protocol != reference:
            raise ValueError("Runs differ in a required fixed setting. Match dataset, cases, judge, reader/memory and budgets before comparing.")
        reference = protocol
        traces = [json.loads(line) for line in (folder / "traces.jsonl").read_text(encoding="utf-8").splitlines()]
        rows.append({"run": str(folder), "method": m["method"], "reader": m["model"], "accuracy": score["accuracy"],
                     "cases": score["cases"], "is_subset": m["is_subset"], "errors": m["errors"],
                     "mean_total_seconds": round(mean(t["elapsed_seconds"] for t in traces), 3),
                     "provider_calls": m["provider_calls"]})
    return {"comparison": varying, "scope": "Local, protocol-matched runs; not global leaderboard placement", "runs": sorted(rows, key=lambda r: r["accuracy"], reverse=True)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("runs", nargs="+")
    p.add_argument("--vary", choices=["memory", "reader"], default="memory")
    args = p.parse_args()
    print(json.dumps(compare(args.runs, args.vary), indent=2))
