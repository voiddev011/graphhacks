"""Aggregate official judge labels with matching-run provenance and error accounting."""
import argparse
import json
from pathlib import Path


def summarize(run_dir, judge_log):
    run = Path(run_dir)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if manifest["dry_run"] or manifest["status"] not in {"complete", "complete_with_errors"}:
        raise ValueError("Only completed answer runs can be scored.")
    rows = [json.loads(line) for line in Path(judge_log).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r["question_id"] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(manifest["selected_ids"]):
        raise ValueError("Judge labels must cover exactly the selected instances, once each.")
    predictions = {r["question_id"]: r["hypothesis"] for r in (json.loads(line) for line in (run / "predictions.jsonl").read_text(encoding="utf-8").splitlines())}
    errors = {r["question_id"] for r in (json.loads(line) for line in (run / "traces.jsonl").read_text(encoding="utf-8").splitlines()) if r["status"] == "error"}
    models, correct = set(), 0
    for row in rows:
        if row.get("hypothesis") != predictions[row["question_id"]]:
            raise ValueError("Judge log answers do not match this run's predictions.")
        label = row["autoeval_label"]
        if not isinstance(label.get("label"), bool) or not label.get("model"):
            raise ValueError("Expected official-style model/boolean judge labels.")
        models.add(label["model"])
        correct += bool(label["label"] and row["question_id"] not in errors)
    if len(models) != 1:
        raise ValueError("Mixed judge models are not a comparable evaluation.")
    result = {"dataset_sha256": manifest["dataset_sha256"], "selected_ids": manifest["selected_ids"],
              "scoring": "Official-style judge labels; execution errors are forced incorrect. Verify scorer provenance separately.",
              "method": manifest["method"], "reader": manifest["model"], "judge": next(iter(models)),
              "cases": len(rows), "correct": correct, "accuracy": correct / len(rows),
              "errors_counted_incorrect": len(errors), "is_subset": manifest["is_subset"],
              "note": "Self-run official-style QA evaluation; no leaderboard acceptance is implied."}
    (run / "score.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--judge-log", required=True)
    args = p.parse_args()
    print(json.dumps(summarize(args.run, args.judge_log), indent=2))
