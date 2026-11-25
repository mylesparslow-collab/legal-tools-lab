# AI Tool Registry (one page)

Organization: ____________________  Registry owner: ____________________  As of: __________

One row per AI tool, including pilots and tools people are using informally. If a cell cannot be filled in, write "unknown". An unknown is a finding, not a gap to hide.

| Tool and purpose | Status | Owner | Data boundary | OCG check | Golden-set score | SB 574 log | Last review | Open flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |

## What goes in each column

- **Tool and purpose.** The name people use for it and one sentence on what it is used for.
- **Status.** proposed, pilot, production, paused or retired.
- **Owner.** One named role that answers for the tool. A committee is not an owner.
- **Data boundary.** Where it runs, who runs the model, which kinds of data may go in (public, firm internal, client confidential, personal data, health information), what is retained and for how long, whether inputs are used for training, and which agreements cover it.
- **OCG check.** How the tool is stopped from being used on a matter whose client's outside counsel guidelines prohibit or restrict AI: an automated gate, a manual lookup, or none. Give the date the check was last confirmed to work.
- **Golden-set score.** The tool's latest result on a fixed set of test documents with known answers: recall on high-severity issues, quote grounding, pass or fail against the marks you set, and the date. `../eval_harness` produces these numbers.
- **SB 574 log.** Whether the tool's output can reach a court filing and, if so, where the record is kept showing that an attorney read the output and verified each citation. See the note below.
- **Last review.** Date the row was last checked against reality.
- **Open flags.** Anything unresolved. `registry.py check` generates the standard ones.

## Note on SB 574

SB 574 adds Bus. & Prof. Code § 6068.1 and amends Code Civ. Proc. § 128.7, operative January 1, 2027. In short, an attorney who uses generative AI must keep confidential information out of public systems, must take reasonable steps to verify the accuracy of AI output and correct errors, and a filing certifies that its cited authorities were read and verified by the signer. The registry column records where the proof of that verification lives. The statute text was read by a separate build in this project (the SB 574 citation verifier); read the sections yourself before relying on this summary.

## Using the JSON version

Copy `registry.blank.json`, fill it in, then:

```
python3 registry.py check  my_registry.json
python3 registry.py render my_registry.json --out out/
```

`check` validates the file and lists flags: no owner, training use not ruled out, client data allowed with no OCG check, stale OCG check, in use with no golden-set score, score below the pass mark, possible court use with no verification log, overdue review, no human review step. `render` writes a landscape one-page HTML view, Markdown and CSV. `registry.example.json` is a filled-in example for a fictional firm.
