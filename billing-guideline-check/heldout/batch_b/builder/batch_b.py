from lib import F,E
from common import rules
YEAR='2026'
TK={
 'bramblewick':{'D31':('Thaddeus Ilves-Moreau','PT','540.00'),'D32':('Calliope Ndiaye-Hart','AS','385.00'),'D33':('Bertrand Yilmaz-Coyle','AS','360.00'),'D34':('Marguerite Osei-Lund','LA','195.00')},
 'coldwaterfen':{'E41':('Rosalind Achterhof-Mensah','PT','495.00'),'E42':('Julius Karlsson-Obeng','AS','350.00'),'E43':('Imogen Tavares-Wolde','AS','320.00'),'E44':('Cyprian Lowell-Adjei','LA','165.00')},
 'nettlecombe':{'G51':('Evander Mistry-Halloran','PT','430.00'),'G52':('Philippa Zubiri-Kane','AS','300.00'),'G53':('Tobiah Lindahl-Eze','AS','275.00'),'G54':('Greer Nakamura-Boyle','LA','140.00')},
}
EXTRA={'D39':('Florian Castellano-Ige','AS','360.00'),'E49':('Leopoldine Graaf-Achebe','AS','320.00')}
B=rules('BFC'); C=rules('CFH'); N=rules('NHL')
INV=[]
# ---------------------------------------------------------------- Bramblewick 1
INV.append(dict(id='INV-BFC-4401',client='bramblewick',matter='BFC-LIT-301',date='2026-11-16',start='2026-10-01',end='2026-10-31',rules=B,
 inv_v=[('staffing_matter_limit','five timekeepers (D31, D32, D33, D34, D39) on the invoice against a limit of three, no approval','','easy')],lines=[
 F('08-14','D31','0.5','L120','A106',"Advise claims manager on carrier liability cap in the bill of lading",ai='no',v=[('late_time','94 days old on the invoice date; limit 90','easy')]),
 F('08-18','D32','1.2','L120','A104',"Analyze shipper's claim letter and reefer temperature download",ai='no',hn="exactly 90 days old on the invoice date; the table refuses work 'over 90 days old'"),
 F('10-01','D32','2.8','L210','A103',"Draft answer and affirmative defenses to shipper's complaint",ai='no'),
 F('10-01','D34','0.7','L320','A110',"Put Bates numbers on reefer unit maintenance records",ai='no',v=[('non_billable_task','clerical work (Bates numbering), not worded as bates stamping','medium')]),
 F('10-02','D33','1.5','L310','A103',"Draft initial disclosures",ai='no',v=[('rate_increase_notice','360 billed, last billed 340; notice given 2026-07-20, so the 90 day period ran to 2026-10-18','medium')]),
 F('10-05','D32','0.4','L120','A105',"Internal conference with T. Ilves-Moreau on limitation-of-liability defense",ai='no',hn="internal conference of exactly 0.4 hour, which is the limit"),
 F('10-06','D31','0.6','L120','A101',"Sat down with C. Ndiaye-Hart to map out discovery plan",ai='no',v=[('internal_conference_limit','0.6 hour in-firm meeting against a 0.4 hour limit; no conference wording and coded A101','hard')]),
 F('10-06','D32','0.4','L310','A103',"Email to shipper's counsel on protective order; review redline",ai='no',hn="two tasks, but 0.4 hour is under this client's 0.5 hour threshold"),
 F('10-07','D32','1.6','L310','A103',"Draft interrogatories to shipper, review dock receipts for seal numbers, phone the driver about the temperature alarm",ai='no',v=[('block_billing','three tasks in one 1.6 hour entry, separated only by commas','hard')]),
 F('10-08','D34','1.0','L320','A104',"Review documents",ai='no',v=[('vague_description','generic phrase, no object','easy')]),
 F('10-09','D32','0.3','L120','A106',"Emails",ai='no',v=[('vague_description','one word','medium')]),
 F('10-12','D33','2.0','L340','A104',"Review surveyor's report on cargo spoilage and salvage value",ai='no',v=[('rate_increase_notice','360 billed, last billed 340; before the notice period ended on 2026-10-18','medium')]),
 F('10-13','D32','3.9','L330','A101',"Prepare driver for deposition",ai='no'),
 F('10-13','D32','4.4','L330','A109',"Defend driver's deposition",ai='no',v=[('daily_hour_cap','D32 day total 8.3 hours on 2026-10-13 against an 8 hour limit; client approved the long day, see waiver W-B01','easy','waived')]),
 F('10-14','D34','1.15','L320','A104',"Chart temperature readings against delivery timeline",ai='no',v=[('minimum_increment','1.15 hours is not a multiple of 0.1','easy')]),
 F('10-15','D32','2.2','L240','A103',"Draft motion for summary adjudication on liability cap [GAI]",ai='yes',hn="AI-assisted, disclosed with the client's marker, and a payable task"),
 F('10-16','D34','1.8','L330','A104',"Summarize driver's deposition transcript for claims manager [GAI]",ai='yes',v=[('ai_nonpayable_task','AI-assisted transcript summary, which the client will not pay for; marker is present','easy')]),
 F('10-19','D33','1.3','L240','A103',"Draft separate statement of undisputed facts",ai='yes',hn_rate=1,v=[('ai_disclosure_required','time system flags the entry as AI-assisted and the narrative has no [GAI] marker. (The 360 rate is allowed on this date: the notice period ended 2026-10-18.)','easy')]),
 F('10-20','D32','0.9','L240','',"Revise summary adjudication motion per partner comments",ai='no',v=[('required_codes','activity code missing','easy')]),
 F('10-21','D39','2.5','L240','A104',"Analyze treatment of released-value clauses in freight contracts",ai='no',v=[('unapproved_timekeeper','D39 is not on the approved list for the matter','easy')]),
 F('10-22','D34','0.5','L140','A110',"Attended firm's e-filing system refresher",ai='no',v=[('non_billable_task','training, described without the word','hard')]),
 F('10-23','D31','1.1','L160','A107',"Settlement discussion with shipper's counsel",ai='no'),
 F('10-23','D31','1.1','L160','A107',"Settlement discussion with shipper's counsel",ai='no',v=[('duplicate_entries','same as the entry before it','easy')]),
 F('10-26','D32','1.4','L240','A103',"Draft reply; sections on notice of claim; spoliation of the load",ai='no',hn="one drafting task described in parts with semicolons, over the 0.5 hour threshold"),
 F('10-27','D34','0.8','L140','A110',"Gathered time detail and expense receipts to answer client's question on the September bill",ai='no',v=[('non_billable_task','time spent answering a billing question; invoice work described without the usual words','hard')]),
 F('10-28','D32','3.0','L330','A109',"Take deposition of shipper's quality manager",ai='no',amount='1165.00',v=[('ARITH-LINE','3.0 x 385 is 1155.00, line says 1165.00','easy')]),
 E('10-13',1,'512.00','E115',"Transcript, driver deposition"),
 E('10-13',1,'50.00','E109',"Parking and tolls, driver deposition",receipt='no',v=[('expense_receipt_threshold','50.00 with no receipt; the table requires receipts at 50.00 and up, so the threshold itself is caught','hard')]),
 E('10-13',1,'49.00','E111',"Working lunch with driver before deposition",receipt='no',hn="no receipt, 49.00 is under the 50.00 threshold; this client has no meal cap"),
 E('10-20',1,'22.00','E105',"Long-distance and conference call charges",v=[('expense_overhead','telephone charges (expense code E105)','medium')]),
 E('10-26',1,'330.00','E119',"Refrigeration engineer, records review",cost='300.00',v=[('expense_markup','billed 330.00 against a cost of 300.00','easy')]),
]))
# ---------------------------------------------------------------- Bramblewick 2
INV.append(dict(id='INV-BFC-4402',client='bramblewick',matter='BFC-LIT-318',date='2026-11-16',start='2026-10-01',end='2026-10-31',rules=B,total_off='-30.00',
 inv_v=[('ARITH-TOTAL','declared total is 30.00 less than the lines','','easy')],lines=[
 F('10-01','D31','0.8','L120','A106',"Call with terminal operations director on holdover rent exposure",ai='no'),
 F('10-02','D32','2.1','L210','A103',"Draft unlawful detainer answer: denial of holdover, estoppel, and offset for roof repairs",ai='no',hn="list of defenses after a colon; one task"),
 F('10-02','D34','0.9','L320','A104',"Review lease, three amendments, and estoppel certificate for renewal option deadlines",ai='no',hn="one review task over a list of documents"),
 F('10-05','D33','1.2','L310','A103',"Draft document requests to landlord",ai='no',hn="D33 at 360: on this matter 360 is both the approved and the last billed rate"),
 F('10-06','D32','0.5','L120','A105',"Internal conference with B. Yilmaz-Coyle and M. Osei-Lund on lease chronology",ai='no',v=[('internal_conference_limit','0.5 hour against a 0.4 hour limit','easy')]),
 F('10-07','D32','3.4','L240','A103',"Draft motion for summary judgment on renewal option",ai='no'),
 F('10-08','D32','4.0','L240','A103',"Draft declaration of terminal operations director with exhibits",ai='no',hn="first entry of a 7.9 hour day, under the 8 hour limit"),
 F('10-08','D32','3.9','L240','A103',"Draft memorandum of points and authorities on option exercise",ai='no',hn="second entry of a 7.9 hour day, under the 8 hour limit"),
 F('10-09','D34','1.6','L240','A104',"Cite-check summary judgment memorandum",ai='no'),
 F('10-12','D33','0.7','L160','A107',"Telephone call with landlord's counsel regarding standstill on eviction",ai='no',hn="starts with a generic phrase but names who and what"),
 F('10-13','D31','0.4','L160','A106',"Follow up with client on standstill terms",ai='no',hn="sounds vague but names who and what"),
 F('10-14','D34','0.6','L320','A110',"Photocopying lease file for landlord's inspection demand",ai='no',v=[('non_billable_task','clerical work (photocopying)','easy')]),
 F('10-15','D32','1.0','L310','A104',"Review landlord's production: rent ledgers, notices of default, broker emails",ai='no'),
 F('10-16','D33','2.3','L330','A101',"Outline deposition of landlord's property manager",ai='no'),
 F('10-19','D33','3.2','L330','A109',"Take deposition of landlord's property manager",ai='no'),
 F('10-20','D32','1.9','L240','A103',"Draft reply and prepare hearing binder, plus call client about settlement authority",ai='no',v=[('block_billing','three tasks in one 1.9 hour entry, joined by and and plus','hard')]),
 F('10-21','D31','1.5','L240','A109',"Argue summary judgment motion",ai='no'),
 F('10-21','D32','1.5','L240','A109',"Attend summary judgment hearing",ai='no',hn="second lawyer at a hearing; this client's table has no limit on attendance at events"),
 F('10-22','D32','0.6','L440','A101',"Trial preparation",ai='no',v=[('vague_description','generic phrase, no object','easy')]),
 F('10-23','D34','0.4','L160','A103',"Drafted and revised stipulation extending trial date",ai='no'),
 F('10-26','D31','0.9','L160','A109',"Settlement conference with landlord's principal",ai='no',hn="a conference with the other side, not an internal conference"),
 F('10-27','D32','1.3','L160','A103',"Draft lease amendment term sheet using machine-generated comparison of prior amendments",v=[('ai_disclosure_required','narrative says a machine-generated work product was used; no [GAI] marker; time-system flag blank','medium')]),
 F('10-28','D33','0.8','L160','A104',"Review landlord's proposed clause on automated gate and AI camera systems at the terminal",ai='no',hn="AI is the subject matter of the clause reviewed, not a tool used to do the work; time-system flag says no"),
 E('10-15',1,'145.00','E107',"Courier, exhibit set to court"),
 E('10-19',1,'640.00','E115',"Transcript, property manager"),
 E('10-21',1,'75.00','E124',"Monthly fee for online case-law service, allocated share",v=[('expense_overhead','database subscription, described without the word subscription','hard')]),
 E('10-12',1,'120.00','E113',"Subpoena service on former broker",receipt='no',v=[('expense_receipt_threshold','120.00 with no receipt; receipts needed from 50.00','easy')]),
]))
# ---------------------------------------------------------------- Bramblewick 3 (LEDES)
INV.append(dict(id='INV-BFC-4403',client='bramblewick',matter='BFC-REG-044',date='2026-11-16',start='2026-10-01',end='2026-10-31',rules=B,fmt='ledes',desc='Legal services, October 2026',
 inv_v=[('staffing_matter_limit','four timekeepers (D31, D32, D34, D39) on the invoice against a limit of three, no approval','','easy')],lines=[
 F('10-01','D31','0.7','L120','A106',"Call with safety director on scope of audit letter"),
 F('10-02','D32','2.4','L120','A104',"Review audit letter and list of driver logs requested"),
 F('10-05','D34','3.1','L320','A104',"Compare electronic logging records against dispatch sheets for 14 sampled drivers"),
 F('10-06','D34','0.9','L320','A110',"Renamed and sorted log files into driver folders on the shared drive",v=[('non_billable_task','clerical file handling described as what was done','hard')]),
 F('10-07','D32','1.7','L120','A103',"Draft response to audit findings 1 through 4"),
 F('10-08','D32','0.35','L120','A106',"Email safety director on missing logs",v=[('minimum_increment','0.35 hour is not a multiple of 0.1','easy')]),
 F('10-09','D31','0.5','L120','A105',"Conference with C. Ndiaye-Hart re audit response structure",v=[('internal_conference_limit','0.5 hour against a 0.4 hour limit','easy')]),
 F('10-12','D32','5.0','L110','A109',"Interview six drivers at Ashby terminal about log edits"),
 F('10-12','D32','3.4','L110','A103',"Draft interview memoranda for sampled drivers",v=[('daily_hour_cap','D32 day total 8.4 hours on 2026-10-12 against an 8 hour limit; 0.4 hour of this entry is over','easy')]),
 F('10-13','D34','1.2','L320','A104',"Work on case",v=[('vague_description','generic phrase, no object','easy')]),
 F('10-14','D32','1.4','L120','A103',"Draft corrective action plan; driver coaching; log edit approvals; quarterly self-audit",hn="one drafting task described in parts with semicolons, over the 0.5 hour threshold"),
 F('10-15','D32','0.8','L120','A103',"Revise corrective action plan with safety director's edits"),
 F('10-16','D31','1.0','','A104',"Review draft audit response",v=[('required_codes','task code missing','easy')]),
 F('10-19','D32','2.2','L120','A103',"Finalize audit response, telephone conference with auditor on extension, begin penalty exposure memo",v=[('block_billing','three tasks in one 2.2 hour entry','medium')]),
 F('10-20','D34','0.6','L320','A103',"Prepare appendix of corrected logs"),
 F('10-20','D34','0.6','L320','A103',"Prepare appendix of corrected logs",v=[('duplicate_entries','same as the entry before it','easy')]),
 F('08-10','D31','0.4','L120','A106',"Preliminary call with safety director on notice of audit",v=[('late_time','98 days old on the invoice date; limit 90. Out of date order on the invoice','medium')]),
 F('10-21','D32','1.0','L120','A103',"Draft penalty exposure memo",rate='400.00',v=[('rate_above_card','billed at 400 against an approved 385','easy')]),
 F('10-22','D39','1.3','L120','A104',"Review prior audit closeout letters",v=[('unapproved_timekeeper','D39 is not on the approved list for the matter','easy')]),
 F('10-23','D32','1.5','L120','A103',"Draft cover letter to auditor [GAI]",hn="carries the client's AI marker and is a payable task"),
 F('10-26','D34','2.0','L320','A104',"Used generative AI tool for first-pass document review of dispatch emails [GAI]",v=[('ai_nonpayable_task','AI first-pass document review, which the client will not pay for; marker is present','easy')]),
 F('10-27','D32','0.7','L120','A103',"Tighten audit response with an AI writing assistant",v=[('ai_disclosure_required','narrative says an AI tool was used; no [GAI] marker','medium')]),
 F('10-28','D31','0.6','L120','A106',"Report to general counsel on audit outcome and next steps"),
 E('10-12',1,'88.40','E109',"Mileage, Ashby terminal interviews"),
 E('10-28',1,'31.00','E108',"Stamps and certified mail, audit response",v=[('expense_overhead','postage, described as stamps and certified mail (expense code E108)','medium')]),
]))
# ---------------------------------------------------------------- Coldwater Fen 1
INV.append(dict(id='INV-CFH-6601',client='coldwaterfen',matter='CFH-2026-A4',date='2026-11-13',start='2026-10-01',end='2026-10-31',rules=C,
 inv_v=[('rounding_pattern','eight of the ten E42 entries (80%) are whole hours; the document questions three-quarters or more','E42','medium'),
        ('budget_cap','BUDGET','','easy'),('phase_cap','PHASE','','easy')],lines=[
 F('09-10','E41','0.6','L120','A106',"Advise chief financial officer on rejection of nonconforming scanner",v=[('late_time','64 days old on the invoice date; limit 60','easy')]),
 F('09-14','E43','1.4','L120','A104',"Review purchase agreement warranty and acceptance testing provisions",hn="exactly 60 days old on the invoice date; the document refuses time presented 'later than sixty days' after the work"),
 F('10-01','E42','2.0','L210','A103',"Draft complaint for breach of warranty and rescission",hn="and joins two causes of action in one complaint; one task"),
 F('10-02','E42','3.0','L210','A103',"Draft application for writ of attachment"),
 F('10-05','E43','1.7','L110','A102',"Research revocation of acceptance for capital equipment",res=1),
 F('10-06','E43','1.6','L110','A104',"Review authorities on consequential damages disclaimers in vendor form contracts",res=1),
 F('10-07','E43','1.1','L110','A102',"Check how courts have treated repair-or-replace clauses that fail of essential purpose",res=1,v=[('research_approval','legal research reaches 4.4 hours (lines 5, 6 and 7) against a 4 hour limit, no approval; lines 6 and 7 do not use the word research and line 6 is coded A104','hard')]),
 F('10-07','E42','1.0','L310','A103',"Draft litigation hold letter to vendor"),
 F('10-08','E44','0.8','L320','A104',"Review service tickets; downtime entries; technician notes",hn="one review task with its parts separated by semicolons"),
 F('10-09','E42','4.0','L310','A103',"Draft first set of special interrogatories"),
 F('10-12','E42','1.3','L160','A107',"Call with vendor's counsel on interim loaner unit, then update to chief financial officer",v=[('block_billing','two tasks in one entry, joined by then; this client allows one','medium')]),
 F('10-13','E44','0.45','L320','A104',"Calculate downtime hours from service tickets",v=[('minimum_increment','0.45 hour is not a multiple of 0.1','easy')]),
 F('10-14','E41','1.2','L160','A107',"Negotiate interim loaner agreement",rate='510.00',v=[('rate_above_card','billed at 510 against an approved 495','easy')]),
 F('10-15','E41','5.0','L160','A109',"Represent Authority at mediation"),
 F('10-15','E42','5.0','L160','A109',"Accompany R. Achterhof-Mensah to mediation and manage exhibits",v=[('staffing_event_limit','second attorney at a mediation, no approval; the word attend is not used. Either attendee line is acceptable as the flagged line','hard')],alt=[14]),
 F('10-15','E41','2.0','L160','A109',"Travel to and from mediation in Dunsmere (half rate)",rate='247.50',v=[('travel_time','travel billed correctly at half rate, but this client also requires advance approval and none is on record for the matter','hard')]),
 F('10-16','E42','2.0','L160','A103',"Draft response to mediator's proposal"),
 F('10-19','E42','1.0','L310','A104',"Review vendor's objections to document requests"),
 F('10-20','E42','3.0','L350','A103',"Draft motion to compel service records"),
 F('10-21','E43','2.4','','A103',"Draft declaration of radiology director",v=[('required_codes','task code missing','easy')]),
 F('10-22','E44','1.1','L320','A103',"Prepare chronology of scanner outages from maintenance log"),
 F('10-22','E44','1.1','L320','A103',"Prepare chronology of scanner outages from maintenance log",v=[('duplicate_entries','same as the entry before it','easy')]),
 F('10-23','E49','1.5','L350','A103',"Draft proposed order on motion to compel",v=[('unapproved_timekeeper','E49 is not among the personnel named for the matter','easy')]),
 F('10-26','E42','0.7','L350','A103',"Revise meet-and-confer declaration"),
 E('10-15',1,'238.00','E110',"Room, Dunsmere Lodge, night before mediation",v=[('expense_per_diem','238.00 a night against a 225.00 lodging cap; described as a room','hard')]),
 E('10-15',2,'65.00','E111',"Dinner, two attorneys, Dunsmere",hn="65.00 a person, which is exactly the meal cap"),
 E('10-15',1,'25.00','E109',"Parking, mediation center",receipt='no',hn="no receipt; the document requires one for a cost 'exceeding' 25.00, and this is exactly 25.00"),
 E('10-15',1,'26.50','E109',"Taxi from station to mediation center",receipt='no',v=[('expense_receipt_threshold','26.50 with no receipt; receipts needed above 25.00','medium')]),
 E('10-20',1,'1500.00','E119',"Biomedical engineer, initial consultation"),
]))
# ---------------------------------------------------------------- Coldwater Fen 2
INV.append(dict(id='INV-CFH-6602',client='coldwaterfen',matter='CFH-2026-B2',date='2026-11-13',start='2026-10-01',end='2026-10-31',rules=C,lines=[
 F('10-01','E41','0.9','L120','A106',"Advise chief medical officer on arbitration demand and coverage obligations"),
 F('10-02','E43','2.2','L210','A103',"Draft response to arbitration demand"),
 F('10-05','E43','2.7','L110','A102',"Research arbitrability of call-coverage stipend dispute",res=1,hn="research; approved on the matter record"),
 F('10-06','E43','2.8','L110','A102',"Research standards for interim relief from arbitrator",res=1,hn="research now totals 5.5 hours against a 4 hour limit, but research over the limit is approved on the matter record"),
 F('10-07','E42','1.4','L310','A103',"Draft information requests to physician group: call schedules, stipend invoices, and locum agency bills",hn="list after a colon; one task"),
 F('10-08','E44','0.6','L320','A104',"Tally unfilled call shifts by month from scheduling exports"),
 F('10-09','E41','1.3','L160','A106',"Meet with chief medical officer and compliance officer to review fair-market-value opinion",hn="one meeting with two people"),
 F('10-12','E42','2.3','L310','A104',"Review physician group's document production and prepare deposition outline for its administrator",v=[('block_billing','two tasks in one entry (review a production; prepare an outline); this client allows one','medium')]),
 F('10-13','E42','0.5','L230','A107',"Scheduling call with arbitrator and opposing counsel"),
 F('10-14','E44','1.25','L320','A103',"Redact patient identifiers from call logs",v=[('minimum_increment','1.25 hours is not a multiple of 0.1','easy')]),
 F('10-15','E42','3.6','L330','A109',"Take deposition of physician group's administrator"),
 F('10-16','E43','1.9','L330','A103',"Summarize administrator's deposition testimony on stipend calculations"),
 F('10-19','E42','0.8','L410','A101',"Prepare chief medical officer for arbitration testimony"),
 F('10-20','E41','1.0','L450','A109',"Travel to arbitration venue (half rate, approved)",rate='247.50',hn="travel at 50% of the approved rate, with travel approved on the matter record"),
 F('10-20','E41','6.5','L450','A109',"First-chair arbitration hearing, day one"),
 F('10-20','E44','6.5','L450','A109',"Run exhibits and realtime transcript at arbitration hearing, day one",hn="a paralegal at the hearing with one attorney; the document limits the number of attorneys, not paralegals. The rule parameters may not be able to express this (schema limit)",schema_limit=1),
 F('10-21','E41','6.0','L450','A109',"Arbitration hearing, day two",hn="first entry of a 10.5 hour day; this client's document sets no daily limit"),
 F('10-21','E41','4.5','L450','A103',"Draft closing brief outline after hearing day",hn="second entry of a 10.5 hour day; no daily limit for this client"),
 F('10-22','E43','3.3','L450','A103',"Draft post-hearing brief"),
 F('10-23','E42','1.6','L450','A103',"Revise post-hearing brief"),
 F('10-26','E41','0.4','L120','A106',"Report award timing to chief medical officer"),
 E('10-20',2,'225.00','E110',"Hotel near arbitration venue, 2 nights",hn="225.00 a night, which is exactly the lodging cap"),
 E('10-20',1,'71.00','E111',"Supper after hearing day one, R. Achterhof-Mensah",v=[('expense_per_diem','71.00 for one person against a 65.00 meal cap; described as supper','hard')]),
 E('10-21',1,'1880.00','E116',"Arbitration hearing transcript, two days"),
 E('10-20',1,'48.00','E109',"Car service to arbitration venue",receipt='no',v=[('expense_receipt_threshold','48.00 with no receipt; receipts needed above 25.00','easy')]),
 E('10-21',1,'3250.00','E124',"Arbitrator's fee deposit, Authority's share"),
]))
# ---------------------------------------------------------------- Nettlecombe 1
INV.append(dict(id='INV-NHL-8801',client='nettlecombe',matter='NHL-FC-77',date='2026-11-09',start='2026-10-01',end='2026-10-31',rules=N,lines=[
 F('08-25','G51','0.5','L120','A106',"Call with default servicing manager on borrower's counterclaims",ne=('NHL-LATE-01',"76 days old. The 60 day wish in the email is only proposed (not confirmed), so it must not produce a finding")),
 F('10-01','G52','2.6','L210','A103',"Draft answer to borrower's counterclaims for wrongful foreclosure"),
 F('10-02','G53','1.8','L110','A104',"Review loan origination file: note, deed of trust, assignments, and payment history",hn="list of documents after a colon; one task"),
 F('10-05','G52','0.3','L120','A105',"Internal conference with T. Lindahl-Eze on standing documents",hn="internal conference of exactly 0.3 hour, which is the limit"),
 F('10-05','G53','0.6','L120','A105',"Walked E. Mistry-Halloran through gaps in the assignment chain",v=[('internal_conference_limit','0.6 hour in-firm briefing against a 0.3 hour limit; no conference wording','hard')]),
 F('10-06','G53','2.2','L110','A102',"Research effect of unrecorded assignment on standing to foreclose",res=1),
 F('10-07','G53','1.9','L110','A102',"Research borrower's dual-tracking theory",res=1,hn="research totals 4.1 hours on the invoice, under the 5 hour limit"),
 F('10-08','G54','0.7','L320','A110',"Data entry of payment history into arrears spreadsheet",v=[('non_billable_task','clerical work (data entry)','easy')]),
 F('10-09','G52','1.4','L310','A103',"Respond to borrower's document requests, chase servicing notes from client, redline protective order",v=[('block_billing','three tasks in one 1.4 hour entry, separated by commas; threshold 0.3 hour','hard')]),
 F('10-12','G52','0.3','L310','A107',"Email borrower's counsel about inspection date; calendar it",hn="two small tasks at exactly 0.3 hour; the rule applies to entries over 0.3"),
 F('10-13','G51','0.4','L120','A104',"Attention to matter",v=[('vague_description','generic phrase','easy')]),
 F('10-14','G52','1.0','L310','A103',"Draft correspondence",v=[('vague_description','no object: to whom and about what','easy')]),
 F('10-15','G54','0.5','L320','A103',"Draft correspondence to title company requesting trustee's sale guarantee update",hn="starts with a generic phrase but names who and what"),
 F('10-16','G52','5.2','L330','A101',"Prepare servicing witness for deposition",hn="first entry of a 10.9 hour day, under the 11 hour limit"),
 F('10-16','G52','4.3','L240','A103',"Draft summary judgment declaration of servicing witness",hn="second entry of a 10.9 hour day, under the 11 hour limit"),
 F('10-16','G52','1.4','L320','A104',"Review borrower's bankruptcy schedules for inconsistent statements",hn="third entry of a 10.9 hour day, under the 11 hour limit"),
 F('10-19','G52','6.4','L330','A109',"Defend deposition of servicing witness"),
 F('10-19','G52','3.0','L250','A103',"Draft motion in limine on payment history exhibits"),
 F('10-19','G52','1.9','L340','A104',"Review borrower's expert disclosure on securitization audit",v=[('daily_hour_cap','G52 day total 11.3 hours on 2026-10-19 against an 11 hour limit; 0.3 hour of this entry is over','easy')]),
 F('10-19','G51','6.4','L330','A109',"Attend deposition of servicing witness"),
 F('10-19','G53','6.4','L330','A109',"Monitored deposition of servicing witness and handled exhibits",v=[('staffing_event_limit','third lawyer at a deposition; client pays for two. The word attend is not used. Any one of lines 17, 20 and 21 is acceptable as the flagged line','hard')],alt=[17,20]),
 F('10-20','G51','1.5','L330','A109',"Drive back from Ashgrove County courthouse after deposition",v=[('travel_time','travel billed at the full 430 rate; client pays 50%. The word travel is not used','hard')]),
 F('10-21','G51','1.0','L160','A109',"Travel to mandatory settlement conference (50%)",rate='215.00',hn="travel at 215.00, which is 50% of the 430.00 approved rate"),
 F('10-21','G51','2.2','L160','A109',"Mandatory settlement conference before Judge Pemberly-Osei",hn="a court conference, not an internal conference"),
 F('10-22','G54','0.9','L160','A103',"Prepare notice of trustee's sale postponement",rate='155.00',v=[('rate_above_card','billed at 155 against an approved 140','easy')]),
 F('10-23','G52','2.0','L250','A103',"Draft opposition to borrower's motion for preliminary injunction"),
 F('10-23','G52','2.0','L250','A103',"Draft opposition to borrower's motion for preliminary injunction",v=[('duplicate_entries','same as the entry before it','easy')]),
 F('10-26','G54','0.4','L110','A111',"Screened new co-borrower name against firm's client database before appearance",v=[('non_billable_task','conflicts check, described as what was done','hard')]),
 E('10-19',2,'39.00','E111',"Lunch at deposition, servicing witness and counsel",hn="two people at 39.00 each, under the 75.00 per person meal cap"),
 E('10-19',1,'82.00','E111',"Dinner, E. Mistry-Halloran, Ashgrove",v=[('expense_per_diem','82.00 for one person against a 75.00 meal cap','medium')]),
 E('10-19',1,'265.00','E110',"Hotel, Ashgrove, one night",v=[('expense_per_diem','265.00 a night against a 250.00 lodging cap','easy')]),
 E('10-19',1,'540.00','E115',"Transcript, servicing witness"),
 E('10-22',1,'17.60','E101',"In-house word processing charge for trustee's sale notices",v=[('expense_overhead','word processing','easy')]),
 E('10-23',1,'132.00','E107',"Same-day courier to trustee",cost='120.00',v=[('expense_markup','billed 132.00 against a cost of 120.00','easy')]),
]))
# ---------------------------------------------------------------- Nettlecombe 2
INV.append(dict(id='INV-NHL-8802',client='nettlecombe',matter='NHL-REG-12',date='2026-11-09',start='2026-10-01',end='2026-10-31',rules=N,lines=[
 F('10-01','G51','1.1','L120','A106',"Kickoff call with compliance officer on examiner's document request"),
 F('10-02','G52','2.4','L120','A104',"Review examiner's request list against servicing policies"),
 F('10-05','G53','3.0','L110','A102',"Research regulator's guidance on force-placed insurance notices",res=1),
 F('10-06','G53','2.5','L110','A102',"Survey of enforcement orders involving late fee pyramiding",res=1,v=[('research_approval','legal research reaches 5.5 hours (lines 3 and 4) against a 5 hour limit, no approval; this line does not use the word research (coded A102)','medium')]),
 F('10-07','G54','1.2','L320','A104',"Check 40 sample loan files for required force-placed insurance notices"),
 F('10-08','G52','1.6','L120','A103',"Draft narrative response on escrow analysis practices"),
 F('10-09','G52','0.9','L120','A103',"Draft narrative response on late fee practices"),
 F('10-12','G54','0.8','L320','A110',"Uploaded response exhibits to examiner's portal and labeled each file",v=[('non_billable_task','clerical file handling described as what was done','hard')]),
 F('10-13','G51','0.5','L120','A105',"Review call with P. Zubiri-Kane on draft responses",v=[('internal_conference_limit','0.5 hour in-firm call against a 0.3 hour limit','medium')]),
 F('10-14','G52','1.3','L120','A103',"Revise responses; escrow section; late fee section; insurance section",hn="one revising task described in parts with semicolons, over the 0.3 hour threshold"),
 F('10-15','G53','0.75','L120','A104',"Check sample notices against timing requirements",v=[('minimum_increment','0.75 hour is not a multiple of 0.1','easy')]),
 F('10-16','G51','0.9','L120','A106',"Various tasks relating to exam",v=[('vague_description','generic phrase','easy')]),
 F('10-19','G52','2.1','L120','A109',"Sit in on examiner's interview of collections supervisor"),
 F('10-20','G52','1.2','L120','A103',"Draft memo to compliance officer on interview takeaways"),
 F('10-21','G54','0.6','L110','A111',"Completed mandatory firm cybersecurity course",v=[('non_billable_task','training, described without the word','hard')]),
 F('10-22','G52','0.8','L120','A101',"Prepare for examiner exit meeting",hn="short, but names what was prepared for"),
 F('10-23','G51','1.4','L120','A109',"Exit meeting with examiners and compliance officer"),
 F('10-23','G51','0.7','L120','A109',"Travel to examiner's regional office for exit meeting",rate='215.00',hn="travel at 215.00, which is 50% of the 430.00 approved rate"),
 F('10-26','G52','1.7','L120','A103',"Draft corrective action letter"),
 F('10-27','G53','1.0','L120','A104',"Review revised late fee policy"),
 F('10-28','G51','0.3','L120','A106',"Email to compliance officer transmitting corrective action letter"),
 E('10-23',1,'64.00','E111',"Lunch, exit meeting day, E. Mistry-Halloran",hn="64.00 is under the 75.00 meal cap"),
 E('10-12',1,'19.50','E124',"Postage for hard-copy exhibit binders to examiner",v=[('expense_overhead','postage','easy')]),
 E('10-20',1,'410.00','E123',"Compliance consultant, sample testing"),
]))
MATTERS={"note":"Fictional matter records for held-out batch B: approved timekeepers, rate cards, approvals and budgets.","matters":[]}
def tkmap(cid,ids,over=None):
    o={}
    for i in ids:
        n,c,r=TK[cid][i]; o[i]={"name":n,"classification":c,"approved_rate":r,"last_billed_rate":r,"rate_notice_date":None}
    for k,v in (over or {}).items(): o[k].update(v)
    return o
