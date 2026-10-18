# Graph Hacks: event facts and Track 2

Checked: 18 October 2026, IST. This file summarizes the public overview, rules,
schedule, and resources pages. Project choices are in [PROJECT_PLAN.md](PROJECT_PLAN.md).

**Status:** implementation has started. See [actual implementation and executed
checks](IMPLEMENTATION_STATUS.md). Event facts below are separate from application
verification; no checkpoint or external benchmark result is claimed.

## Event and tracks

Graph Hacks is an online, worldwide WeMakeDevs event with FalkorDB. Entry is free;
beginners can join alone or in groups of at most four. The advertised prize pool
is $20,000, with each winning team member receiving their track's prize.

| Track | Focus | Advertised prize |
|---|---|---|
| 1: Agents That Act on Connected Data | Decisions and actions using relationships | iPhone 18 Pro |
| 2: Agent Memory and Coordination | Durable, changing memories shared by agents | PS5 with GTA VI |
| 3: Company Brain | Connected organizational knowledge | M6 Mac Mini |

Track 2 highlights semantic, episodic, and procedural memory; retained conversations;
shared state and handoffs; concurrent access; and memory separated by user or tenant.
The graph must influence behavior and support traceable results.

Side awards: AirPods 5 for the best project blog and shirts for members of the
top 50 teams. Entering several tracks is allowed.

Source: [official overview and FAQ](https://www.wemakedevs.org/hackathons/falkordb).

## Dates and registration

- Opening: 15 October 2026 at 12:01 AM IST.
- Closing: **18 October 2026 at 11:59 PM IST**.
- Registration and team additions remain available before closing.
- Sign into WeMakeDevs and register on the event page; team/submission management
  is through that panel.

Today is the final advertised event day. Use the dated schedule rather than the
site's generic countdown or registration copy. No separate judging date or kickoff
session time is supplied on the public schedule reviewed.

Source: [schedule](https://www.wemakedevs.org/hackathons/falkordb/schedule).

## Rules and submission checklist

Each person can join one team. FalkorDB must be essential to the product;
local, self-hosted, and Cloud deployments are permitted. Other technologies are
your choice. Declare every entered track.

Use permitted public, synthetic, or owned data; the rules prohibit restricted,
paywalled, private, and personal information. Main design/coding belongs inside
the event window; earlier notes and sketches are allowed. Libraries/templates
are permitted, while judging concerns participants' original event work.

Submit:

- [ ] Public repository.
- [ ] README covering setup and graph structure.
- [ ] Important Cypher/algorithm implementations.
- [ ] Video of the functioning product.
- [ ] Hosted app or complete local reproduction instructions.
- [ ] Track selection.
- [ ] Disclosure of coding-assistant use.

Participants must understand and explain their implementation. Entirely generated
work without meaningful contribution, verification, or understanding risks rejection.
Creators retain their IP. Respectful conduct is required; harassment, discrimination,
plagiarism, judging manipulation, and rule breaches can disqualify entries.
Organizer/community announcements can amend event information.

Source: [complete official rules](https://www.wemakedevs.org/hackathons/falkordb/rules).
The rules also incorporate the [WeMakeDevs Code of Conduct](https://www.wemakedevs.org/coc).

## Official resources to keep open

The [event resource directory](https://www.wemakedevs.org/hackathons/falkordb/resources)
collects these references:

- [FalkorDB quickstart](https://docs.falkordb.com/getting-started).
- [Documentation](https://docs.falkordb.com/).
- [Database repository](https://github.com/FalkorDB/FalkorDB).
- [GraphRAG SDK](https://github.com/FalkorDB/GraphRAG-SDK).
- [Docker setup](https://docs.falkordb.com/operations/docker).
- [Cloud console](https://app.falkordb.cloud/).
- [Graph browser](https://docs.falkordb.com/browser).
- [Cypher](https://docs.falkordb.com/cypher).
- [Client libraries](https://docs.falkordb.com/clients).
- [Graph algorithms](https://docs.falkordb.com/algorithms).
- Its integrations, community examples, and graph-agent walkthrough links.
- Its curated videos on Cypher, algorithms, Graph/RAG, and Cloud setup.
- [FalkorDB Discord](https://discord.com/invite/Y2mMT9VdMy), for support and teammates.

Some linked videos did not load in the research tool; their listings were visible
on the resource page. I have not watched or independently checked their contents.

## Information that is not established

The four public pages reviewed do not state numeric scoring weights, an official
memory benchmark, a minimum benchmark score, named judges, video duration limits,
or detailed submission-form fields. The registration panel returned a loading
placeholder to the research tool; account-specific instructions remain unverified.
Check that panel and organizer announcements before submitting.

LangChain, LangGraph, GraphRAG SDK, embeddings, and multiple model providers are
not listed as compulsory tools. Our recommended stack is a design decision.

## Continuity's proposed submission boundary

Keep a Planner and Helper in one local Python process, with LangChain, a small
explicit LangGraph workflow, the FalkorDB client, and a minimal interface. A
separate FastAPI service is optional and is not currently implemented.

The project focuses on resuming valid work: sourced decisions and correction
history, declared decision-to-result dependencies, review of affected completed
work, prerequisites, one approved procedure, prior attempts, and durable handoffs.
Unrelated changes must not invalidate a handoff; changed inputs must be checked
again when completing work. These are application design choices, not extra
organizer requirements or a claim of a new memory algorithm.

The submission-critical evaluation is a small deterministic correctness suite and
several real-model cases. Broad memory platforms, automated lease reassignment,
multi-process workers, full benchmark ingestion, and load campaigns are deferred.
Small race checks do not justify a high-throughput claim.

FalkorDBSaver is behind a pinned-version save/restart/restore/isolation smoke-test
gate. If incompatible, demonstrate durable business handoffs resumed in a fresh
conversation and disclose that arbitrary workflow checkpoint recovery is deferred.
Actual Gemini project quotas, installed package compatibility, local persistence,
and all implementation/verification statuses remain to be checked.

The substantive revision log is at the end of [PROJECT_PLAN.md](PROJECT_PLAN.md).
