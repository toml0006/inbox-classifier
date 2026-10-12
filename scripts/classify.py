#!/usr/bin/env python3
"""Classify inbox messages with TypeSafe Jev through OpenRouter.

Jev is a decisions model, not a chat model. It takes a state (one email) plus
typed questions and returns typed answers with calibrated probabilities. There
is no generated text to parse, so the category comes from the model and the
action comes from the table in ACTION_BY_CATEGORY below.

Input:  JSON array of messages (file or stdin). Per message:
          id       required, opaque, echoed back untouched
          from     sender name and/or address
          subject  subject line
          snippet  first ~300 chars of the body (optional, improves accuracy)
          date     any readable date (optional)
          labels   labels already on the message (optional)
Output: JSON array with id, category, action, confidence, the raw signals, and
        flags naming every reason a human should look.

Reads OPENROUTER_API_KEY. Never prints it.
"""
import argparse, json, os, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

API_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "typesafe/jev-1.13")
DEFAULT_QUESTIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "references", "questions.json")

ACTION_BY_CATEGORY = {
    "action_required": "keep_inbox",
    "waiting_on_other": "keep_inbox",
    "school": "keep_inbox",
    "security": "keep_inbox",
    "bill": "keep_inbox",
    "receipt_or_ticket": "label_and_archive",
    "code_2fa": "archive",
    "newsletter_or_digest": "archive",
    "tool_notification": "archive",
    "marketing": "archive",
}

# A question that is missing from questions.json simply stops contributing.
NOUL_THRESHOLD = 0.6

# Urgency can rescue a message from the archive pile, but only where being
# time-critical also means being worth reading. A login code is urgent and
# worthless; a sale that ends tonight is urgent to the sender only.
URGENCY_CAN_RESCUE = {"tool_notification", "newsletter_or_digest", "receipt_or_ticket"}
REVIEW_CONFIDENCE = 0.7


SELFTEST_MESSAGES = [
    {"id": "selftest-ask", "from": "Dana Reyes <dana@example.com>", "subject": "Pricing docs for review",
     "snippet": "Can you look at slides 3-8 of the rate card deck before Thursday? I need your sign-off to send it."},
    {"id": "selftest-promo", "from": "Acme Tools <news@acme.example>", "subject": "Our fall sale ends tonight",
     "snippet": "Don't miss out. Shop the biggest deals of the season before midnight."},
]


def render_state(msg):
    parts = []
    for label, key in (("From", "from"), ("Subject", "subject"), ("Date", "date")):
        if msg.get(key):
            parts.append("%s: %s" % (label, str(msg[key])[:200]))
    if msg.get("labels"):
        parts.append("Existing labels: %s" % ", ".join(str(x)[:40] for x in msg["labels"][:8]))
    if msg.get("snippet"):
        parts.append("Body: %s" % str(msg["snippet"])[:800])
    return "\n".join(parts)


