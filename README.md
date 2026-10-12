# inbox-classifier

A skill for Claude that cleans up a Gmail inbox. You say "triage my inbox".
Claude fetches what arrived since the last run, has a small model sort every
message, archives the noise, and tells you what still needs you.

It never deletes anything, and one search undoes a whole run.

## What a run looks like

You ask. A minute later you get a short report. This one is made up, but it
has the shape of a real one.

```
Needs you (3)
- Dana Reyes wants sign-off on slides 3-8 of the rate card deck by Thursday
- Northside Dental sent an invoice for $240, due the 20th, not on autopay
- The school needs the field trip form back by Friday

Waiting on someone else (1)
- Priya has the contract draft and owes you comments

Possible phishing (1)
- "PayPal Support" from a gmail.com address, asking you to confirm a refund. Left in the inbox, links not opened.

Archived 41 under Triage/2026-10-12. 4 kept. Undo with label:triage-2026-10-12
```

## How it decides

Most email tools ask a chat model to read your mail and write an opinion. This
one asks a decisions model, TypeSafe Jev, five fixed questions about each
message. Jev answers with a choice and a probability and writes no prose, so
there is nothing to misread and nothing made up.

The first question puts the message in one of ten categories. A table in
`scripts/classify.py` turns the category into an action.

| Category | What happens |
|---|---|
| Someone needs something from you | stays in the inbox |
| You are waiting on someone else | stays |
| School | stays |
| Security alert | stays |
| Bill | stays, unless it is on autopay or already paid |
| Receipt, ticket or reservation | labelled, then archived |
| Login code | archived |
| Newsletter or digest | archived |
| Notification from a tool | archived |
| Marketing | archived |

The other four questions catch the mistakes a category alone would make. A
message stays in the inbox, with a note saying why, when any of these is true.

- It looks like phishing.
- A person is waiting for a reply, whatever the category says.
- The model was less than 70% sure of the category.
- A newsletter, notification or receipt carries a deadline in the next few days.

Claude reads every flagged message before anything moves and can overrule the
model. It also applies your own rules, such as "mail from my kid's school
always stays".

## Undo

Before a message leaves the inbox it gets a label named for the day, such as
`Triage/2026-10-12`. To put a run back, search Gmail for
`label:triage-2026-10-12`, select everything, and choose Move to Inbox.

## What you need

- Claude Code, or another Claude app that runs skills and can run `python3`
- `python3` and `jq`
- An OpenRouter account and key. Create one at https://openrouter.ai/keys
- The Gmail connector, signed in to the mailbox you want triaged
- Optionally Claude in Chrome, to triage a second Gmail account that has no connector

## Install

### Have your agent do it

Paste this into Claude Code. It installs the skill, checks each requirement,
and sets up your rules with you. It does not touch your mail.

```text
Install the inbox-classifier skill from https://github.com/toml0006/inbox-classifier and set it up with me.

1. Clone the repository into ~/.claude/skills/inbox-classifier. If you are not Claude Code, use your own skills directory. If that folder already exists, stop and tell me instead of overwriting it.
2. Check that python3 and jq are installed. Tell me how to install whichever is missing.
3. Check whether OPENROUTER_API_KEY is set, without printing it. If it is not, tell me to create a key at https://openrouter.ai/keys and export it in my shell profile, then wait for me. Do not ask me to paste the key into this chat.
4. Run `python3 ~/.claude/skills/inbox-classifier/scripts/classify.py --selftest`. It sends two made-up messages to the model, costs a fraction of a cent, and must end with "selftest ok". If it fails, show me the error and stop.
5. Check that you have the Gmail tools search_threads, list_labels, create_label, label_thread and unlabel_thread. If you do not, tell me to connect Gmail and stop.
6. Read SKILL.md in the skill folder, then do its "Before the first run" section with me. Ask me which senders must always stay in my inbox, which clients or projects are never noise, and which labels I file receipts and paid bills under. Look up the label ids with list_labels, and write my answers into references/mailbox-rules.md. Reword the first instruction in references/questions.json so it describes me.
7. Do not fetch, label or archive any of my mail during setup.

Finish with a short summary of what works, what is still missing, and the sentence I should say to run my first triage.
```

### Or by hand

```bash
git clone https://github.com/toml0006/inbox-classifier ~/.claude/skills/inbox-classifier
export OPENROUTER_API_KEY=...   # put this line in your shell profile
python3 ~/.claude/skills/inbox-classifier/scripts/classify.py --selftest
```

The last command should end with `selftest ok`. Then open
`references/mailbox-rules.md` and replace each `<...>` with your own senders,
clients and labels. Restart Claude so it picks up the skill and the key.

Apps that install skills from a file can use `inbox-classifier.skill` from the
[releases page](https://github.com/toml0006/inbox-classifier/releases).

## Using it

Say any of these.

- "Triage my inbox."
- "What needs a reply in my email?" Claude reports and archives nothing.
- "Clean up my inbox since Monday."

The first run asks how far back to go. Later runs start from the newest
`Triage/` label.

## Making it yours

Two files hold everything personal, and both are meant to be edited.

`references/mailbox-rules.md` holds your policy. It lists who always stays,
which clients matter, and which label a receipt gets.

`references/questions.json` holds the five questions the model answers. The
first one describes whose inbox this is. If you run a business, have kids in
school, or get a lot of one kind of mail, say so there. You can rename
categories or add one. A new category needs a line in `ACTION_BY_CATEGORY` in
the script, or its mail stays in the inbox.

## What leaves your machine

For each message the script sends the sender, subject, date, existing labels
and up to 800 characters of the body to OpenRouter, which passes them to the
model provider. It sends nothing else. It reads your key from the environment
and never prints it.

If your mail is covered by a confidentiality agreement or an employer policy,
check that this is allowed before you run it.

## Cost

About $0.00004 per message. Two hundred messages cost under a cent and take a
few seconds.

## Limits

- Gmail only.
- The model sees one message at a time. It does not know what you promised
  someone last week, which is why Claude reviews the flagged ones.
- The Chrome path for a second account clicks through Gmail's web page. Google
  changes that page without notice, so expect it to break now and then. The
  connector path does not have this problem.
- This started as one person's setup. The classify step is tested. The full
  flow has only run on its author's two mailboxes, before the instructions
  were rewritten for general use.

## Files

```
SKILL.md                     the steps Claude follows
scripts/classify.py          calls the model and turns answers into actions
references/questions.json    the five questions
references/mailbox-rules.md  your rules and label ids, shipped as a template
references/gmail-web.md      how to drive Gmail in Chrome for a second account
```
