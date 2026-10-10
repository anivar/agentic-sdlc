---
description: A review of an inline diff uses Conventional Comments, one finding per thread with file and line, and ends with a decision.
tags: [review]
max_turns: 8
allowed_tools: [Skill]
---
Review this change. Reply with the findings and a summary, nothing else.

```diff
--- a/src/pager.py
+++ b/src/pager.py
@@ -10,7 +10,9 @@ def page(items, size, number):
-    start = number * size
+    start = (number - 1) * size
     end = start + size
-    return items[start:end]
+    if start > len(items):
+        return []
+    return items[start:end + 1]
```

No test was changed in this diff.
