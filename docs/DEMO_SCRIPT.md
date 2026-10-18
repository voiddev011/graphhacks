# Record a short, honest demo

Explain: "Continuity lets several agent roles use the same changing, sourced
memory. It remembers between conversations and shows the evidence."

1. Show an empty NEW profile/project in the local Streamlit app.
2. Type a fictional example yourself: "My name is Jack and I own 2 restaurants."
   Say explicitly that this is demo input, not preloaded database content.
3. Open the memory/source panel and Memory page. Show current facts and the
   connected graph. Explain that the original user message backs each memory.
4. Click New conversation, switch to Helper and ask for your name and restaurant
   count. Explain that the new thread has no earlier chat turns, but reads the
   same persistent graph facts.
5. Correct the count to 3. Refresh. Show 3 as current and 2 in correction history.
6. Switch to Planner and ask for a weekly-budget task. Approve Create this plan.
   Open Helper steps and show its saved evidence. Explain that both agents share
   current memory, but neither has performed the actual work.
7. Optionally show an explicit routine and a user-reported past event; their
   memory types appear in Memory. Show another project is empty, then switch back.
8. Show the final test report and explain the actual limits: local prototype,
   no global leaderboard score, provider availability varies, no production
   authentication or large-scale throughput proof.

Mention Python, LangGraph, LangChain, Gemini/OpenRouter and FalkorDB. The graph
stores relationships, versions and sources and supplies the agents' context;
it is not merely a visualization beside the app.

Use the test commands yourself before recording. Do not expose .env or API keys.
The app is local. For an undeployed submission, include setup instructions and
the recorded working demo as requested by the event FAQ. Nothing is automatically
published, submitted or pushed by this project.
