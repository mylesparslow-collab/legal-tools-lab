import json,re
from common import SUF
H='/home/claude/legal-tools-lab/billing-guideline-check/heldout/'
# Standard lists as they appear in every sample client file under data/guidelines/ (copied, not tuned).
V_ALWAYS=["attention to file","attention to matter","various tasks","work on case","work on matter"]
V_BARE=["draft correspondence","legal research","prepare for hearing","review documents","review file","telephone call","trial preparation","work on discovery"]
CLER=["scanning","scan documents","photocopying","bates stamping","organizing files","organize files","data entry","updating file index","saving documents to"]
TRAIN=["training","orientation","getting up to speed"]
CONFL=["conflicts check","conflict check","new matter intake"]
INVP=["prepare invoice","preparing invoice","prebill","pre-bill","billing inquiry","invoice backup","correct invoice"]
OH_CODES=["E103","E104","E105","E108"]
OH_PH=["postage","word processing","local telephone","office supplies","overtime","subscription"]
AI_TERMS=["generative ai","artificial intelligence","ai tool","ai-assisted","ai assisted","large language model","machine-generated"]
AI_TASKS=["summarize","summary of","summaries of","first-pass document review","first pass document review"]
def R(t,sev,params,quote,ref,status='confirmed',notes=None,docterms=None): return dict(t=t,sev=sev,params=params,quote=quote,ref=ref,status=status,notes=notes,docterms=docterms)
def vague(extra_always=(),extra_bare=()): return {"always_phrases":sorted(set(V_ALWAYS)|set(extra_always)),"bare_phrases":sorted(set(V_BARE)|set(extra_bare)),"min_words":3}
C={}
C['batch_a/harrowgate']=('HCE','Harrowgate Casualty Exchange',[
 R('unapproved_timekeeper','reject',{}, "Only people the claims examiner has cleared in writing for the claim.","Who may bill, sheet 1"),
 R('staffing_event_limit','reduce',{"max_attendees":1,"events":["deposition","mediation","arbitration","hearing"]},"One attorney paid per deposition, mediation, arbitration session or court hearing; a second needs the examiner's OK beforehand.","Depositions etc., sheet 1"),
 R('internal_conference_limit','reduce',{"max_hours_per_entry":"0.2"},"Capped at 0.2 hr per entry, per person.","In-firm discussions, sheet 1"),
 R('minimum_increment','reject',{"increment":"0.1"},"Six-minute units (0.1 hr); no quarter hours.","Time units, sheet 1"),
 R('rounding_pattern','review',{"block":"0.5","min_entries":6,"threshold_percent":80},"A timekeeper with 80% or more of entries (6 entries minimum) landing on the half hour or the hour gets audited.","Half-hour habits, sheet 1"),
 R('block_billing','reduce',{"max_tasks":1,"min_hours":0},"Each entry covers a single task with its own time; lumped entries are cut.","One entry, one task, sheet 1"),
 R('vague_description','reject',vague(extra_bare=["follow up"]),"Say what was done and to what; \"attention to file\", \"follow up\" and similar get zero.","Descriptions, sheet 1",docterms=["follow up"]),
 R('required_codes','reject',{"require_task":True,"require_activity":True,"require_expense":True},"Task code and activity code on fee lines, expense code on cost lines; all mandatory.","Codes, sheet 1"),
 R('daily_hour_cap','reduce',{"max_hours":9},"Over 9.0 hrs by one person in one day is not paid without a written reason.","Long days, sheet 1"),
 R('late_time','reject',{"max_age_days":75},"Work more than 75 days old at invoice date is not paid.","Stale time, sheet 1"),
 R('duplicate_entries','reject',{},"Same entry twice: the second one is struck.","Repeats, sheet 1"),
 R('rate_above_card','reduce',{},"The approved rate sheet for the claim is the ceiling.","Rates, sheet 2"),
 R('rate_increase_notice','reduce',{"notice_days":45},"45 days' written notice to the examiner before a new rate may be billed.","Rate changes, sheet 2"),
 R('non_billable_task','reject',{"categories":{"clerical":CLER+["secretarial","file-room"],"training":TRAIN+["onboarding"],"conflicts":CONFL+["conflicts clearance"],"invoice_prep":INVP}},"Secretarial and file-room work; training and onboarding; conflicts clearance; preparing or fixing bills.","Not billable, sheet 2",docterms=["secretarial","file-room","onboarding","conflicts clearance"]),
 R('research_approval','reduce',{"max_hours":"2.5"},"Up to 2.5 hrs per claim without asking; beyond that, examiner pre-approval.","Legal research, sheet 2"),
 R('travel_time','reduce',{"billable_percent":50,"requires_approval":False},"Paid at half the approved rate.","Travel, sheet 2"),
 R('expense_overhead','reject',{"codes":OH_CODES,"phrases":OH_PH},"Not reimbursed: postage, word processing, local telephone, office supplies.","Overhead, sheet 2"),
 R('expense_receipt_threshold','reject',{"threshold":"35.00","inclusive":True},"Required for any single charge of $35.00 or more.","Receipts, sheet 2"),
 R('expense_per_diem','reduce',{"caps":{"meal":"55.00","lodging":"190.00"}},"Meals max $55.00 per person per day; hotel max $190.00 per night.","Food and lodging, sheet 2"),
 R('expense_markup','reduce',{},"At cost, no uplift.","Third-party costs, sheet 2"),
],[
 ("Quarterly, or at $5,000 of unbilled time, whichever comes first.","invoice frequency; no rule type covers it"),
 ("No more than $0.10 a page.","a per-page copy rate; no rule type covers it. It must not be read as a per diem cap or a receipt threshold"),
 ("Status report to the examiner every 90 days.","a reporting duty; the 90 days must not be read as a late-time limit or a rate notice period"),
])
C['batch_a/marrowfen']=('MSD','Marrowfen Sanitary District',[
 R('budget_cap','reject',{},"the aggregate of all fees and costs invoiced on a matter shall at no time surpass the maximum compensation set out in the applicable engagement letter unless and until the Board has approved an increase by written amendment.","Section 1.01, page 1"),
 R('phase_cap','reduce',{},"Where the engagement letter divides the maximum compensation among phases of work, Counsel shall not invoice against any phase a sum greater than the portion assigned to that phase, it being understood that savings in one phase do not carry over to another without the General Manager's written consent.","Section 1.02, page 1"),
 R('rate_above_card','reduce',{},"Hourly rates are those appearing in the fee schedule attached to the engagement letter, and no timekeeper shall be billed at a rate higher than the rate there shown for that timekeeper.","Section 1.03, page 1"),
 R('unapproved_timekeeper','reject',{},"The District will not pay for the time of any person who does not appear by name in the fee schedule.","Section 1.04, page 1"),
 R('staffing_matter_limit','review',{"max_timekeepers":4},"Absent the General Manager's prior written consent, not more than four (4) timekeepers shall record time to a single matter in any one billing month.","Section 1.05, page 1"),
 R('minimum_increment','reject',{"increment":"0.1"},"All time shall be kept contemporaneously and stated in units of one-tenth (0.1) of an hour.","Section 2.01, page 2"),
 R('block_billing','reject',{"max_tasks":1,"min_hours":"1.5"},"Each entry shall be confined to one activity; an entry exceeding one and one-half (1.5) hours that aggregates distinct activities under a single time figure will be disallowed in its entirety, the District being unable to assess the reasonableness of the time devoted to each.","Section 2.02, page 2"),
 R('required_codes','reject',{"require_task":True,"require_activity":False,"require_expense":False},"Every time entry shall bear the task code corresponding to the phase of work to which it relates.","Section 2.03, page 2"),
 R('late_time','reject',{"max_age_days":120},"Time submitted more than one hundred twenty (120) days after the date on which the work was performed is deemed waived.","Section 2.04, page 2"),
 R('duplicate_entries','reject',{},"Counsel shall review each invoice before submission to ensure that no service appears on it more than once; any repeated entry will be deducted.","Section 2.05, page 2"),
 R('travel_time','reject',{"billable_percent":100,"requires_approval":True},"Time spent in transit is compensable only where the General Counsel has authorized the trip in writing before it is taken; authorized transit time is paid at the timekeeper's ordinary rate.","Section 3.01, page 2"),
 R('non_billable_task','reject',{"categories":{"clerical":CLER+["secretarial","filing","calendaring"]}},"The hourly rates are understood to absorb the cost of secretarial support, filing, photocopying, calendaring and similar administrative functions, none of which shall appear as a time charge.","Section 3.02, page 2",docterms=["secretarial","filing","calendaring"]),
 R('expense_per_diem','reduce',{"caps":{"meal":"40.00","lodging":"150.00"}},"Subsistence while away overnight on District business is reimbursable up to forty dollars ($40.00) per person per day for meals and one hundred fifty dollars ($150.00) per night for lodging.","Section 4.01, page 3"),
 R('expense_receipt_threshold','reject',{"threshold":"20.00","inclusive":False},"Counsel shall furnish a receipt for every cost item in excess of $20.00.","Section 4.02, page 3"),
 R('expense_markup','reduce',{},"Costs advanced to third parties on the District's behalf shall be invoiced in the amount actually paid, without surcharge or handling fee.","Section 4.03, page 3"),
],[
 ("The District does not impose a ceiling on the number of hours a timekeeper may record in a single day, but Counsel should expect questions where the hours recorded appear disproportionate to the task.","says there is NO daily limit; a daily_hour_cap rule must not be proposed from it"),
 ("Invoices shall be rendered monthly and addressed to the General Manager, and shall be paid within forty-five (45) days of receipt.","payment terms; the 45 days is not a late-time limit or a rate notice period"),
 ("Counsel shall maintain professional liability coverage of not less than $2,000,000 throughout the engagement.","insurance; not a billing rule"),
])
C['batch_a/pindlecroft']=('PCR','Pindlecroft Robotics',[
 R('minimum_increment','reject',{"increment":"0.25"},"Quarter-hour increments (0.25) are fine with us, just be consistent about it.","item 1"),
 R('block_billing','reduce',{"max_tasks":2,"min_hours":"1.0"},"Please don't cram a whole afternoon into one line: two related tasks in an entry is OK, but if an entry of more than an hour lists three or more things I'll send it back to be split.","item 1"),
 R('vague_description','reduce',vague(),"Tell me what you actually did, because \"work on matter\" or \"review file\" tells me nothing and I can't approve it.","item 1"),
 R('daily_hour_cap','review',{"max_hours":10},"If any one person bills more than 10 hours in a day I'm going to ask why, so give me a heads-up.","item 2"),
 R('staffing_event_limit','reduce',{"max_attendees":2,"events":["hearing","deposition"]},"For hearings and depositions, two of your lawyers at most on our dime.","item 2"),
 R('internal_conference_limit','reduce',{"max_hours_per_entry":"0.5"},"Internal meetings among your own team: bill up to half an hour (0.5) per entry and no more.","item 2"),
 R('research_approval','reduce',{"max_hours":6},"Clear it with me before the team spends more than 6 hours on legal research on a matter.","item 2"),
 R('rate_above_card','reduce',{},"Whatever is on the rate schedule we signed in January is the rate, and nothing above it.","item 3"),
 R('late_time','reject',{"max_age_days":60},"Anything older than 60 days when the bill goes out, we won't pay.","item 4"),
 R('duplicate_entries','reject',{},"If a line shows up twice, we pay it once.","item 4"),
 R('expense_overhead','reject',{"codes":OH_CODES,"phrases":sorted(set(OH_PH)|{"phones"})},"Please don't pass through overhead: online research subscriptions, phones, postage, staff overtime, word processing.","item 5",docterms=["phones"]),
 R('expense_markup','reduce',{},"Vendor costs come through at what you paid, with no markup.","item 5"),
 R('ai_disclosure_required','reject',{"disclosure_marker":"(GenAI)","ai_terms":AI_TERMS},"put \"(GenAI)\" in the narrative of any time entry where one was used.","item 6"),
 R('ai_nonpayable_task','reject',{"disclosure_marker":"(GenAI)","ai_terms":AI_TERMS,"task_phrases":AI_TASKS+["digest","first-level document review","first level document review"]},"We won't pay lawyer rates for AI-written summaries or digests of depositions and documents, or for AI doing the first-level document review.","item 6",docterms=["digest","first-level document review","first level document review"]),
 R('travel_time','reduce',{"billable_percent":0,"requires_approval":False},"Honestly we'd rather not pay for travel time at all, but I haven't settled that with our CFO yet, so treat it as a preference for now and let's talk before any big trip.","item 7",status='proposed',notes="Not confirmed. The memo calls this a preference that is not yet settled, so it is not enforced."),
],[
 ("Last thing: please get bills to me by the 5th of the month and copy accounts payable.","bill timing; no rule type covers it"),
])
C['batch_b/bramblewick']=('BFC','Bramblewick Freight Cooperative',[
 R('unapproved_timekeeper','reject',{},"Named on the matter staffing list only.","row 1, Timekeepers"),
 R('staffing_matter_limit','review',{"max_timekeepers":3},"Max 3 timekeepers per matter per bill unless Legal Ops agrees a bigger team.","row 2, Team size"),
 R('rate_above_card','reduce',{},"The matter rate card governs; nothing higher.","row 3, Rates"),
 R('rate_increase_notice','reduce',{"notice_days":90},"90 days written notice before a rise applies.","row 4, Rate rises"),
 R('minimum_increment','reject',{"increment":"0.1"},"Tenths of an hour.","row 5, Units"),
 R('block_billing','reduce',{"max_tasks":1,"min_hours":"0.5"},"One task per line once a line is over 0.5 h.","row 6, Task detail"),
 R('vague_description','reject',vague(extra_bare=["emails"]),"Must name the work product or the person dealt with; \"review documents\" or \"emails\" will not do.","row 7, Narrative",docterms=["emails"]),
 R('required_codes','reject',{"require_task":True,"require_activity":True,"require_expense":False},"Task code and activity code on every fee line.","row 8, Codes"),
 R('daily_hour_cap','reduce',{"max_hours":8},"8.0 h per person per day; more needs a note from the partner.","row 9, Daily hours"),
 R('late_time','reject',{"max_age_days":90},"Nothing over 90 days old at bill date.","row 10, Age of time"),
 R('duplicate_entries','reject',{},"Paid once.","row 11, Duplicates"),
 R('non_billable_task','reject',{"categories":{"clerical":CLER+["copying","filing","bates"],"training":TRAIN,"invoice_prep":INVP}},"No charge for copying, filing, Bates work, staff training, or preparing or explaining a bill.","row 12, Admin work",docterms=["copying","filing","bates"]),
 R('internal_conference_limit','reduce',{"max_hours_per_entry":"0.4"},"0.4 h cap per line.","row 13, Internal meetings"),
 R('expense_overhead','reject',{"codes":OH_CODES,"phrases":sorted(set(OH_PH)|{"phone"})},"No postage, phone, in-house word processing, staff overtime or database subscriptions.","row 14, Overhead",docterms=["phone"]),
 R('expense_receipt_threshold','reject',{"threshold":"50.00","inclusive":True},"Needed for any cost of $50.00 and up.","row 15, Receipts"),
 R('expense_markup','reduce',{},"Actual cost only.","row 16, Third-party costs"),
 R('ai_disclosure_required','reject',{"disclosure_marker":"[GAI]","ai_terms":AI_TERMS},"A line done with a generative AI tool must carry the tag [GAI].","row 17, AI tools"),
 R('ai_nonpayable_task','reject',{"disclosure_marker":"[GAI]","ai_terms":AI_TERMS,"task_phrases":AI_TASKS},"No payment for AI-made summaries of transcripts or documents, or AI first-pass document review.","row 18, AI output"),
],[
 ("Monthly, by the 15th.","bill timing; no rule type covers it"),
 ("Send a fee estimate at matter opening; update it if it moves by 20%.","an estimate, not a not-to-exceed amount; a budget_cap rule must not be proposed from it"),
])
C['batch_b/coldwaterfen']=('CFH','Coldwater Fen Hospital Authority',[
 R('budget_cap','reject',{},"The Authority's obligation to pay Counsel on any assignment is limited to the ceiling amount fixed in the assignment order, and Counsel proceeds at its own risk as to any fees or costs that would carry total billings past that ceiling.","clause (a) Ceiling, page 1"),
 R('phase_cap','reduce',{},"Where an assignment order apportions the ceiling amount among stages, billings attributable to a stage shall be held within the sum apportioned to it.","clause (a) Ceiling, page 1"),
 R('rate_above_card','reduce',{},"Services shall be charged at the rates enumerated in the assignment order and not otherwise.","clause (b) Persons and rates, page 1"),
 R('unapproved_timekeeper','reject',{},"Charges for the services of any individual not named in the assignment order will be refused.","clause (b) Persons and rates, page 1"),
 R('minimum_increment','reject',{"increment":"0.1"},"Time is to be reported in tenths of an hour (six-minute units).","clause (c) Recording of time, page 1"),
 R('rounding_pattern','review',{"block":"1.0","min_entries":8,"threshold_percent":75},"The Authority's auditors will inquire into the records of any timekeeper three-quarters or more of whose entries (eight entries being the minimum examined) are stated in whole hours.","clause (c) Recording of time, page 1"),
 R('block_billing','reject',{"max_tasks":1,"min_hours":0},"A time entry shall describe a single service, and the Authority declines to pay for composite entries in which two or more services share one time figure.","clause (c) Recording of time, page 1"),
 R('required_codes','reject',{"require_task":True,"require_activity":False,"require_expense":False},"Each time entry shall carry the task code of the stage of work it belongs to.","clause (c) Recording of time, page 1"),
 R('late_time','reject',{"max_age_days":60},"Charges presented later than sixty (60) days after the service was rendered are barred.","clause (d) Timeliness and repetition, page 2"),
 R('duplicate_entries','reject',{},"No service shall be charged more than once, and any charge found to be repeated shall be deducted.","clause (d) Timeliness and repetition, page 2"),
 R('research_approval','reduce',{"max_hours":4},"Counsel shall obtain the written concurrence of the Chief Legal Officer before devoting in excess of four (4) hours to legal research on an assignment.","clause (e) Research and attendance, page 2"),
 R('staffing_event_limit','reduce',{"max_attendees":1,"events":["deposition","hearing","mediation","arbitration"]},"The Authority will compensate the attendance of not more than one (1) attorney at any deposition, hearing, mediation or arbitration session.","clause (e) Research and attendance, page 2"),
 R('travel_time','reduce',{"billable_percent":50,"requires_approval":True},"Travel time, where the Chief Legal Officer has approved the travel in advance, is compensated at one-half of the timekeeper's rate; unapproved travel time is not compensated.","clause (f) Travel, page 2"),
 R('expense_per_diem','reduce',{"caps":{"meal":"65.00","lodging":"225.00"}},"Meals taken while travelling for the Authority are reimbursed to a limit of $65.00 per person per day, and overnight accommodation to a limit of $225.00 per night.","clause (g) Disbursements, page 3"),
 R('expense_receipt_threshold','reject',{"threshold":"25.00","inclusive":False},"A receipt shall accompany every disbursement exceeding $25.00.","clause (g) Disbursements, page 3"),
],[
 ("The Authority places no fixed limit on the hours a timekeeper may work in a day.","says there is NO daily limit; a daily_hour_cap rule must not be proposed from it"),
 ("Counsel shall submit its invoices within thirty (30) days of the close of each calendar quarter and shall retain its time records for four (4) years.","invoice timing and record keeping; the 30 days is not a late-time limit and the 4 is not an hours limit"),
 ("Expert and consultant fees above $5,000 require a purchase order before the expense is incurred.","a purchase-order rule; no rule type covers it. It must not be read as a receipt threshold"),
])
C['batch_b/nettlecombe']=('NHL','Nettlecombe Home Lending',[
 R('minimum_increment','reject',{"increment":"0.1"},"Keep time in six-minute blocks, so 0.1 of an hour.","paragraph 2"),
 R('block_billing','reduce',{"max_tasks":1,"min_hours":"0.3"},"Anything over 18 minutes (0.3) that covers more than one task comes back to you.","paragraph 2"),
 R('vague_description','reduce',vague(),"Same for entries that don't say anything: \"attention to matter\", \"draft correspondence\" and the like.","paragraph 2"),
 R('rate_above_card','reduce',{},"Stick to the rates in the engagement letter.","paragraph 3"),
 R('duplicate_entries','reject',{},"Double entries get paid once.","paragraph 3"),
 R('daily_hour_cap','review',{"max_hours":11},"Eleven hours is the most I'll accept from one person in a day without a call first.","paragraph 4"),
 R('staffing_event_limit','reduce',{"max_attendees":2,"events":["deposition","hearing","mediation"]},"No more than two of your people at any deposition, hearing or mediation.","paragraph 4"),
 R('internal_conference_limit','reduce',{"max_hours_per_entry":"0.3"},"Lawyers talking to each other inside your firm: 0.3 max per entry.","paragraph 4"),
 R('research_approval','reduce',{"max_hours":5},"Ask me before legal research on a file goes past 5 hours.","paragraph 4"),
 R('travel_time','reduce',{"billable_percent":50,"requires_approval":False},"Travel time gets billed at half your normal rate.","paragraph 5"),
 R('expense_per_diem','reduce',{"caps":{"meal":"75.00","lodging":"250.00"}},"On the road, meals are $75 a head per day and hotels $250 a night, tops.","paragraph 5"),
 R('non_billable_task','reject',{"categories":{"clerical":CLER,"conflicts":CONFL,"training":TRAIN}},"Don't bill us for clerical work, conflict checks or training your own people.","paragraph 6"),
 R('expense_overhead','reject',{"codes":OH_CODES,"phrases":sorted(set(OH_PH)|{"phone charges","online research"})},"No overhead on the bill either: postage, word processing, phone charges, office supplies, online research fees.","paragraph 6",docterms=["phone charges","online research"]),
 R('expense_markup','reduce',{},"Outside vendor charges come through at cost.","paragraph 6"),
 R('late_time','reject',{"max_age_days":60},"Try to get time to us within 60 days.","paragraph 8",status='proposed',notes="Not confirmed. The email says older time will not be bounced yet, so this is a wish and is not enforced."),
],[
 ("Keep your receipts, because I may ask for them, but you don't need to attach them.","says receipts are NOT required with the bill; an expense_receipt_threshold rule must not be proposed from it"),
 ("Our fiscal year ends March 31, so please get February and March time in promptly.","a request with no limit; not a rule"),
])
for path,(pref,name,rs,non) in C.items():
    batch,cid=path.split('/')
    doc=open(H+batch+'/guideline_docs/'+cid+'.txt').read()
    out={"client_id":cid,"client_name":name,"document":"heldout/%s/guideline_docs/%s.txt"%(batch,cid),"rules":[]}
    ik={"client_id":cid,"document":"guideline_docs/%s.txt"%cid,"expected_rules":[],"sentences_that_are_not_rules":[]}
    seen=set()
    for r in rs:
        assert r['quote'] in doc,(cid,r['quote'])
        assert r['t'] not in seen; seen.add(r['t'])
        rid='%s-%s-01'%(pref,SUF[r['t']])
        d={"rule_id":rid,"type":r['t'],"status":r['status'],"severity":r['sev'],"params":r['params'],"source_quote":r['quote'],"source_ref":r['ref']}
        if r['status']=='confirmed': d.update(confirmed_by="Independent test author (fictional billing manager)",confirmed_on="2026-11-26")
        if r['notes']: d['notes']=r['notes']
        out['rules'].append(d)
        num={k:v for k,v in r['params'].items() if k not in('always_phrases','bare_phrases','categories','codes','phrases','ai_terms','task_phrases')}
        if 'categories' in r['params']: num['categories']=sorted(r['params']['categories'])
        e={"rule_id":rid,"type":r['t'],"status_a_person_would_give":r['status'],"key_params":num,"source_quote":r['quote']}
        if r['docterms']: e['terms_added_from_document']=r['docterms']
        ik['expected_rules'].append(e)
    for q,why in non:
        assert q in doc,(cid,q)
        ik['sentences_that_are_not_rules'].append({"text":q,"why":why})
    json.dump(out,open(H+batch+'/guidelines/'+cid+'.json','w'),indent=2)
    C[path]=ik
for batch in ('batch_a','batch_b'):
    K={"note":"Ground truth for the intake helper, %s. Written by hand from the guideline documents, before any tool run. expected_rules lists the rules a person reading the document would confirm (or, where marked proposed, would leave unconfirmed). key_params are the values stated in the document. Keyword lists (vague phrases, clerical phrases, overhead phrases and codes, AI terms) are NOT ground truth and are left out of key_params: see README. sentences_that_are_not_rules are sentences an intake pass must not turn into a rule of the type named."%batch,
       "scoring_suggestion":"A proposed rule matches when its type matches and its source sentence overlaps the source_quote. Score type recall and precision first, then key_params equality on matched rules. Severity is the test author's judgement and should be reported separately, not counted as wrong.",
       "clients":[v for k,v in C.items() if k.startswith(batch)]}
    json.dump(K,open(H+batch+'/INTAKE_KEY.json','w'),indent=1)
    print(batch,[ (c['client_id'],len(c['expected_rules'])) for c in K['clients']])
