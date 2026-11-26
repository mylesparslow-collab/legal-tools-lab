"""Block-billing detection: count the tasks a narrative appears to describe.

The heuristic, in order:

1. Strong separators are a semicolon, a full stop followed by a space, and a
   line break. The text after a strong separator starts a new task only if it
   begins with a task word from LEXICON (draft, review, telephone conference
   with, ...). Otherwise it is treated as a continuation of the task before
   it. That keeps "Draft motion to compel; sections on relevance;
   proportionality" as one task.

2. Weak separators are a comma, " and ", " & " and " then ". The text after a
   weak separator starts a new task only if all three hold:
     a. it begins with a task word,
     b. the task before it already has an object ("Review and revise the
        order" does not split, because "Review" has no object of its own),
     c. its task word is a different kind of activity from the task before
        it, or both are writing, preparing or filing words with their own
        objects ("Draft the motion and draft the proposed order" is two
        tasks). Two reviewing, researching, attending or travelling words
        in a row stay one task, and so does a conversation followed by
        "discuss", "advise" or "negotiate" ("Meet with client and discuss
        settlement"). A second call, email or briefing is a second task.
   A task word followed by a document noun ("research memo", "meeting notes")
   is read as a noun in a list, not a new task.

3. Nothing after a colon is split on weak separators. A colon introduces a
   list ("Review production: invoices, purchase orders and shipping records").

The count is a prompt for a person. The tool never rewrites a narrative and
never guesses how time divides between tasks.
"""

import re

LEXICON = {
    "communicate": [
        "telephone conference", "telephone call", "teleconference", "conference call", "video conference", "videoconference",
        "phone call", "call with", "call to", "call from", "call", "called", "phone", "phoned",
        "confer with", "conferred with", "conferring with", "conference with", "office conference", "internal conference",
        "meet with", "met with", "meeting with",
        "email to", "email from", "email", "emailed", "emails to", "emails with", "email exchange", "e-mail to", "e-mail from",
        "exchange emails", "exchanged emails", "exchange correspondence",
        "correspond with", "corresponded with", "correspondence with", "correspondence to", "correspondence from",
        "letter to", "write to", "wrote to", "writing to",
        "discuss", "discussed", "discussing", "respond to", "responded to", "reply to", "replied to",
        "speak with", "spoke with", "speaking with", "speak to", "spoke to", "talk with", "talked with", "talk to", "talked to",
        "brief the", "briefed the", "brief client", "briefed client", "advise", "advised", "notify", "notified",
        "report to", "reported to", "negotiate", "negotiated", "negotiating", "huddle with",
    ],
    "compose": [
        "draft", "drafted", "drafting", "revise", "revised", "revising", "edit", "edited", "editing",
        "finalize", "finalized", "finalizing", "redline", "redlined", "update", "updated", "updating",
        "write", "wrote", "outline", "outlined", "outlining", "mark up", "marked up",
    ],
    "prepare": ["prepare", "prepared", "preparing", "assemble", "assembled", "compile", "compiled"],
    "filing": ["file", "filed", "e-file", "e-filed", "efile", "efiled", "serve", "served", "lodge", "lodged", "submit", "submitted"],
    "review": [
        "review", "reviewed", "reviewing", "analyze", "analyzed", "analyzing", "analysis of", "examine", "examined",
        "read", "evaluate", "evaluated", "assess", "assessed", "summarize", "summarized",
        "cite-check", "cite-checked", "cite check", "proofread", "proof",
    ],
    "research": ["research", "researched", "researching", "legal research"],
    "attend": [
        "attend", "attended", "attending", "appear", "appeared", "appearance at", "participate in", "participated in",
        "defend", "defended", "take deposition", "took deposition", "second-chair", "second-chaired",
    ],
    "travel": ["travel", "traveled", "travelled", "traveling", "travelling", "return travel", "drive to", "drove to"],
    "other": [
        "attention to", "work on", "worked on", "organize", "organized", "organizing", "scan", "scanned", "scanning",
        "investigate", "investigated", "interview", "interviewed", "coordinate", "coordinated", "schedule", "scheduled",
        "supervise", "supervised", "calendar", "calendared",
    ],
}

# Two task words of the same kind joined by a comma or "and" are read as one
# task only for these kinds ("Meet with client and discuss settlement",
# "Review the complaint and analyze the claims"). For the others, a second
# task word with its own object is a second task ("Draft the motion and draft
# the proposed order").
MERGE_SAME_FAMILY = {"communicate", "review", "research", "attend", "travel"}
# Within communicating words, only these continue the conversation just named
# ("Call with opposing counsel and negotiate the protocol"). Another call,
# email or briefing is a separate communication ("Call with client and email
# to adjuster" is two tasks).
CONTINUES_A_CONVERSATION = {"discuss", "discussed", "discussing", "advise", "advised", "negotiate", "negotiated", "negotiating"}

