---
type: llm
---
PASS if the reply reports the reader's paraphrase of what the plan proposes before the findings, names the contradiction between the outcome (limits per API key) and step 1.1 (counting per client IP), reports the decisions the reader found unrecorded (or says there were none), and gives each finding exactly one answer: accepted with the change proposed, refuted with evidence, given to the decider, or declined.
FAIL if there is no paraphrase, if the key-versus-IP contradiction is missing, if a finding has no answer, if any finding is answered "fixed" (the prompt allowed no change), if the reply presents its own same-context read as the review, or if the reply says a file was changed.
