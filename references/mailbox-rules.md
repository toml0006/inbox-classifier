# Mailbox rules

Policy for the review and apply steps, and the source material for the wording
in `references/questions.json`. Edit both together when habits change.

This file ships as a template. Every `<...>` is a blank to fill in with the
user; until then, apply only the rules that have no blank in them.

## Every mailbox

- A message from a real person who asks a question is `action_required`, even
  when it is short or friendly.
- A one-time login code is `code_2fa` and is always archived. It expires in minutes.
- A sender name that does not match the brand it claims is possible phishing,
  whatever the model scored. Keep it in the inbox and say so. Never follow its
  links.
- Invoices, contracts and anything about getting paid are `action_required`.
- A bill stays in the inbox only when it is unpaid and not on autopay.
- These senders always stay in the inbox, whatever the message looks like:
  <for example a school, a family member, a manager>.

## Connector mailbox: <address>

Clients and projects that mean `action_required` or `waiting_on_other`, never
noise: <names>.

Category labels for `label_and_archive`. Read the ids with `list_labels`; a
category with no row here gets the day label only.

| Category | Label | Label id |
|---|---|---|
| `receipt_or_ticket` | <for example Receipts> | <Label_id> |
| `bill` (autopay or already paid) | <for example Money> | <Label_id> |

Optional labels for archived mail the user likes filed, such as newsletters or
tool notifications: <label name and id, or none>.

## Chrome mailbox: <address, or delete this section>

Chrome applies labels by name, so no ids are needed here.

- Receipts get the `<label>` label, then archive.
- Tickets, reservations and order pickups get the `<label>` label, then archive.
