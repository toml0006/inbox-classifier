---
name: inbox-classifier
description: Triage a Gmail inbox by classifying every message with the TypeSafe Jev decisions model (through OpenRouter), then keeping, labelling or archiving each one under a dated Triage label so the whole run can be undone. Use whenever the user asks to triage, clean up, sort, classify or catch up on their email or inbox, asks what needs action or a reply in their mail, or wants to know what is sitting in their inbox, even if they never say "triage". Works through the Gmail connector, and through Chrome for a Gmail account that has no connector.
compatibility: Needs python3, jq, an OPENROUTER_API_KEY in the environment, and the Gmail connector (MCP tools search_threads, list_labels, create_label, label_thread, unlabel_thread). Claude in Chrome is optional, for a second Gmail account.
---

# Inbox classifier

Reading two hundred subject lines is not a job for this conversation's context,
and it is not a job for a chat model either. Jev is a decisions model: it takes
one email as `state`, answers typed questions about it, and returns a choice
with calibrated probabilities. No prose, nothing to parse, nothing invented.

```
fetch -> inbox.json -> classify.py -> classified.json -> [your review] -> apply -> report
```

The model decides *what a message is*. The script decides *what to do about it*,
from a table you can read. You decide the ones the script flags. Nothing is ever
deleted, and everything archived first gets a `Triage/YYYY-MM-DD` label, so a
whole run is recoverable with the search `label:triage-YYYY-MM-DD`.

Paths below are relative to the directory this file is in; call it `$SKILL`.

## Before the first run

Do these once per machine, and again whenever the classify step fails.

1. Check the key and the model in one go. This sends two made-up messages and
   costs a fraction of a cent:

   ```bash
   python3 "$SKILL/scripts/classify.py" --selftest
   ```

   It ends with `selftest ok`. If the key is missing, the user creates one at
   openrouter.ai and exports `OPENROUTER_API_KEY` in the shell profile that
   starts Claude. Never ask them to paste the key into the conversation.

2. Tell the user, once, what leaves their machine: for every message the
   sender, subject, date, existing labels and the first few hundred characters
   of the body go to OpenRouter and on to the model provider. Nothing else does.

3. Open `references/mailbox-rules.md`. If it still contains `<...>`
   placeholders it has never been filled in. Ask the user for the few things it
   needs (senders that always stay, clients or projects that are never noise,
   which labels they file into), read the label ids with `list_labels`, and
   write the answers into the file. A run with an unfilled file still works: it
   applies only the day label and no category labels.

4. The first line of `references/questions.json` describes whose inbox this is.
   Reword it for the user; the model reads it on every message.

## 1. Fetch

The mailbox the Gmail connector is signed in to:

```
search_threads  query: "in:inbox after:<epoch seconds>"
```

The window runs from the last run to now. Find the last run with `list_labels`:
the newest `Triage/YYYY-MM-DD` label is its date. Starting from midnight of that
day is safe, because mail that run archived is no longer `in:inbox`. With no
such label this is the first run, so ask how far back to go.

```bash
date -v-30H +%s                 # macOS: 30 hours ago
date -d '30 hours ago' +%s      # Linux
```

A second Gmail account with no connector goes through Chrome instead. Read
`references/gmail-web.md` before touching it; it holds the scrape, the tick, the
guard and the traps. Skip it entirely for a user with one mailbox.

Write one JSON array per mailbox, into a scratch directory:

```json
[{"id": "1a0c4fa6c260dcce", "from": "Dana Reyes <dana@example.com>",
  "subject": "Pricing docs for review",
  "snippet": "Can you look at slides 3-8 of the rate card deck before Thursday?",
  "date": "2026-09-21"}]
```

`id` is the thread id for connector mail and the composite id from the
reference file for Chrome mail; the script echoes it back untouched. `snippet`
is optional, but it is what separates a real ask from a newsletter, so include
it whenever the fetch gives you one.

## 2. Classify

```bash
python3 "$SKILL/scripts/classify.py" inbox.json --out classified.json
```

One call per message, eight in parallel; ten messages take under a second. The
model defaults to `typesafe/jev-1.13` and can be changed with `--model` or
`OPENROUTER_MODEL`. Jev answers through
`https://openrouter.ai/api/alpha/decisions`, not `chat/completions`, which
refuses decisions models outright. That is why the script exists instead of a
generic chat call.

The five questions live in `references/questions.json` and are the user's to edit:

| Question | Type | What it gives back |
|---|---|---|
| `category` | choice | one of ten kinds of mail, plus a probability for each and a confidence |
| `needs_reply` | noul | 0 to 1, a person is waiting for words back |
| `phishing` | noul | 0 to 1, sender or pressure looks fake |
| `settled_money` | noul | 0 to 1, money already handled or on autopay |
| `urgency` | score | 0 to 3 against four written levels |

Score levels must stay *descriptive*. Jev evaluates each level on its own and
never sees its number, so "2 = worse than 1" teaches it nothing.

`ACTION_BY_CATEGORY` in the script maps category to one of three actions:
`keep_inbox`, `archive`, `label_and_archive`. Five overrides sit after it, and
each one leaves a flag: phishing, someone waiting on a reply, a bill that turns
out to be autopay, confidence under 0.70, and a real deadline on something that
looked archivable. Login codes are never rescued by urgency: they are urgent
and worthless.

## 3. Review before touching anything

Read results with `jq`, never by dumping the file into the conversation:

```bash
jq -r '.[] | select(.flags|length>0) | "\(.id) \(.action) \(.category) conf=\(.confidence) \(.flags|join("; "))"' classified.json
jq -r 'group_by(.action)[] | "\(.[0].action): \(length)"' classified.json
```

Overrule the model wherever you disagree, and apply the rules in
`references/mailbox-rules.md` on top of its verdicts. It sees one email; it does
not know what the user promised someone last week. Flagged rows are yours to
settle. Anything with a high `phishing` score stays in the inbox and gets named
in the report. A row flagged `no verdict` was never classified: leave it in the
inbox.

If the user asked only what is in their inbox, stop here and report. Archiving
is for when they asked for the inbox to be cleaned up.

## 4. Apply

Create the day's label first, then label, then remove `INBOX`. Never the other
way round: the label is the undo, and a thread that loses `INBOX` before it
gains the label is findable only by guessing.

```
create_label   name: "Triage/2026-09-22"     -> returns a label id
label_thread   threadId, labelIds: [<day label>, <category label if any>]
unlabel_thread threadId, labelIds: ["INBOX"]
```

`archive` rows get the day label only. `label_and_archive` rows also get the
category label that `references/mailbox-rules.md` names for them. `keep_inbox`
rows are not touched. If `label_thread` answers "The service is currently
unavailable", retry it in the next batch rather than skipping the thread.

Chrome mailbox: tick, label, run the guard, archive, exactly as
`references/gmail-web.md` says. Re-scan afterwards, because Gmail refills the
window with older mail after every archive.

## 5. Verify and report

Re-run the original search. Only keepers may remain. Then report:

- what needs the user to act, one line each, naming the sender and the real ask
- what is waiting on someone else
- what resolved itself since last time
- anything flagged as possible phishing
- the counts, and `label:triage-YYYY-MM-DD` as the undo

Short enough to read on a phone.

## Cost

About $0.00004 per message, all five questions included. Two hundred messages
cost under a cent and finish in a few seconds.