_STARTS = sorted(
    ((phrase, family) for family, phrases in LEXICON.items() for phrase in phrases),
    key=lambda item: -len(item[0]),
)
_FILLERS = ("and ", "then ", "also ", "further ", "& ")
_STOP = {"for", "to", "with", "on", "re", "regarding", "the", "a", "an", "of", "in", "at", "and"}
NOUN_FOLLOWERS = {
    "memo",
    "memos",
    "memorandum",
    "memoranda",
    "notes",
    "log",
    "logs",
    "report",
    "reports",
    "records",
    "binder",
    "binders",
    "agenda",
    "minutes",
    "summary",
    "summaries",
    "plan",
    "files",
    "transcript",
    "transcripts",
    "recordings",
    "list",
    "lists",
    "exhibits",
    "outlines",
    "messages",
    "chains",
    "chain",
    "threads",
    "thread",
    "attachments",
    "correspondence",
}
_STRONG = re.compile(r"(;\s*|\.\s+|\n+)")
_WEAK = re.compile(r"(,\s+and\s+then\s+|,\s+and\s+|,\s+then\s+|,\s+|\s+and\s+then\s+|\s+and\s+|\s+&\s+|\s+then\s+)")
_COLON = re.compile(r":\s")


def _strip_fillers(text):
    lowered = text.strip().lower()
    changed = True
    while changed:
        changed = False
        for filler in _FILLERS:
            if lowered.startswith(filler):
                lowered = lowered[len(filler):].lstrip()
                changed = True
    return lowered


def lead_phrase(text, list_context=False):
    """Return (phrase, family) if the text begins with a task word, else None."""
    lowered = _strip_fillers(text)
    for phrase, family in _STARTS:
        if not lowered.startswith(phrase):
            continue
        rest = lowered[len(phrase):]
        if rest and (rest[0].isalnum() or rest[0] == "-"):
            continue
        if list_context:
            words = rest.split()
            if words and words[0].strip(".,;:()") in NOUN_FOLLOWERS:
                return None
        return phrase, family
    return None


def _has_object(task):
    lowered = _strip_fillers(task["text"])
    if task["lead"]:
        lowered = lowered[len(task["lead"]):]
    words = [w.strip(".,;:()") for w in lowered.split()]
    words = [w for w in words if w and w not in _STOP]
    needed = 1 if task["lead"] else 2
    return len(words) >= needed


def _new_task(text, lead):
    return {"text": text.strip(), "lead": lead[0] if lead else None, "family": lead[1] if lead else None}


def analyze(narrative):
    """Return {"task_count", "tasks", "notes"} for a narrative."""
    tasks = []
    notes = []
    parts = _STRONG.split(narrative.strip())
    # parts alternates text, separator, text, ...
    chunks = []
    for index in range(0, len(parts), 2):
        sep = parts[index - 1] if index > 0 else ""
        chunks.append((sep, parts[index]))
    for sep, chunk in chunks:
        if not chunk.strip():
            continue
        colon = _COLON.search(chunk)
        head = chunk[: colon.start()] if colon else chunk
        tail = chunk[colon.start():] if colon else ""
        pieces = _WEAK.split(head)
        first = pieces[0]
        lead = lead_phrase(first)
        if tasks and lead is None:
            tasks[-1]["text"] += sep + first
            current = tasks[-1]
            notes.append('"%s" does not begin with a task word; read as part of the task before it.' % first.strip())
        else:
            current = _new_task(first, lead)
            tasks.append(current)
            if len(tasks) > 1:
                notes.append('"%s" begins with the task word "%s" after a strong separator; counted as a new task.' % (first.strip(), lead[0]))
        for index in range(1, len(pieces), 2):
            weak_sep, piece = pieces[index], pieces[index + 1]
            lead2 = lead_phrase(piece, list_context=True)
            if lead2 is None:
                current["text"] += weak_sep + piece
            elif not _has_object(current):
                current["text"] += weak_sep + piece
                notes.append('"%s" shares its object with the words before it; not split.' % piece.strip())
            elif lead2[1] == current["family"] and lead2[1] in MERGE_SAME_FAMILY and (
                lead2[1] != "communicate" or lead2[0] in CONTINUES_A_CONVERSATION
            ):
                current["text"] += weak_sep + piece
                notes.append('"%s" is the same kind of activity as the task before it; not split.' % piece.strip())
            else:
                current = _new_task(piece, lead2)
                tasks.append(current)
                notes.append('"%s" begins with the task word "%s" and the task before it is complete; counted as a new task.' % (piece.strip(), lead2[0]))
        if tail:
            current["text"] += tail
            notes.append("Text after a colon is read as a list and is not split.")
    texts = []
    for task in tasks:
        text = task["text"].strip().rstrip(".;,").strip()
        lowered = text.lower()
        for filler in _FILLERS:
            if lowered.startswith(filler):
                text = text[len(filler):].lstrip()
                lowered = text.lower()
        texts.append(text)
    return {"task_count": len(texts), "tasks": texts, "notes": notes}


def count_tasks(narrative):
    return analyze(narrative)["task_count"]
