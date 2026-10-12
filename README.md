# inbox-classifier

A Claude skill that triages a Gmail inbox. Every message is classified by the
TypeSafe Jev decisions model through OpenRouter, a small script turns each
verdict into keep, label or archive, and Claude reviews the uncertain ones
before anything moves.

Nothing is deleted. Everything archived gets a `Triage/YYYY-MM-DD` label first,
so a whole run can be undone by searching `label:triage-YYYY-MM-DD` and moving
the results back to the inbox.

## What you need

- Claude Code, or another Claude app that runs skills and can run `python3`
- `python3` and `jq`
- An [OpenRouter](https://openrouter.ai) key exported as `OPENROUTER_API_KEY`
- The Gmail connector, signed in to the mailbox you want triaged
- Optional: Claude in Chrome, for a second Gmail account with no connector

## Install

```bash
git clone https://github.com/toml0006/inbox-classifier ~/.claude/skills/inbox-classifier
python3 ~/.claude/skills/inbox-classifier/scripts/classify.py --selftest
```

The second command sends two made-up messages to the model and ends with
`selftest ok`. It costs a fraction of a cent.

There is also a packaged `inbox-classifier.skill` on the
[releases page](https://github.com/toml0006/inbox-classifier/releases) for apps
that install skills from a file.

## Use

Ask Claude to "triage my inbox", or ask what needs a reply. On the first run it
walks you through two files that ship as templates:

- `references/mailbox-rules.md`: senders that always stay, clients and projects
  that are never noise, and the labels you file into
- `references/questions.json`: the questions the model answers about each
  message. The first one describes whose inbox it is, so reword it for you

## What leaves your machine

For each message: the sender, subject, date, existing labels and the first few
hundred characters of the body go to OpenRouter and on to the model provider.
The script sends nothing else, and it never prints your key.

## Cost

About $0.00004 per message. Two hundred messages cost under a cent.

## Layout

```
SKILL.md                     the workflow Claude follows
scripts/classify.py          calls the model, maps verdicts to actions
references/questions.json    the five questions
references/mailbox-rules.md  your rules and label ids (template)
references/gmail-web.md      driving Gmail in Chrome, for a second account
```

The Chrome path depends on Gmail's page structure, which changes without
notice. The connector path does not.
