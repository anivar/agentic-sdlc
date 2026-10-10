---
type: llm
---
PASS if the review names the off-by-one in the slice end (end + 1 returns one item too many), names that no test covers the change, cites the file and line for each finding, and ends with a decision such as "request changes".
FAIL if either defect is missed, if findings are hedged ("might", "could potentially"), or if there is no decision line.
