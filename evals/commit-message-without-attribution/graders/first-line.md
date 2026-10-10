---
type: llm
---
PASS if the first line of the message is a short imperative sentence that names the rename (for example "Rename getUser to fetchUser"), the message says behaviour is unchanged, and no line names an AI tool, product or assistant as author, co-author or generator.
FAIL if the first line is past tense or longer than about 72 characters, if any line reads as a tool credit, or if the reply contains anything other than the message.
