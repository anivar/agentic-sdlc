# Finding format

One finding per inline thread (REVIEW-2). Labels follow Conventional Comments:
`issue`, `suggestion`, `question`, `nitpick`, `thought`, `chore`, `praise`. Decorations in
parentheses when useful: `(blocking)`, `(non-blocking)`, `(security)`, `(test)`.

```
issue (blocking): the retry loop re-sends a non-idempotent request

src/client/send.py:142 at 3f9c2ab
Consequence: a timeout after the server accepted the write creates a duplicate order.
Rule: a retried request carries an idempotency key, or is not retried.
Required: send the key from `Order.id` on every attempt, or retry only on connection errors
before any byte was sent.
Suggestion: `with_idempotency(order.id)` already exists in `src/client/keys.py`.
```

Rules of the format:

- The first line is the label, the decoration and the defect in one sentence.
- `file:line` at the head sha of the change (REVIEW-1). One location per thread.
- Consequence states what happens to a user, a record or a system, not "this is wrong".
- Rule names the convention, the invariant or the registry id broken.
- Required states the behaviour, not the patch.
- At most one suggestion, and only when a concrete alternative exists.
- No hedges: "might", "could potentially", "I think" do not appear. If the reviewer is not sure,
  the label is `question` and the question is precise.

## The summary

Two to four lines (REVIEW-3). Shape:

```
Two issues block: the retry duplicate (send.py:142) and the missing test for the timeout path.
The migration is additive and reverses cleanly.
Request changes; the idempotency choice is the author's, the key source is open and needs
the payments owner by Friday.
```

The last line is the decision. An open point names who decides and by when.

## Bot threads

A cosmetic suggestion from a bot: one line, verdict only ("Not changing: the cast is explicit on
purpose"). A real defect from a bot: treat as a lead (EVID-3), open the line, then a normal
finding. On your own change, resolve every bot thread after answering it. On another author's
change, reply and leave it open for the author.
