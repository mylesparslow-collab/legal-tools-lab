# Standard prompt

Give every tool under test the same prompt and the same document, with no other
context. Save what it returns as one entry in a run file (see `README.md`).
Record the wall-clock minutes from sending the prompt to having the output as
`tool_minutes`. If an attorney times the verification, record that as
`attorney_verification_minutes`.

`python3 -m harness prompt DOC_ID` prints the prompt followed by the document.

---PROMPT---
You are reviewing a California legal document for an attorney. Identify every
provision, or missing provision, that conflicts with a California or federal
statute or regulation. Do not report style points, business terms or drafting
preferences.

Return only JSON, in this form:

{
  "findings": [
    {
      "issue": "one or two sentences: what the problem is",
      "authority": "the statute or regulation, for example Civ. Code § 1950.7(c)",
      "quote": "the words of the document that show the problem, copied exactly, 20 to 400 characters, from a single paragraph",
      "severity": "high or medium"
    }
  ]
}

Rules:
- Copy each quote character for character from the document. Do not paraphrase,
  correct or shorten it except by replacing omitted words with [...].
- If the problem is that something is missing, quote the nearest related clause
  and say what is missing in "issue".
- Cite only authority you are confident exists and says what you claim.
- If you find nothing, return {"findings": []}.
