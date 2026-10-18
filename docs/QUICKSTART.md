# Talk to Continuity and check its memory

No new installation is needed in this workspace.

```powershell
.\docker.ps1 compose up -d --wait
.\ui.ps1
```

Open http://localhost:8501 and refresh if it was already open.

1. Enter a NEW project name, such as `memory_test_1`, and click **Open project**.
2. In **AI Assistant Chat**, send your own facts, for example:
   `My name is Jack and I own 2 restaurants.`
3. Expect a normal response and **Saved ... sourced memories**. Expand the
   memory/source panel. These are facts you supplied, not preloaded examples.
4. Click **New conversation**, select **Helper** under **Talk to**, and ask:
   `What is my name and how many restaurants do I own?`
5. Send: `Correction: I now own 3 restaurants.`
6. Start another conversation and ask the count again. Expect 3, with a source.
7. Refresh or restart Streamlit. The conversation selector and saved facts should
   remain. **Memory** shows the connected graph, current facts and earlier values.
8. Ask: `Help me plan a weekly budget for my restaurants.` If a task is suggested,
   click **Create this plan**, then **Get Step-by-Step Helper Guide**. Planner and
   Helper read the same current memory. Nothing is completed automatically.

Use your actual name and situation when testing for real. The text above is only
an example you can type; it is not loaded into your project by the app.

Use the task board to declare technical dependencies, confirm completed work,
and resolve reviews. Chat can discuss a decision, but the decision form makes
an actual technical change. Completion always needs your explicit report.

A new conversation keeps project memory. A new PROJECT starts with separate
memory. Switching back restores the earlier project's records.

If a provider fails, the router can try a configured standby within the request
budget. If all attempts fail, the UI reports failure; it never replaces them
with scripted answers. Retry the same message while budget remains; the sidebar
can start a new request after exhaustion. Free-provider availability can vary.
