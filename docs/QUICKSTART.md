# Test Continuity live

Open **http://localhost:8501**. Start it again later with:

```powershell
.\docker.ps1 compose up -d --wait
.\ui.ps1
```

1. In **Workspace**, choose **Start a new task**.
2. Type a task you actually want help with. Nothing is filled in for you.
3. Click **Create plan**. Your text is saved as your task and sent to Gemini.
4. Click **Get Helper steps** to get live suggestions for that plan.
5. Refresh the page to see the saved task and draft again.

When you have performed and checked the work, report the actual outcome and
confirm it. The app records your report; it does not execute the task for you.

Use **Plan saved tasks** to continue ready work already in this project.
**Memory** shows only decisions, procedures and attempts you have saved.
Optional dependencies let you connect a new task to saved decisions and earlier work.

There are no preloaded tasks, example conversations or scripted-answer controls
in the live app. Test fixtures are kept separately under `tests/`.

The earlier Apollo sample records were cleared after a private local backup.
Use the project field to open your own project name; new projects start empty.

If a request times out, retry with unchanged inputs to retain its request ID.
Existing drafts display without another API call.
