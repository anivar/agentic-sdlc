# Glossary format

```markdown
# <Context name>

<One or two sentences on what this context is and why it exists.>

## Language

| Term | Is | Avoid | Calibration |
|---|---|---|---|
| Order | A customer's request to buy, from placement to fulfilment. | purchase, transaction | Verified in `src/ordering/` |
| Invoice | A request for payment sent after delivery. | bill, payment request | Verified |
| Customer | A person or organisation that places orders. | client, buyer, account | unverified |
```

## Rules

- Be opinionated: one term per concept, the others under "avoid".
- Define what the thing is, in one or two sentences, never what it does or how it is built.
- Only terms specific to this context. General programming concepts do not belong even when the
  project uses them everywhere.
- Group under subheadings when natural clusters emerge; a flat table is fine for one area.
- Calibration is written on every row: where the definition was checked, or "unverified".

## Single and multiple contexts

Most repositories have one context: one `GLOSSARY.md` at the root. A repository with several
contexts carries `GLOSSARY-MAP.md` at the root:

```markdown
# Glossary map

| Context | Glossary | Purpose |
|---|---|---|
| Ordering | ./src/ordering/GLOSSARY.md | receives and tracks customer orders |
| Billing | ./src/billing/GLOSSARY.md | generates invoices and takes payment |

## Relationships

| From | To | How |
|---|---|---|
| Ordering | Billing | `OrderPlaced` events; shared `CustomerId` and `Money` types |
```

If `GLOSSARY-MAP.md` exists, read it to find the contexts. If only a root glossary exists, there
is one context. If neither exists, create the root glossary when the first term is resolved.
