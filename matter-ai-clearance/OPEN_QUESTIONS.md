# Open questions for the General Counsel and IT

Personal portfolio demo. Fictional data. Not legal advice. Not reviewed by an attorney.

Every rule in `data/policy.json` is a firm policy default that someone chose so the demo could run. None of them
states what the law requires. This file lists the real question behind each default. Where the question is legal,
it is marked **attorney decision**. The tool takes no position on any of them.

Each heading matches the `open_question` code on the policy rules and in the memo.

## Tool lanes

### OQ-01
Who signs off that a feature may receive a data class, and on what evidence? The lanes file is the only source the
engine trusts. Today it is filled in by hand. (IT and General Counsel)

### OQ-02
What contract wording is enough to record `used_for_training: no` for a feature? Does it need to cover prompts,
uploads, outputs, feedback and logs separately? The default treats `unknown` as not approved. (Attorney decision on
the contract reading; IT on vendor settings)

### OQ-24
When a restricted data class is present on a matter and a feature is not approved for it, the shipped default
(`block_feature`) turns the feature off for the whole matter. The opt-in (`exclude_class`) keeps the feature usable
for the matter's other material with a "keep it out" condition. The opt-in clears more features, and what it trades
away is the control itself: restricted material is then kept out only by each person remembering the condition,
with nothing in the software to stop a mistake. Is there any practice group or tool for which that trade is
acceptable, and who would approve it? Under the opt-in, should a hold on one data class hold the whole feature
(`hold_propagates`)? Under either setting, is a hold the right result when intake has not said whether the class is
present? (General Counsel and IT)

## Health-data lane

### OQ-03
When intake leaves a flag unknown, the default holds every feature. Who resolves the flag, and how fast? Is a full
hold the right default for every practice group? (General Counsel)

### OQ-04
**Attorney decision.** What must a business associate agreement cover before the firm records
`baa_covers_feature: true` for one feature of a tool? Is coverage decided per product, per feature or per data flow?
Who confirms it, and how is the confirmation kept? Does the answer change with the firm's own role for a given
client? The tool only stores true, false or unknown and treats anything but true as not covered.

### OQ-05
The default bars protected health information from any feature with connectors or web access on. Should specific
connectors be approvable one at a time? Who confirms the setting, and can users switch it back on? (IT, Privacy
Officer)

### OQ-06
**Attorney decision** on what retention is acceptable for protected health information in a tool. The default bars
`unknown` and `vendor_default` and accepts the rest. IT question: how is the retention setting verified?

### OQ-07
What record of use is wanted when protected health information goes into a lane feature: who, what, when, where it
is kept? The default only says "record each use in the matter log". (Privacy Officer)

## Protective orders

### OQ-08
**Attorney decision.** What a given protective order permits is a reading of that order. The tool does not read
orders. Intake enters four coded fields and optional quotes. Who is qualified to code them, and who checks?

### OQ-09
**Attorney decision.** Where an order says nothing about AI, may protected material go into any tool? Should the
firm seek a stipulation or amendment first? The default holds the material.

### OQ-10
**Attorney decision.** Is an AI vendor a "vendor" or other permitted recipient under a given order? Is a signed
undertaking from the vendor needed, possible, or enough? Does a tool hosted in the firm's own tenant count as
disclosure to anyone? The default treats only firm-hosted features as outside the vendor question.

### OQ-11
**Attorney decision.** How does an order's return-or-destroy term apply to prompts, outputs, logs and backups held
by a tool? The default accepts only zero or matter-controlled retention.

### OQ-12
**Attorney decision.** May material in an attorneys-eyes-only tier go into any tool at all? The default holds it.

### OQ-13
**Attorney decision.** Should sealed material ever go into a tool? The default says no, for every feature.

## Client terms

### OQ-14
If a client's guidelines or engagement letter are not on file, the default holds every feature. Is that right for
existing clients whose paper is old? Who chases the documents? (General Counsel, Knowledge Management)

### OQ-15
**Attorney decision.** How far does a client's prohibition reach? Does it cover research tools that receive no
client data, AI features built into ordinary software, and e-discovery review? The default applies it to every
feature on the matter. The classifier also cannot tell a prohibition on one task from a prohibition on everything.

### OQ-16
**Attorney decision.** What counts as the consent a client's terms ask for: who at the client may give it, in what
form, for which tools, for how long, and does it carry from one matter to the next? The tool only checks that a
consent record names the feature.

### OQ-17
**Attorney decision.** What notice satisfies a disclosure clause: timing, content, recipient, and whether one notice
covers later tools? Separately, whether the firm should give notice even where the terms are silent. The default
lists notice as a condition and reports whether intake shows a notice.

### OQ-18
Where terms limit use to approved tools, who keeps each client's list, and how are list changes picked up? (Knowledge
Management)

### OQ-19
Residency and retention clauses vary too much to parse. The default holds until an analyst records the limits. Who
is the analyst, and who reviews the entry? Are the lanes file's region and retention values reliable enough to
compare against? (Knowledge Management, IT)

### OQ-20
**Attorney decision.** How should AI-assisted work be billed under each client's terms, and what should the invoice
say? The default only routes the matter to billing review.

### OQ-21
What does "attorney review" mean in practice, and how is it evidenced? The default is one sentence. (General Counsel)

### OQ-22
**Attorney decision.** When a client's documents conflict, which controls? The tool does not apply an order of
precedence between an engagement letter and guidelines, or between older and newer documents. It flags the conflict.
Until someone resolves it, the stricter rule still fires. There is no screen yet for recording the resolution.

### OQ-23
**Attorney decision.** When a client's terms say nothing about AI, may the firm use AI on the matter without telling
the client? The default says the firm's lanes apply and nothing more. This is the most consequential default in the
file and the one most likely to be wrong for some matters.

## For IT

- The existing registry format has no field for agreement coverage per feature, connectors, web access, hosting or
  structured retention. Should the registry gain them, or should the lanes file stay separate?
- The registry has one entry per tool. Lanes need one entry per feature. Which system is the source of record?
- Nothing here enforces a decision. The memo and banner tell people what is allowed. Can the banner be shown in the
  document management system, and can any tool actually be switched off per matter?
- Who updates a policy rule when its review date passes? The tool flags late rules but still applies them.
