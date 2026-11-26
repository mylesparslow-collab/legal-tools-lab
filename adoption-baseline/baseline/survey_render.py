"""Render the survey definition as a static fillable form and as a printable page."""
import html
import json

DESIGN_NOTES = """## Design choices

- Short on purpose: 14 questions, mostly tick boxes, under five minutes. Longer surveys lose the
  people who use the tools least, which are the people this baseline most needs to hear from.
- No name or email is collected. Role, practice and office are asked so results can be grouped.
  Groups under five people are not reported.
- Two fixed recall windows (7 days and 30 days) are asked before the "typical week" question.
  A fixed window can be compared with the usage logs for the same week. "Typical" cannot.
- Wording is neutral. Questions do not assume the tools are useful or that people should be
  using them. "None", "Not applicable" and "Nothing limits my use" are always offered.
- The checking question asks what people do, not whether they follow a policy.
- "Another AI tool" is offered without comment so that use outside the approved tools can be
  seen in aggregate. Expect it to be under-reported.
- The blocker list is the hypothesis list from the plan. "Something else" and the free-text
  question are there for what the list misses. Option order should be shuffled if the survey
  platform supports it.
- Free-text answers are counted in the report but not reproduced.

## Known biases

- Self-report inflates use. People recall more use than the logs show, and some answer with what
  they think is expected. The report shows survey and log figures side by side for the same
  group and week so the size of the gap is visible.
- Non-response. People who use the tools are more likely to answer a survey about them. The
  response count is shown next to every survey figure. Survey figures describe respondents,
  not the firm.
- The survey is anonymous, so respondents are not matched to log records. The survey-versus-log
  gap compares two group rates. It cannot say who over- or under-reported.
- The logs only cover the approved tools. The survey is the only source for other tools, and
  it is a weak one.
- Role, practice and office are self-described and may differ from the roster.
"""


def render_markdown(defn):
    lines = ["# %s" % defn["title"], "", "Printable copy of `survey.json`, version %s. "
             "Personal portfolio demo with synthetic practice and office names." % defn["version"], "",
             defn["intro"], ""]
    for n, q in enumerate(defn["questions"], 1):
        note = "" if q.get("required") else " (optional)"
        lines.append("**%d. %s**%s" % (n, q["text"], note))
        lines.append("")
        if q["type"] == "text":
            lines += ["_Free text._", ""]
            continue
        box = "( )" if q["type"] == "single" else "[ ]"
        lines += ["- %s %s" % (box, o["label"]) for o in q["options"]]
        lines.append("")
    lines.append(DESIGN_NOTES)
    return "\n".join(lines)