def ask(key, model, questions, msg, timeout, attempts=4):
    body = json.dumps({"model": model, "state": render_state(msg), "questions": questions}).encode()
    last = None
    for attempt in range(attempts):
        req = urllib.request.Request(API_URL, data=body, headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "X-Title": "inbox-classifier",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code in (400, 401, 403, 404):
                raise SystemExit("OpenRouter rejected the request (HTTP %d): %s" % (exc.code, detail))
            last = "HTTP %d %s" % (exc.code, detail)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = repr(exc)
        time.sleep(2 ** attempt)
    return {"error": last}


def verdict(msg, payload):
    out = {"id": msg["id"], "category": None, "action": "keep_inbox",
           "confidence": 0.0, "flags": []}
    if payload.get("error") or "answers" not in payload:
        out["flags"].append("no verdict: %s" % (payload.get("error") or "missing answers"))
        out["category"] = "unclassified"
        return out, 0.0

    answers = payload["answers"]
    cat = answers.get("category", {})
    out["category"] = cat.get("choice") or "unclassified"
    out["confidence"] = round(float(cat.get("confidence") or 0.0), 3)
    probs = cat.get("probabilities") or {}
    out["runner_up"] = sorted(((v, k) for k, v in probs.items()), reverse=True)[1][1] if len(probs) > 1 else None

    for name in ("needs_reply", "phishing", "settled_money"):
        if name in answers:
            out[name] = round(float(answers[name].get("noul") or 0.0), 3)
    if "urgency" in answers:
        out["urgency"] = round(float(answers["urgency"].get("score") or 0.0), 2)

    out["action"] = ACTION_BY_CATEGORY.get(out["category"], "keep_inbox")

    # Deterministic overrides. Each one is a reason a human should look.
    if out.get("phishing", 0) >= NOUL_THRESHOLD:
        out["action"] = "keep_inbox"
        out["flags"].append("possible phishing (%.2f)" % out["phishing"])
    if out.get("needs_reply", 0) >= NOUL_THRESHOLD and out["action"] != "keep_inbox":
        out["action"] = "keep_inbox"
        out["flags"].append("someone waits on a reply (%.2f)" % out["needs_reply"])
    if out["category"] == "bill" and out.get("settled_money", 0) >= NOUL_THRESHOLD:
        out["action"] = "label_and_archive"
        out["flags"].append("bill is autopay or already paid")
    if out["confidence"] < REVIEW_CONFIDENCE:
        out["action"] = "keep_inbox"
        out["flags"].append("low confidence %.2f, runner up %s" % (out["confidence"], out.get("runner_up")))
    if (out.get("urgency", 0) >= 2 and out["action"] != "keep_inbox"
            and out["category"] in URGENCY_CAN_RESCUE):
        out["action"] = "keep_inbox"
        out["flags"].append("deadline within days (urgency %.1f)" % out["urgency"])

    return out, float((payload.get("usage") or {}).get("cost") or 0.0)


def main():
    ap = argparse.ArgumentParser(description="Classify inbox messages with Jev via OpenRouter.")
    ap.add_argument("input", nargs="?", default="-", help="JSON array file, or - for stdin")
    ap.add_argument("--out", help="write results here (default: stdout)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--questions", default=DEFAULT_QUESTIONS, help="question definitions JSON")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--show-state", action="store_true", help="print the first state and exit")
    ap.add_argument("--selftest", action="store_true",
                    help="classify two built-in messages to check the key, the model and the questions")
    args = ap.parse_args()

    if args.selftest:
        messages = SELFTEST_MESSAGES
    else:
        raw = sys.stdin.read() if args.input == "-" else open(args.input).read()
        messages = json.loads(raw)
    if isinstance(messages, dict):
        messages = messages.get("messages", [])
    if not messages:
        raise SystemExit("no messages in input")
    missing = [i for i, m in enumerate(messages) if not m.get("id")]
    if missing:
        raise SystemExit("messages at positions %s have no id" % missing[:5])

    questions = json.load(open(args.questions))

    if args.show_state:
        print(render_state(messages[0]))
        print("\n--- questions ---")
        print(json.dumps(questions, indent=2))
        return

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set. Create a key at openrouter.ai and "
                         "export it in the shell profile that starts Claude")

    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        payloads = list(pool.map(
            lambda m: ask(key, args.model, questions, m, args.timeout), messages))

    results, cost = [], 0.0
    for msg, payload in zip(messages, payloads):
        row, spent = verdict(msg, payload)
        results.append(row)
        cost += spent

    text = json.dumps(results, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    else:
        print(text)

    counts, cats = {}, {}
    for r in results:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    flagged = [r for r in results if r["flags"]]
    print("\n".join([
        "model=%s messages=%d in %.1fs cost=$%.5f" % (args.model, len(messages), time.time() - started, cost),
        "actions=" + ", ".join("%s:%d" % kv for kv in sorted(counts.items())),
        "categories=" + ", ".join("%s:%d" % kv for kv in sorted(cats.items(), key=lambda kv: -kv[1])),
        "flagged_for_review=%d" % len(flagged),
    ]), file=sys.stderr)

    if args.selftest:
        failed = [r for r in results if r["category"] == "unclassified"]
        if failed:
            raise SystemExit("selftest failed: %s" % "; ".join(failed[0]["flags"]))
        print("selftest ok", file=sys.stderr)


if __name__ == "__main__":
    main()
