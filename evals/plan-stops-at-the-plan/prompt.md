---
description: Asked to plan a change, the agent writes the plan in the template with assumptions tied to tests and stops for approval instead of starting the work.
tags: [planning]
max_turns: 8
allowed_tools: [Skill, Write]
---
Plan the addition of per-client rate limiting to a small HTTP API service (one service, a Redis instance is available, limits are per API key, the client library must not change). Write the plan as a markdown document and then stop; do not start implementing anything.
