# Graph Hacks: Learn and Build for Track 2

Updated: 16 October 2026  
Deadline: 18 October 2026, 11:59 PM IST  
Starting point: I know a little Python and am new to AI agents.

## 1. What the hackathon is about

Build an AI agent that uses connected information to make useful decisions.
FalkorDB must be the primary graph database and drive a central part of the product.

Track 2 is **Agent Memory and Coordination**. It focuses on agents that:

- Remember information across sessions.
- Update memories when information changes.
- Share information and hand tasks to each other.
- Keep different users' memories separate.
- Support simultaneous reads and writes.

The goal is to show how saved information improves the agent's decisions.
The event page does not publish scoring weights, so the feature priorities below
are recommendations, not an official judging checklist.

The submission and its main FalkorDB implementation must be new work completed
during the event. A live deployment is preferred; otherwise provide complete
local setup instructions and a working demo video.

[Official hackathon brief and requirements](https://www.wemakedevs.org/hackathons/falkordb)

## 2. What an AI agent is

A language model generates responses. An agent system gives the model tools
and a process for choosing and using them.

A **tool** is a function that your application can run.

Example:

1. You ask, "What should I work on next?"
2. The model requests `get_pending_tasks()`.
3. Python executes that function and queries FalkorDB.
4. The model receives the tasks and their dependencies.
5. It recommends a task or requests another tool.

The model requests an action; your application executes it.

**Memory** means storing information and retrieving it for future requests.
Saving a memory does not retrain the model.

## 3. Exactly which tools to use

**Recommended stack: Python + FalkorDB + LangChain + LangGraph + one LLM API.**

Include LangGraph in this learning plan: it will help organize the memory workflow
and coordinate agents. The hackathon rules require FalkorDB and allow you to choose
the other frameworks.

| Tool | What it does | How it helps this project |
|---|---|---|
| Python | Runs your application | Connects the model, tools, database, and interface |
| LLM API | Lets your application request responses from a model, such as Gemini | Interprets messages, requests tools, and generates answers |
| FalkorDB | Stores things and their relationships | Holds users, preferences, tasks, past attempts, and handoffs |
| Cypher | Reads and changes graph data | Retrieves memories and follows task dependencies |
| LangChain | Provides components for models and tools | Connects your model and exposes Python functions as tools |
| LangGraph | Defines steps, branches, and workflow state | Coordinates remembering, planning, helping, and recording results |
| FalkorDB GraphRAG SDK | Helps turn source material into a searchable knowledge graph | Useful if you import documents or notes |
| Streamlit | Builds a simple Python interface | Displays chat, memories, tasks, and supporting records |

Use direct FalkorDB queries for the first version. Add GraphRAG SDK if document
extraction and retrieval become part of the chosen project.

### FalkorDB and LangGraph have different graphs

- **FalkorDB:** a connection means something such as "Task A depends on Task B."
- **LangGraph:** a connection means something such as "After retrieving memories, run the Planner."

LangChain supplies model and tool components. LangGraph organizes their execution.
Python functions connect those steps to FalkorDB.

### What GraphRAG means

GraphRAG means retrieving connected information from a graph and supplying it to
the model before it answers. FalkorDB's SDK helps extract entities and relationships,
retrieve context, and trace it to sources. You can also retrieve graph context
using your own Cypher queries.

### Two kinds of saved information

- **Workflow state:** where the agent is in its current process. LangGraph can save this using a configured checkpointer.
- **Long-term project memory:** facts, decisions, attempts, and handoffs retrieved across sessions. Store these in FalkorDB.

Installing LangGraph does not automatically save your memories in FalkorDB.
You must implement the functions that write and retrieve them.

References: [LangChain](https://docs.langchain.com/oss/python/langchain/overview),
[LangGraph](https://docs.langchain.com/oss/python/langgraph/overview),
[memory concepts](https://docs.langchain.com/oss/python/concepts/memory),
[FalkorDB GraphRAG SDK](https://github.com/FalkorDB/GraphRAG-SDK).

## 4. Suggested project: Project Continuation Assistant

You return to a project after a break. The assistant remembers decisions,
unfinished work, previous failures, and your preferred way of working.
This is a suggested idea, not a confirmed final choice.

Build two roles:

- **Planner:** reads the project history and chooses a useful next task.
- **Helper:** reads the saved handoff, helps with the task, and records the outcome.

Both roles can use the same model with different instructions and tools.
Build one working agent before adding the second role.

### Three memory types

| Memory type | Simple meaning | Example |
|---|---|---|
| Semantic | Facts and preferences | "This project uses Streamlit." |
| Episodic | Past events and outcomes | "Yesterday's database connection attempt failed." |
| Procedural | Instructions to follow | "Check existing package versions before suggesting installation commands." |

### A small graph model

```text
User -> Project -> Task -> Prerequisite task
                    |
                    v
                Past attempt -> Outcome
                    |
                    v
                Source message
```

Useful question:

> Which unfinished task is available now, considering its prerequisites and what we already tried?

The relationships should affect the answer. For example, completing a prerequisite
should make a previously blocked task available.

## 5. Learn and build in this order

Use this rhythm: **learn one concept -> build one feature -> change one requirement yourself -> explain the result.**

### Step 1: Refresh the Python you need

Learn functions, dictionaries, lists, JSON, installing packages, and handling errors.

**Build:** functions that save and load a small task list.

**Ready when:** you can explain the input and output of each function.

Watch selected lessons from [Microsoft Python for Beginners](https://learn.microsoft.com/en-us/shows/intro-to-python-development/).
Build between lessons instead of waiting to finish the course.

### Step 2: Call a model and give it one tool

Learn API requests, messages, tool arguments, and tool results.

**Build:** an agent that calls a function to look up a task.
Inspect which tool it requested and what the function returned.

**Ready when:** you understand how the model's request becomes a Python function call.

Follow the basic-agent example in the [LangChain quickstart](https://docs.langchain.com/oss/python/langchain/quickstart).
For API basics, watch [What is an API?](https://www.youtube.com/watch?v=-0MmWEYR2a8).

### Step 3: Learn FalkorDB and basic Cypher

Learn nodes, relationships, properties, query parameters, and these commands:
`CREATE`, `MATCH`, `WHERE`, `RETURN`, `MERGE`, and `SET`.

**Build:** store projects and tasks. Find tasks with unfinished prerequisites.

**Ready when:** you can write a query that follows two relationships and explain its result.

Read [FalkorDB getting started](https://docs.falkordb.com/getting-started/).
Watch [Cypher Fundamentals](https://www.youtube.com/watch?v=K3nSwMheWng),
using the [FalkorDB reference](https://docs.falkordb.com/cypher/) to check supported syntax.

### Step 4: Organize the workflow with LangGraph

Learn state, nodes, edges, and conditional edges.
**State** is information passed between workflow steps.

**Build:** retrieve project context, run the agent, execute requested tools,
and record the results.

**Ready when:** you can explain which step runs next and why.

Watch **Nodes, Edges, Conditional Edges, and Memory** in the free
[LangGraph Essentials course](https://academy.langchain.com/courses/langgraph-essentials-python).
Adapt the [official LangGraph quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart).

### Step 5: Make memory work correctly

Save each memory with its user, project, source, timestamp, and current or historical status.
Start with explicit user statements. Validate the fields before writing them.

**Build:** save a preference, retrieve it in a fresh session, then correct it.
Keep the previous decision as history while using the latest decision in answers.

**Ready when:** memory survives application and database restarts, and a fresh
session recalls it without receiving the old conversation.

Read the [memory overview](https://docs.langchain.com/oss/python/concepts/memory).

### Step 6: Add coordination

Have the Planner save a handoff containing the task, objective, relevant memories,
and status. Have the Helper retrieve it and record its result.

**Build:** restart the application between planning and helping, then continue
from the saved handoff in FalkorDB.

**Ready when:** the Helper can continue the work using saved context.

## 6. Make the Track 2 demo convincing

Demonstrate these behaviors with visible results:

- **Recall:** a new session remembers an earlier decision.
- **Correction:** changing a decision changes future answers.
- **Coordination:** the Helper continues a handoff saved by the Planner.
- **Graph value:** dependencies and past attempts change the recommended action.
- **User separation:** a different user cannot retrieve those memories.
- **Persistence:** records survive application and database restarts.
- **Concurrent access:** a small simultaneous-read/write test checks for missing or duplicate records. Report its actual size and results.
- **Evidence:** display the memories, source records, and relationships used for the answer.

Compare a few requests with memory enabled and disabled to show its effect.
These are suggested demonstrations based on the brief, not official scoring rules.

### Choose storage that supports your demonstration

Use local FalkorDB with persistent storage configured, or suitable persistent hosting.
Cloud Free is useful for experiments but currently has 100 MB RAM and no persistence
or backups. It cannot provide the durable memory needed for a database-restart test.

References: [Cloud Free limits](https://docs.falkordb.com/cloud/free-tier),
[local Docker and persistence setup](https://docs.falkordb.com/operations/docker).

### Remaining event schedule

| Date | Target |
|---|---|
| October 16 | One agent with working graph memory |
| October 17 | Corrections, a second role, and saved handoffs |
| October 18 | Verify behavior, record the demo, finish setup instructions, and submit |

Start with a working core and add features as each part becomes reliable.
Prepare a README, reproducible setup, and a working demo video.
Check the official event page before submitting.

## 7. First task and tutoring instructions

**First goal:** save a project preference in FalkorDB, retrieve it through Python,
and have one agent use it in a fresh session.

Before that, check which Python basics I already understand.

My AI tutor should:

- Teach one step at a time in simple words.
- Give one main resource and one small task per lesson.
- Help me apply the concept even if the exercise stays separate from the final project.
- Review my result and ask one understanding question before moving on.
- Keep LangGraph in the learning plan and explain its purpose as we build.
- Use current official documentation and Windows-compatible commands.
- Explain changes and avoid generating the entire application at once.
- Record what was actually run and avoid claiming untested behavior works.

Current step: not recorded.  
What works: not recorded.  
Next action: check Python basics, then begin the first unfinished step.