def matter(cid,mid,name,ids,over=None,appr=None,budget=None):
    m={"client_id":cid,"name":name,"timekeepers":tkmap(cid,ids,over),"matter_id":mid,"approvals":{"research":False,"travel":False,"staffing":False}}
    m["approvals"].update(appr or {})
    if budget: m["budget"]=budget
    MATTERS["matters"].append(m)
matter('bramblewick','BFC-LIT-301','Cargo loss claim: refrigerated trailer',['D31','D32','D33','D34'],over={'D33':{"last_billed_rate":"340.00","rate_notice_date":"2026-07-20"}})
matter('bramblewick','BFC-LIT-318','Terminal lease holdover dispute',['D31','D32','D33','D34'],appr={"staffing":True})
matter('bramblewick','BFC-REG-044','Hours-of-service audit response',['D31','D32','D34'])
matter('coldwaterfen','CFH-2026-A4','Imaging equipment vendor dispute',['E41','E42','E43','E44'],budget='A4')
matter('coldwaterfen','CFH-2026-B2','Physician group contract arbitration',['E41','E42','E43','E44'],appr={"travel":True,"research":True},budget={"cap":"150000.00","billed_to_date":"41000.00"})
matter('nettlecombe','NHL-FC-77','Contested foreclosure: Ashgrove Lane property',['G51','G52','G53','G54'])
matter('nettlecombe','NHL-REG-12','Servicing complaint examination',['G51','G52','G53','G54'])
WAIVERS={"note":"Fictional client-approved exceptions for held-out batch B.","waivers":[{"waiver_id":"W-B01","client_id":"bramblewick","matter_id":"BFC-LIT-301","rule_id":"BFC-DAYCAP-01","timekeeper_id":"D32","invoice_id":"","line_no":None,"approved_by":"Claims manager, Bramblewick Freight Cooperative (fictional)","approved_on":"2026-10-09","reference":"Email of 2026-10-09, subject: long day for driver deposition","effective_from":"2026-10-13","expires_on":"2026-10-13","note":"Day over the daily limit approved for the 13 October driver deposition only."}]}
BATCH='batch_b'
KEYNOTE="Held-out batch B (sealed) for the billing-guideline check. Every planted violation in the seven invoices, written by hand by an independent test author who did not read the detector code. Fictional data."
LEDES_NOTE="INV-BFC-4403 is in the LEDES-style layout, which has no receipt, cost or AI flag. Receipt and mark-up rules cannot be checked on it, and AI rules can only use the narrative; a 'not checked' notice is expected and is not a finding."
NOTES={'BUDGET':"ceiling 120,000.00, billed to date 104,000.00, this invoice 17,521.75: the assignment goes 1,521.75 over the ceiling",
       'PHASE':"stage L100 allotment 30,000.00, billed to date 22,500.00, L1xx fee lines on this invoice 8,640.00: 1,140.00 over the stage allotment"}
BUDGETS={'A4':{"cap":"120000.00","billed_to_date":"104000.00","phases":{"L100":{"cap":"30000.00","billed_to_date":"22500.00"},"L300":{"cap":"45000.00","billed_to_date":"20000.00"}}}}
