# Corrections to the research report, Tool 8

The Tool 8 section of the research report was checked against primary text on 2026-11-25. Sources read: eCFR (49 CFR Parts 661 and 663, 2 CFR Part 184), the Federal Register (81 FR 60278), FTA's Buy America page, California Legislative Information (Pub. Contract Code 3500-3505), and 49 U.S.C. 5323(j) on Cornell LII (the uscode.house.gov link did not load, so the statute was read on a secondary host).

I am not an attorney. These are reading notes for a lawyer to confirm, not legal conclusions.

## What the report got wrong

1. **The 70% figure is not in 49 CFR 661.11.** The report cites 661.11 for "> 70% domestic component cost". The regulation on eCFR still says "more than 60 percent" in 661.11(a), (g) and (l). The 70% figure (FY2020 on; 65% for FY2018-19) is in the statute, 49 U.S.C. 5323(j)(2)(C)(i). FTA's 2016 policy notice (81 FR 60278) applies the same higher percentage to the subcomponent test in 661.11(g). The number is right; the citation and the fact that the regulation is stale were missed.

2. **"If foreign, 0% counts" is wrong for US-made components.** The report says a component that fails the subcomponent test counts for nothing. Under 661.11(l), a component manufactured in the US with too few domestic subcomponents still counts its domestic subcomponents plus the cost of manufacturing the component. Zero applies to components manufactured abroad, and even then tariff-exempt re-exported US subcomponents count (661.11(i), (j)). On the sample bus this is the difference between 71.8% (pass) and 46.1% (fail).

3. **The BABA 55% test does not govern FTA-funded stations and charging depots.** The report assigns "fixed guideway, stations and charging infrastructure" to 2 CFR Part 184's 55% component-cost test. Part 184 does not apply to an existing Buy America preference that meets or exceeds BABA (2 CFR 184.2(a)), and FTA says Part 184 "largely does not affect FTA's existing standards for iron, steel, and manufactured products". For FTA-funded work, manufactured products must be 100% US under 49 CFR 661.5(d): all manufacturing processes in the US and every component US-manufactured. BABA's main addition for FTA projects is the construction materials requirement. The 55% test matters when the money comes from a program that uses Part 184's standard. The tool shows both tests side by side and applies the one that matches the funding source.

4. **The 55% test is not in 2 CFR 184.5.** It is in the definition of "Produced in the United States" in 184.3. Section 184.5 only says how to cost components.

5. **The construction materials list is in 184.3, and the report's list is incomplete.** Section 184.6 holds the manufacturing-process standard for each material. The list has eight items; the report left out plastic and polymer-based products and optical fiber.

6. **"100% U.S. melt-and-pour" is not the regulatory wording.** Part 184 says "all manufacturing processes, from the initial melting stage through the application of coatings". FTA's own steel rule (661.5(b)) says all manufacturing processes, with an exception for refinement of steel additives. Coating location matters under the BABA wording.

7. **Buy Clean California does not reach local transit districts.** The report has the tool checking Pub. Contract Code 3500 limits on "structural steel/glass/insulation". Section 3500 is only the short title. The Act applies to state agencies under the State Contract Act, the UC Regents and the CSU Trustees (3501(a)). BART, AC Transit, Caltrain and similar districts are not on that list. The eligible materials are carbon steel rebar, flat glass, insulation and structural steel (3501(c)); the report dropped rebar. The GWP limits are set by the Department of General Services, not by the statute. The tool keeps the check but leaves it off unless the awarding authority is one of the three, and it loads no limits because I did not read the DGS table.

## What the report left out

- **Frame and car shell steel credit.** For procurements averaging more than $300,000 per vehicle, US steel or iron in a non-US frame or car shell counts toward domestic content (49 U.S.C. 5323(j)(5)).
- **Final assembly labor is excluded** from component cost (5323(j)(4); 661.11(p)).
- **Resident inspector exceptions** in 49 CFR 663.37(c): 10 or fewer buses; 20 or fewer vehicles for rural areas or urbanized areas of 200,000 or fewer; unmodified standard-production vans.
- **Part 663 only covers rolling stock that carries passengers in revenue service** (663.3), and the FMVSS subpart does not apply to rail vehicles (663.43(b)).

## What checked out

- Rolling stock needs more than 70% domestic content for current deliveries, plus US final assembly.
- Pre-award and post-delivery audits are at 49 CFR 663.21-663.37.
- BABA is Pub. L. 117-58 and its guidance is 2 CFR Part 184.
- The Federal Register API URL in the report works and returns FTA Buy America notices (289 documents on 2026-11-25). It also returns unrelated FTA documents that mention the phrase, so results need filtering.

## Not verified

- The "80% federal grant match" figure and the client list in the report.
- "Phased DOT/FTA Federal Register EV-charger waivers". I did not find or read one. Whether an EV charger is a manufactured product, part of a larger end product, or traction power equipment under FTA's rules is a classification question the tool leaves to counsel.
- The DOT de minimis waiver (Aug. 16, 2023). I read only FTA's summary. Its scope and current status are unchecked, so the tool reports the numbers for information and never changes a result because of it.
- How FTA's Part 661 treats cement and aggregates.
