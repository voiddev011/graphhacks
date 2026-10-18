"""Create a readable, auditable report from a completed LoCoMo pilot."""
import argparse
import csv
import html
import json
from pathlib import Path
import statistics


def report(directory):
    root=Path(directory)
    score=json.loads((root/"score.json").read_text())
    manifest=json.loads((root/"manifest.json").read_text())
    rows=[json.loads(s) for s in (root/"judged.jsonl").read_text().splitlines() if s.strip()]
    score["evaluation_degraded"]=bool(score.get("ingestion_errors") or any(r["status"]!="answered" or r.get("judge_error") for r in rows))
    for method,result in score["results"].items():
        selected=[r for r in rows if r["method"]==method]
        usage=[u for r in selected for u in r.get("usage",[]) if u]
        inputs=[u.get("prompt_tokens",u.get("input_tokens")) for u in usage]
        outputs=[u.get("completion_tokens",u.get("output_tokens")) for u in usage]
        result["mean_input_tokens_successful"]=round(statistics.mean(x for x in inputs if x is not None),1) if any(x is not None for x in inputs) else None
        result["mean_output_tokens_successful"]=round(statistics.mean(x for x in outputs if x is not None),1) if any(x is not None for x in outputs) else None
    score["provider_calls"]=manifest["provider_calls"]
    (root/"score.json").write_text(json.dumps(score,indent=2))
    lines=["# Continuity - LoCoMo pilot results", "", "**Measured results, not an official leaderboard submission.**", "",
        f"Dataset: original LoCoMo, sample `{score['sample_id']}`. {len(score['selected_ids'])} fixed questions per method, categories 1-4; category 5 excluded.",
        "",f"Reader: `{score['model']}`. Extractor: `{score.get('extractor_model',score['model'])}`. Local judge: `{score['judge_model']}`.",
        "",f"Import: {score['ingested_chunks']}/{score['planned_chunks']} chunks accepted; {score['ingestion_errors']} failed. {score['current_memories']} current memories. {score['source_rejections']} proposed memories rejected by source rules.",
        "", "| Method | Token F1 (%) | Local judge correctness (%) | Questions | Answer errors | Judge errors | Mean answer seconds | Mean input tokens (successful) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    if score["evaluation_degraded"]:
        lines.insert(4,"**DEGRADED RUN: import/provider/judge failures occurred. These numbers do not establish memory quality or a fair quality comparison. See the error counts below.**\n")
    for method,r in score["results"].items():
        judge=r["local_judge_accuracy_percent"]
        lines.append(f"| {method} | {r['token_f1_percent']} | {judge if judge is not None else 'Unavailable: judging incomplete'} | {r['questions']} | {r['answer_errors']} | {r['judge_errors']} | {r['mean_answer_seconds']} | {r.get('mean_input_tokens_successful')} |")
    lines += ["", "Token F1 measures stemmed answer-word overlap using the original category rules; it is not percent of questions fully correct.",
        "Local judge correctness measures semantic agreement with the reference. It uses our disclosed free-model judge, not an exact reproduction of Mem0's reader/judge/protocol. Judge errors make this accuracy unavailable.",
        "", "## Category results", "", "| Method | Category | Questions | Token F1 (%) | Local judge correctness (%) |", "|---|---|---:|---:|---:|"]
    for method,r in score["results"].items():
        for category,c in r["per_category"].items():
            lines.append(f"| {method} | {category} | {c['questions']} | {c['token_f1_percent']} | {c['local_judge_accuracy_percent'] if c['local_judge_accuracy_percent'] is not None else 'Unavailable'} |")
    lines += ["", "## What was tested", "",
        "All raw turns of the chosen conversation were offered chronologically to the speaker-aware import extension. It uses the app's MemoryProposal, source validation, versioned domain commits and FalkorDB graph projection. Question answering uses the production conversation_context/select_memories retrieval, no STM, and read-only concise-answer mode. Model fallback and SDK retries were disabled.",
        "", "The import extension batches external dialogue; this is not the unmodified website's one-user-message ingestion mode. Images/captions were not ingested. Reference answers, category labels, evidence IDs, supplied observations and summaries never entered ingestion or answer prompts. Gold references enter only post-answer scoring/judging. Each QA starts without previous question/answer history, and frozen memory is verified unchanged.",
        "", "## Limits and comparison", "",
        "This is one conversation and a deterministic small question subset, not the full LoCoMo corpus. Import, source-rejection and provider errors are exposed rather than hidden. Answer errors score zero in the fixed denominator. Compare graph/no-memory carefully if error rates differ. No result establishes a rank against Mem0's published 1,540-question score; reader, judge, corpus coverage and input mode differ.",
        "", "## Reproduce and inspect", "",
        "See manifest.json for exact model IDs, selected question IDs, dataset SHA-256, revision, call reservations, budgets and protocol. selection.json fixes questions before answering. ingestion.jsonl records import/rejection failures. predictions.jsonl records original answers and retrieved facts. judged.jsonl adds verdicts. memory.json contains source-backed saved memory. Source graphs were temporary and were removed; your projects were untouched.",
        "", "Official data/scorer: https://github.com/snap-research/locomo", "Mem0 comparison context: https://mem0.ai/research"]
    (root/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    fields=["id","method","category","question","reference","answer","f1","correct","status","error_type","judge_error","judge_reason","elapsed_seconds","context_chars","served_by"]
    with (root/"answers.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(rows)
    cards=[]
    for method,r in score["results"].items():
        j=r["local_judge_accuracy_percent"]
        cards.append(f"<section><h2>{'Continuity graph memory' if method=='graph' else 'Same model without memory'}</h2><strong>{r['token_f1_percent']:.2f}%</strong><p>Original-style token F1</p><div class='bar'><i style='width:{r['token_f1_percent']}%'></i></div><strong>{str(j)+'%' if j is not None else 'Unavailable'}</strong><p>Local judge correctness</p><small>{r['questions']} questions; {r['answer_errors']} answer errors; {r['judge_errors']} judge errors.</small></section>")
    page="<!doctype html><meta charset='utf-8'><title>Continuity LoCoMo Pilot</title><style>body{font:17px system-ui;background:#10241f;color:#e8f5ee;max-width:1000px;margin:50px auto;padding:24px}h1{font-size:38px}.cards{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{padding:24px;border:1px solid #4b7567;border-radius:16px;background:#18352c}strong{font-size:42px;color:#9be3c0}p{line-height:1.6}.bar{height:10px;background:#355449;margin:20px 0;border-radius:8px}.bar i{display:block;height:100%;background:#9be3c0}.note{padding:20px;background:#3b3320;border-radius:12px}@media(max-width:650px){.cards{grid-template-columns:1fr}}</style>"
    page+=f"<h1>Continuity - LoCoMo pilot</h1><p>{html.escape(score['sample_id'])}: {len(score['selected_ids'])} fixed questions per method. Original public dataset, subset evaluation.</p><div class='cards'>"+"".join(cards)+"</div>"
    if score["evaluation_degraded"]:
        page=page.replace("<div class='cards'>","<p class='note'><b>DEGRADED RUN.</b> Import/provider/judge failures occurred. Do not interpret these numbers as a reliable memory-quality comparison.</p><div class='cards'>")
    page+=f"<p>Model: {html.escape(score['model'])}<br>Judge: {html.escape(score['judge_model'])}<br>Import: {score['ingested_chunks']}/{score['planned_chunks']} chunks accepted; {score['current_memories']} current memories.</p><p class='note'>Pilot, not a global leaderboard score. Token F1 and judge correctness are different metrics. These results are not directly comparable to Mem0's full published evaluation. Open REPORT.md and answers.csv for protocol, failures, and individual answers.</p>"
    (root/"dashboard.html").write_text(page,encoding="utf-8")
    return score

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--run",required=True);args=p.parse_args();print(json.dumps(report(args.run),indent=2))
