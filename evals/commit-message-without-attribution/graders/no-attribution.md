---
type: regex
pattern: co-authored-by|generated (with|by)|assisted-by|🤖
flags: i
match: not_contains
target: last_message
arm: both
---
