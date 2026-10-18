"""Model doubles for automated tests only."""


class DemoModel:
    def generate(self, role, context):
        if role == "planner":
            return {"task_id": context["eligible"][0], "objective": "Resume: " + context["tasks"][0]["title"]}
        return {"summary": "TEST draft: " + context["task"]["title"],
                "steps": ["Read the cited decisions.", "Perform and check the work, then report the actual outcome."]}
