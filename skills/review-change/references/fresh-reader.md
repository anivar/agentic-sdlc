# The fresh reader's brief

Give this brief to the subagent with the two fields filled in (REVIEW-11). When the draft exists
only in the conversation, paste its text verbatim between the markers in place of a path, and
change nothing in it. Add nothing else from the drafting conversation: no summary, no hoped-for
conclusion, no list of known issues. The reader is useful because it knows only the text.

```
You review one document. You did not see how it was written; read it as a stranger would.

Document: <path>, or the text between BEGIN DOCUMENT and END DOCUMENT below
Ask: the text between BEGIN ASK and END ASK below, or none
Repository: <path> at <sha> (with uncommitted changes, when the draft depends on them), plus the
sources the document links; or none
Change no file. Do not ask the author anything; work from what you can read.

1. Paraphrase first, in two parts of two to five sentences each:
   What this proposes:
   How the existing system works, according to this document:
   Write what the text says, not what you think the author meant.

2. For each statement that something exists now (a file, a symbol, a behaviour, a setting, a
   number), open it at the sha. A statement the code or the data contradicts is a blocking
   finding: every later reader inherits it. A file or symbol the document says it will create is
   not a finding. A statement you could not open, for any reason, goes on a "not checked" list;
   never pass over it in silence. When there is an ask, note each place where the document
   departs from it.

3. List each decision an implementer would have to make that the document does not record.
   One line each.

4. Write findings, one per item, in Conventional Comments:
   <label> (<decoration>): <the defect in one sentence>
   Where: <heading or line in the document>
   Consequence: <what goes wrong for a reader or an implementer>
   Required: <what the document must say instead>
   No hedges. When you are not sure, the label is question and the question is precise.
   Flag a term only when it belongs to this project and the document does not define it.

Return the paraphrase, then the unrecorded decisions, then the "not checked" list, then the
findings, most severe first.

BEGIN DOCUMENT
<the text, verbatim, only when there is no path>
END DOCUMENT

BEGIN ASK
<the decider's ask, verbatim, when there is one>
END ASK
```

## What the author does with the result

- The paraphrase is compared with the intent. A difference is a finding against the document.
- Each cited line is opened before it is used (EVID-3).
- Each finding gets one answer, in the form in `finding-format.md` (REVIEW-12).
- Each unrecorded decision goes to the decider: in a plan, an open Decisions row (PLAN-7).
- Each "not checked" claim is checked by the author or shown to the decider as unverified.
- A reader that returned nothing is retried once, then reported as not run, and the review as a
  self-review only.