def render_html(defn):
    e = html.escape
    parts = []
    for n, q in enumerate(defn["questions"], 1):
        qid = e(q["id"])
        req = ' data-required="1"' if q.get("required") else ""
        parts.append('<fieldset id="q-%s" data-qid="%s" data-type="%s"%s>' % (qid, qid, q["type"], req))
        parts.append("<legend>%d. %s%s</legend>" % (n, e(q["text"]), "" if q.get("required") else " (optional)"))
        if q["type"] == "text":
            parts.append('<textarea name="%s" rows="4" aria-label="%s"></textarea>' % (qid, e(q["text"])))
        else:
            kind = "radio" if q["type"] == "single" else "checkbox"
            for o in q["options"]:
                excl = ' data-exclusive="1"' if o.get("exclusive") else ""
                parts.append('<label><input type="%s" name="%s" value="%s"%s> %s</label>'
                             % (kind, qid, e(str(o["id"])), excl, e(o["label"])))
        parts.append('<p class="err" hidden>Please answer this question.</p></fieldset>')
    meta = json.dumps({"survey_id": defn["survey_id"], "version": defn["version"]})
    return PAGE % {"title": e(defn["title"]), "intro": e(defn["intro"]), "questions": "\n".join(parts),
                   "meta": meta}


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
:root { color-scheme: light dark; --bg: #ffffff; --text: #191919; --muted: #666666; --line: #d0d0d0; --accent: #1b64be; --err: #b3261e; }
@media (prefers-color-scheme: dark) { :root { --bg: #191919; --text: #efefef; --muted: #9c9c9c; --line: #444444; --accent: #6aabf1; --err: #f28b82; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 42rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; }
h1 { font-size: 1.5rem; line-height: 1.25; margin: 0 0 .5rem; }
.note { color: var(--muted); font-size: .9rem; }
fieldset { border: 1px solid var(--line); border-radius: 6px; margin: 1rem 0; padding: .75rem 1rem; }
fieldset.invalid { border-color: var(--err); }
legend { font-weight: 600; padding: 0 .25rem; }
label { display: block; padding: .3rem 0; }
input { accent-color: var(--accent); width: 1.1rem; height: 1.1rem; vertical-align: -2px; margin-right: .4rem; }
textarea { width: 100%%; font: inherit; color: inherit; background: transparent; border: 1px solid var(--line); border-radius: 4px; padding: .5rem; }
.err { color: var(--err); margin: .25rem 0 0; font-size: .9rem; }
button { font: inherit; padding: .6rem 1rem; border-radius: 6px; border: 1px solid var(--accent); background: var(--accent); color: var(--bg); cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
#out { width: 100%%; min-height: 12rem; font: 13px/1.4 ui-monospace, monospace; margin-top: .5rem; }
</style>
</head>
<body>
<main>
<h1>%(title)s</h1>
<p>%(intro)s</p>
<p class="note">Demo form with synthetic practice and office names. This page works offline and sends nothing anywhere. Saving produces a JSON file on your own device.</p>
<form id="survey" novalidate>
%(questions)s
<button type="submit">Save response as JSON</button>
<p id="status" role="status" class="note"></p>
</form>
<section id="result" hidden>
<h2>Your response</h2>
<p class="note">If the download did not start, copy the text below.</p>
<textarea id="out" readonly aria-label="Response as JSON"></textarea>
</section>
</main>
<script>
(function () {
  var META = %(meta)s;
  var form = document.getElementById('survey');
  form.addEventListener('change', function (ev) {
    var box = ev.target;
    if (box.type !== 'checkbox' || !box.checked) return;
    var others = form.querySelectorAll('input[type=checkbox][name="' + box.name + '"]');
    for (var i = 0; i < others.length; i++) {
      var o = others[i];
      if (o === box) continue;
      if (box.dataset.exclusive || o.dataset.exclusive) o.checked = false;
    }
  });
  function collect() {
    var answers = {}, firstBad = null;
    var sets = form.querySelectorAll('fieldset');
    for (var i = 0; i < sets.length; i++) {
      var fs = sets[i], qid = fs.dataset.qid, type = fs.dataset.type, value;
      if (type === 'text') {
        value = fs.querySelector('textarea').value.trim();
      } else if (type === 'single') {
        var r = fs.querySelector('input:checked');
        value = r ? r.value : null;
      } else {
        value = [];
        var cs = fs.querySelectorAll('input:checked');
        for (var j = 0; j < cs.length; j++) value.push(cs[j].value);
      }
      var empty = value === null || value === '' || (Array.isArray(value) && !value.length);
      var bad = !!fs.dataset.required && empty;
      fs.classList.toggle('invalid', bad);
      fs.querySelector('.err').hidden = !bad;
      if (bad && !firstBad) firstBad = fs;
      answers[qid] = value;
    }
    return { answers: answers, firstBad: firstBad };
  }
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var res = collect(), status = document.getElementById('status');
    if (res.firstBad) {
      status.textContent = 'Some questions still need an answer.';
      res.firstBad.scrollIntoView({ block: 'center' });
      var first = res.firstBad.querySelector('input, textarea');
      if (first) first.focus();
      return;
    }
    var payload = { survey_id: META.survey_id, version: META.version, answers: res.answers };
    var text = JSON.stringify(payload, null, 2);
    document.getElementById('out').value = text;
    document.getElementById('result').hidden = false;
    try {
      var blob = new Blob([text], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'response-' + Math.random().toString(36).slice(2, 8) + '.json';
      document.body.appendChild(a); a.click(); a.remove();
      status.textContent = 'Saved. Thank you.';
    } catch (e) {
      status.textContent = 'Could not start a download. Copy the text below instead.';
    }
  });
})();
</script>
</body>
</html>
"""
