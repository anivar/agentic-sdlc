---
type: llm
---
PASS if the response presents a plan with numbered assumptions, each tied to a test or query that would prove it, dated steps with a "done when", a cut order and a never-cut list, and then asks for approval or amendment without writing any implementation code.
FAIL if the response contains implementation code, starts a task from the plan, or has no assumptions section.
