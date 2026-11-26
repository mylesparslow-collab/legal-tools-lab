"""Optional rewrite hook. Off by default. The demo never calls a model.

The desk drafts by retrieval and assembly: it copies previously approved text
and fills tagged placeholders. This file is the single place where a firm could
later plug in a model it has approved, to rewrite an assembled passage so that
it answers the question more directly.

Interface
---------
    rewrite(passage, requirement_text, context) -> str

    passage           the assembled text, placeholders already filled
    requirement_text  the RFP requirement being answered, exactly as written
    context           dict: agency, agency_type, question_type, answer_id

Return the text to use. Return the passage unchanged to do nothing.

Rules for anyone who implements this
------------------------------------
1. Whatever this function returns is checked by the same fact guard as any
   reused passage (desk/facts.py), after the rewrite, before it is shown. That
   is wired in desk/pipeline.py and covered by tests. Do not bypass it.
2. A rewritten passage is marked as rewritten in the draft and is never counted
   as approved text. A person must compare it with the source answer.
3. The guard catches only what it has patterns for. A model can state a new
   "fact" in a form the guard does not recognise. A rewrite therefore needs a
   human read against firm_facts.json and the source answer, every time.
4. Do not send client names, RFP text or library content to any service the
   firm has not approved for that material.
"""

ENABLED = False


def rewrite(passage, requirement_text, context):
    """No-op. Returns the passage unchanged."""
    return passage
