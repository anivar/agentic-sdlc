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

## Answering findings

Each finding on your own work gets exactly one answer (REVIEW-12).

| Answer | When | It carries |
|---|---|---|
| Fixed | The finding is right and the change is made | The change and where it is |
| Accepted | The finding is right, and the author may not edit yet (a draft awaiting approval, a file outside the change) | The exact change proposed |
| Refuted | The reviewer is wrong, and the evidence was within the reviewer's reach | The file and symbol at the sha, or the decision as the document records it |
| To the decider | The reviewer is wrong only in the light of something it could not read: a team convention, a decision taken in a meeting | The fact, and the choice: keep the text, or add the fact to the document |
| Declined | The reviewer labelled it `nitpick`, or it is a cosmetic bot suggestion (REVIEW-5) | One line |

- "I meant it that way" is not evidence. Without evidence the reviewer could read, the answer is
  Fixed, Accepted or To the decider.
- A reader who could not follow the document found a gap in the document. Fix it; do not refute it.
- The label and its decoration are the reviewer's. If a blocking finding is wrong, refute it and
  say why; do not relabel it.
- Add text for the human who will read the document. Text that only a zero-context reviewer needs
  goes to the decider instead.
- Every answer, refutations included, goes in front of the decider: a reviewer's point stays open
  until the decider has seen the answer (VOICE-9). A thread given to the decider stays unresolved
  until the decider answers; then resolve it as REVIEW-5 says.

Across rounds:

- Keep the answers where the next round can read them: the change's threads, or the summary the
  decider saw.
- A refutation the decider saw and did not overrule, or a finding the decider accepted as a known
  risk, stays settled. When a new reader raises it again at the same place (the same heading or
  the same line of code, wherever later edits moved it), point to the earlier answer and do not
  re-open it.
- A fixed finding raised again at the same place re-opens: the fix did not hold, or a later edit
  undid it.
- A reviewer that failed, timed out or returned nothing is reported as not run. It is never
  counted as a reviewer with no findings.

## Bot threads

A cosmetic suggestion from a bot: one line, verdict only ("Not changing: the cast is explicit on
purpose"). A real defect from a bot: treat as a lead (EVID-3), open the line, then a normal
finding. On your own change, resolve every bot thread after answering it. On another author's
change, reply and leave it open for the author.
