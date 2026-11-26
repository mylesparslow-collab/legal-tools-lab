from lib import F,E
from common import rules
YEAR='2026'
TK={
 'harrowgate':{'A01':('Marisela Draycott-Obi','PT','325.00'),'A02':('Linus Achebe-Ferrand','AS','240.00'),'A03':('Petronella Vasquez-Holm','AS','215.00'),'A04':('Dov Lindgren-Okoro','LA','120.00'),'A05':('Wilhelmina Okpara-Stein','AS','230.00')},
 'marrowfen':{'B11':('Ignatius Corbel-Asante','PT','410.00'),'B12':('Solveig Marchetti-Dube','AS','295.00'),'B13':('Tamsin Okereke-Vance','AS','270.00'),'B14':('Rufus Delacroix-Imai','LA','150.00')},
 'pindlecroft':{'C21':('Henrike Solano-Brandt','PT','760.00'),'C22':('Obadiah Tran-Whitcombe','AS','520.00'),'C23':('Lucinda Mbatha-Rourke','AS','480.00'),'C24':('Ansel Petrov-Nwosu','LA','260.00')},
}
EXTRA={'A09':('Casimir Fontaine-Adeyemi','AS','240.00'),'B19':('Odalie Fenwick-Ruiz','LA','150.00')}
H=rules('HCE'); M=rules('MSD'); P=rules('PCR')
INV=[]
# ---------------------------------------------------------------- Harrowgate 1
INV.append(dict(id='INV-HCE-7001',client='harrowgate',matter='HCE-5521',date='2026-11-09',start='2026-10-01',end='2026-10-31',rules=H,lines=[
 F('08-20','A01','0.6','L120','A104',"Evaluate reservation-of-rights letter and coverage position before first report to adjuster",v=[('late_time','81 days old on the invoice date; limit 75','easy')]),
 F('08-26','A01','0.4','L120','A106',"Call with claims examiner on litigation plan and reserve recommendation",hn="exactly 75 days old on the invoice date; the document refuses work 'more than 75 days old', so this is inside the limit"),
 F('10-01','A02','1.3','L310','A103',"Prepare objections and answers to plaintiff's first interrogatories"),
 F('10-01','A04','0.7','L320','A110',"Paginated and numbered insured's driver logs for production",v=[('non_billable_task','clerical work (page numbering of a production) described as what was done','hard')]),
 F('10-02','A02','2.4','L240','A103',"Draft motion for partial summary judgment; argument on comparative fault; argument on statutory employer defense",hn="one drafting task described in parts with semicolons"),
 F('10-02','A01','0.3','L120','A105',"Discuss deposition sequencing with L. Achebe-Ferrand",v=[('internal_conference_limit','0.3 hour in-firm discussion against a 0.2 hour limit; the word conference is not used','medium')]),
 F('10-05','A01','3.2','L330','A109',"Take deposition of investigating trooper"),
 F('10-05','A02','3.2','L330','A109',"Second-chaired trooper's deposition and tracked exhibits",v=[('staffing_event_limit','second attorney at a deposition, no approval; either attendee line is acceptable as the flagged line','medium')],alt=[7]),
 F('10-05','A01','1.5','L330','A109',"Drive to and from Kessock for trooper deposition",v=[('travel_time','travel billed at the full 325 rate; client pays 50%. The word travel is not used','hard')]),
 F('10-06','A04','0.9','L320','A104',"Compare insured's maintenance invoices against repair history for gaps"),
 F('10-07','A02','1.6','L210','A102',"Look into whether a lessor of the tractor can be vicariously liable under the lease terms",res=1),
 F('10-08','A02','1.2','L210','A104',"Read and brief appellate decisions on negligent entrustment by motor carriers",res=1,v=[('research_approval','legal research reaches 2.8 hours (lines 11 and 12) against a 2.5 hour limit, no approval; neither line uses the word research and this one is coded A104','hard')]),
 F('10-08','A01','0.5','L160','A106',"Report to adjuster on settlement posture after trooper testimony"),
 F('10-09','A04','1.1','L320','A103',"Prepare privilege log: adjuster notes, counsel emails, and reserve worksheets",hn="list of documents after a colon; one task"),
 F('10-12','A02','2.7','L310','A103',"Finalize responses to requests for production, call the insured's safety director about missing inspection reports, and outline topics for corporate designee",v=[('block_billing','three tasks in one entry, joined by commas and and','medium')]),
 F('10-13','A03','1.4','L250','A103',"Draft motion to quash subpoena served on insured's telematics vendor",v=[('rate_increase_notice','215 billed, last billed 200; notice given 2026-09-01, so the 45 day period ran to 2026-10-16','medium')]),
 F('10-14','A02','0.25','L310','A107',"Email exchange with plaintiff's counsel on extension for discovery responses",v=[('minimum_increment','0.25 hour is not a multiple of 0.1','easy')]),
 F('10-15','A01','0.4','L120','A104',"Attention to file",v=[('vague_description','generic phrase the document itself quotes','easy')]),
 F('10-16','A04','0.8','L320','A104',"Follow up",v=[('vague_description','two words, no object','medium')]),
 F('10-19','A02','4.1','L330','A101',"Prepare corporate designee for deposition on driver hiring and training files",hn="the word training describes the insured's files, not law firm training; must not be flagged as non-billable"),
 F('10-19','A02','3.0','L340','A103',"Draft outline for deposition of plaintiff's accident reconstructionist"),
 F('10-19','A02','2.5','L340','A104',"Review telematics data export and mark speed and braking entries for expert",v=[('daily_hour_cap','A02 day total 9.6 hours on 2026-10-19 against a 9 hour limit; 0.6 hour of this entry is over','easy')]),
 F('10-20','A03','0.9','L250','A103',"Revise motion to quash after meet-and-confer with vendor's counsel",hn="A03's new rate billed after the 45 day notice period ended on 2026-10-16; allowed"),
 F('10-21','A01','1.0','L160','A106',"Walk claims examiner through verdict range and recommended authority"),
 F('10-21','A09','1.8','L310','A104',"Summarize plaintiff's medical chronology from treating records",v=[('unapproved_timekeeper','A09 is not on the approved list for the claim','easy')]),
 F('10-22','A02','1.1','L330','',"Review errata sheet for trooper deposition transcript",v=[('required_codes','activity code missing','easy')]),
 F('10-23','A04','0.6','L140','A110',"New-hire orientation on firm's document platform",v=[('non_billable_task','training','easy')]),
 F('10-26','A02','0.8','L330','A103',"Deposition notice for plaintiff's treating orthopedist"),
 F('10-26','A02','0.8','L330','A103',"Deposition notice for plaintiff's treating orthopedist",v=[('duplicate_entries','same as the entry before it','easy')]),
 F('10-27','A04','1.5','L330','A103',"Draft exhibit list for corporate designee deposition: hiring file, drug test records, and log audits",amount='190.00',v=[('ARITH-LINE','1.5 x 120 is 180.00, line says 190.00','easy')]),
 E('10-05',1,'412.80','E115',"Court reporter, trooper deposition transcript"),
 E('10-05',1,'38.50','E109',"Tolls and garage, Kessock (trooper deposition)",receipt='no',v=[('expense_receipt_threshold','38.50 with no receipt; receipts needed from 35.00','easy')]),
 E('10-05',1,'68.00','E111',"Lunch, M. Draycott-Obi, Kessock",v=[('expense_per_diem','68.00 for one person against a 55.00 daily food cap; the word meal is not used','medium')]),
 E('10-12',1,'14.20','E108',"Certified mail to telematics vendor",receipt='no',v=[('expense_overhead','postage, described as certified mail (expense code E108)','medium')]),
 E('10-20',1,'23.00','E109',"Parking near courthouse for motion hearing",receipt='no',hn="no receipt, but 23.00 is under the 35.00 receipt threshold"),
 E('10-22',1,'240.00','E118',"Records retrieval service, hospital records",cost='200.00',v=[('expense_markup','billed 240.00 against a cost of 200.00','easy')]),
]))
# ---------------------------------------------------------------- Harrowgate 2
INV.append(dict(id='INV-HCE-7002',client='harrowgate',matter='HCE-5604',date='2026-11-09',start='2026-10-01',end='2026-10-31',rules=H,
 inv_v=[('rounding_pattern','six of the seven A05 entries (86%) are multiples of 0.5 hour','A05','medium')],lines=[
 F('10-01','A01','0.7','L120','A106',"Initial evaluation letter to claims examiner with liability and exposure analysis"),
 F('10-02','A05','1.0','L310','A103',"Draft requests for production to plaintiff on prior injuries and footwear"),
 F('10-02','A04','0.6','L320','A104',"Review store surveillance footage and log timestamps of the fall and the last floor inspection",hn="one review task; the second verb (log) is part of the same review"),
 F('10-05','A05','2.5','L310','A103',"Draft answers to plaintiff's form interrogatories"),
 F('10-06','A02','0.4','L120','A105',"Conferred with W. Okpara-Stein and D. Lindgren-Okoro about sweep log gaps",v=[('internal_conference_limit','0.4 hour against a 0.2 hour limit','easy')]),
 F('10-06','A01','0.2','L120','A105',"Brief check-in with associate on sweep log gaps",hn="in-firm discussion of exactly 0.2 hour, which is the limit"),
 F('10-07','A05','0.5','L310','A107',"Letter to plaintiff's counsel requesting medical authorizations"),
 F('10-08','A04','1.3','L320','A110',"Scanned 140 pages of incident reports into the claim folder",v=[('non_billable_task','clerical work (scanning)','medium')]),
 F('10-09','A02','1.8','L330','A101',"Prepare store manager for deposition"),
 F('10-12','A05','3.0','L330','A109',"Defend deposition of store manager"),
 F('10-13','A02','0.9','L330','A104',"Deposition",v=[('vague_description','one word','medium')]),
 F('10-14','A05','1.5','L340','A104',"Review plaintiff's expert report on floor slip resistance testing"),
 F('10-15','A01','0.3','L160','A106',"Telephone call",v=[('vague_description','no object: who was called and about what','easy')]),
 F('10-15','A02','1.4','L210','A102',"Research notice requirements for transitory spills",res=1,hn="research, but 1.4 hours in total is under the 2.5 hour limit"),
 F('10-16','A04','0.5','L110','A111',"Ran conflicts search on newly identified janitorial subcontractor",v=[('non_billable_task','conflicts check, worded as conflicts search','medium')]),
 F('10-19','A05','2.0','L240','A103',"Draft motion for summary judgment on lack of constructive notice"),
 F('10-20','A02','0.5','L330','A109',"Travel to plaintiff's deposition (billed at half rate)",rate='120.00',hn="travel billed at 120.00, which is 50% of the 240.00 approved rate"),
 F('10-20','A02','4.6','L330','A109',"Take plaintiff's deposition"),
 F('10-22','A01','3.5','L160','A109',"Attend mediation with claims examiner"),
 F('10-22','A02','3.5','L160','A109',"Attend mediation as second chair at claims examiner's request",v=[('staffing_event_limit','second attorney at a mediation; client approved it, see waiver W-A01','easy','waived')]),
 F('10-23','A05','0.7','L160','A103',"Draft settlement agreement and release",hn="and is part of the document's name; one task"),
 F('10-26','A04','0.4','L140','A103',"Prepared and corrected September invoice at bill reviewer's request",v=[('non_billable_task','invoice preparation and correction','medium')]),
 F('10-27','A01','0.5','L160','A106',"Closing report to claims examiner"),
 E('10-12',1,'388.00','E115',"Certified transcript, store manager deposition"),
 E('10-20',1,'34.00','E109',"Parking garage, plaintiff's deposition",receipt='no',hn="no receipt, 34.00 is under the 35.00 threshold"),
 E('10-22',1,'35.00','E124',"Share of mediation suite charge",receipt='no',v=[('expense_receipt_threshold','35.00 with no receipt; the document requires receipts for charges of 35.00 or more, so the threshold itself is caught','hard')]),
 E('10-08',1,'45.00','',"Process server, subpoena on janitorial subcontractor",v=[('required_codes','expense code missing','easy')]),
 E('10-28',1,'27.50','E124',"Printer toner and binder tabs for mediation notebooks",v=[('expense_overhead','office supplies, described by the items bought','hard')]),
]))
# ---------------------------------------------------------------- Marrowfen 1
INV.append(dict(id='INV-MSD-3101',client='marrowfen',matter='MSD-2026-07',date='2026-11-12',start='2026-10-01',end='2026-10-31',rules=M,
 inv_v=[('staffing_matter_limit','five timekeepers (B11, B12, B13, B14, B19) on the invoice against a limit of four, no approval','','easy'),
        ('budget_cap','BUDGET','','easy'),('phase_cap','PHASE','','easy')],lines=[
 F('07-10','B11','1.1','L110','A109',"Site walk with District engineer at outfall headworks to photograph trench shoring conditions",v=[('late_time','125 days old on the invoice date; limit 120','easy')]),
 F('10-01','B11','0.8','L120','A106',"Advise District engineer on notice requirements before assessing liquidated damages"),
 F('10-02','B12','2.2','L310','A103',"Draft requests for production directed to contractor: daily logs, schedule updates, and subcontractor pay applications",hn="list of document categories after a colon; one task over the 1.5 hour threshold"),
 F('10-05','B13','1.8','L320','A104',"Review contractor's schedule updates for float consumption; critical path entries for June through August; weather day claims",hn="one review task with its parts separated by semicolons, over the 1.5 hour threshold"),
 F('10-06','B12','2.9','L310','A103',"Outline deposition questions for contractor's superintendent, telephone call with District inspector about pump bypass failures, and edit the litigation hold notice",v=[('block_billing','three tasks in one 2.9 hour entry; threshold 1.5 hours','easy')]),
 F('10-06','B14','0.4','L320','A108',"Email District clerk for board minutes; read the reply and calendar follow-up",hn="more than one task, but 0.4 hour is under this client's 1.5 hour threshold"),
 F('10-07','B11','2.5','L230','A109',"Round trip to Marrowfen for site meeting",v=[('travel_time','travel time with no approval on record for this matter; the word travel is not used','hard')]),
 F('10-08','B14','0.9','L320','A110',"Ran three copy sets of the bid documents and hand-carried one set to the expert's office",v=[('non_billable_task','clerical work (copying and delivery) described as what was done','hard')]),
 F('10-09','B12','1.25','L310','A103',"Revise requests for admission on substantial completion date",v=[('minimum_increment','1.25 hours is not a multiple of 0.1','easy')]),
 F('10-12','B13','1.6','','A103',"Draft declaration of District inspector on trench collapse",v=[('required_codes','task code missing','easy')]),
 F('10-13','B12','1.0','L350','A103',"Meet and confer letter on contractor's refusal to produce cost records",rate='310.00',v=[('rate_above_card','billed at 310 against an approved 295','easy')]),
 F('10-14','B19','2.0','L320','A104',"First-level review of contractor emails for responsiveness",v=[('unapproved_timekeeper','B19 is not listed in the fee schedule for this matter','easy')]),
 F('10-15','B13','6.5','L330','A109',"Defend deposition of District's construction manager",hn="12.4 hours for B13 on 2026-10-15 across two entries; this client's document sets no daily limit"),
 F('10-15','B13','5.9','L330','A103',"Draft summary of construction manager's deposition testimony for the District's board",hn="second entry of a 12.4 hour day; no daily limit for this client"),
 F('10-16','B14','0.7','L320','A104',"Tabulate contractor's change order requests by date and amount for damages analysis"),
 F('10-16','B14','0.7','L320','A104',"Tabulate contractor's change order requests by date and amount for damages analysis",v=[('duplicate_entries','same as the entry before it','easy')]),
 F('10-19','B11','1.4','L160','A107',"Settlement call with contractor's counsel and surety representative",hn="and joins two people on one call"),
 F('10-20','B12','3.4','L350','A103',"Draft motion to compel cost records"),
 F('10-21','B12','2.6','L350','A103',"Draft separate statement of disputed requests in support of motion to compel"),
 F('10-22','B13','1.9','L340','A108',"Work with scheduling expert on as-built schedule analysis"),
 F('10-23','B11','0.6','L120','A106',"Update General Manager on motion to compel and budget status"),
 F('10-26','B12','4.8','L350','A103',"Draft reply in support of motion to compel"),
 F('10-27','B11','2.0','L350','A109',"Argue motion to compel at hearing"),
 F('10-28','B13','3.0','L330','A109',"Take deposition of contractor's project scheduler"),
 F('10-29','B14','2.5','L320','A103',"Prepare production set of District inspection reports with redactions for personnel information"),
 E('10-07',1,'172.00','E110',"Hotel, one night, Marrowfen (site meeting)",v=[('expense_per_diem','172.00 a night against a 150.00 lodging cap','easy')]),
 E('10-07',1,'36.40','E111',"Dinner, I. Corbel-Asante, Marrowfen",hn="36.40 is under the 40.00 meal cap"),
 E('10-07',1,'20.00','E109',"Bridge toll and parking, site meeting",receipt='no',hn="no receipt; the document requires one only for a cost 'in excess of' 20.00, and this is exactly 20.00"),
 E('10-15',1,'645.00','E115',"Deposition transcript, construction manager"),
 E('10-22',1,'1850.00','E119',"Scheduling expert, October invoice"),
]))
# ---------------------------------------------------------------- Marrowfen 2
INV.append(dict(id='INV-MSD-3102',client='marrowfen',matter='MSD-2026-11',date='2026-11-12',start='2026-10-01',end='2026-10-31',rules=M,total_off='50.00',
 inv_v=[('ARITH-TOTAL','declared total is 50.00 more than the lines','','easy')],lines=[
 F('07-15','B11','0.9','L120','A104',"Review hauler's notice of price escalation and contract index clause",hn="exactly 120 days old on the invoice date; the document refuses time submitted 'more than' 120 days after the work"),
 F('10-01','B12','1.7','L120','A104',"Analyze termination-for-convenience clause and cure period mechanics"),
 F('10-02','B12','2.3','L210','A103',"Draft complaint for breach of hauling contract; causes of action for breach, declaratory relief, and account stated",hn="one drafting task with a semicolon and a list"),
 F('10-05','B14','1.4','L110','A104',"Calculate overcharges from hauler's scale tickets against contract tonnage rates"),
 F('10-06','B11','1.0','L160','A106',"Meet with General Manager and Operations Chief regarding interim hauling arrangements"),
 F('10-07','B12','1.5','L230','A109',"Travel to Marrowfen for case management conference (approved by General Counsel 9/28)",hn="travel time; travel is approved on the matter record"),
 F('10-07','B12','0.8','L230','A109',"Appear at case management conference"),
 F('10-08','B13','2.1','L310','A103',"Draft first set of interrogatories to hauler"),
 F('10-09','B13','1.9','L310','A103',"Prepare document requests, then phone District's records clerk about scale ticket archives, then update the discovery plan",v=[('block_billing','three tasks in one 1.9 hour entry, joined by then; threshold 1.5 hours','hard')]),
 F('10-12','B14','0.6','L320','A110',"Filed incoming correspondence and updated the pleadings binder",v=[('non_billable_task','clerical filing work described as what was done','hard')]),
 F('10-13','B12','1.5','L320','A104',"Review hauler's document production; note missing manifests",hn="arguably two tasks, but exactly 1.5 hours; the rule applies to entries 'exceeding' 1.5 hours"),
 F('10-14','B11','0.5','L120','A106',"Status",hn="one-word narrative, but this client's document has no rule on vague descriptions"),
 F('10-15','B12','3.6','L240','A103',"Draft opposition to hauler's demurrer"),
 F('10-16','B13','2.4','L240','A103',"Draft request for judicial notice of contract award resolution"),
 F('10-19','B12','1.1','L240','A103',"Revise opposition after General Counsel's comments"),
 F('10-20','B14','0.9','L240','A103',"Prepare table of contents and table of authorities for opposition"),
 F('10-22','B11','1.8','L240','A109',"Argue demurrer hearing"),
 F('10-22','B11','1.6','L240','A109',"Travel to and from courthouse for demurrer hearing",hn="approved travel, one task over 1.5 hours"),
 F('10-23','B11','0.4','L120','A106',"Report hearing result to General Manager"),
 F('10-26','B13','2.0','L310','A103',"Draft responses to hauler's first document requests"),
 F('10-27','B12','0.7','L160','A103',"Draft settlement proposal letter to hauler's counsel"),
 F('10-28','B13','1.3','L320','A104',"Review District board minutes approving hauling contract amendments"),
 E('10-07',1,'47.25','E111',"Lunch at Marrowfen, S. Marchetti-Dube",v=[('expense_per_diem','47.25 for one person against a 40.00 meal cap','medium')]),
 E('10-07',1,'45.00','E109',"Rideshare from rail station to courthouse",receipt='no',v=[('expense_receipt_threshold','45.00 with no receipt; receipts needed above 20.00','easy')]),
 E('10-22',1,'149.00','E110',"Lodging, one night, demurrer hearing",hn="149.00 is under the 150.00 lodging cap"),
 E('10-22',1,'88.00','E107',"Messenger service, courtesy copies to department",cost='80.00',v=[('expense_markup','billed 88.00 against a cost of 80.00','easy')]),
 E('10-13',1,'435.00','E112',"First appearance and motion fees"),
]))
# ---------------------------------------------------------------- Marrowfen 3 (LEDES)
INV.append(dict(id='INV-MSD-3103',client='marrowfen',matter='MSD-2026-15',date='2026-11-12',start='2026-10-01',end='2026-10-31',rules=M,fmt='ledes',desc='Professional services for October 2026',
 inv_v=[('staffing_matter_limit','five timekeepers (B11, B12, B13, B14, B19) on the invoice against a limit of four, no approval','','easy')],lines=[
 F('10-01','B11','0.6','L120','A106',"Advise on offer letter contents and appraisal summary statement"),
 F('10-02','B13','2.2','L120','A104',"Review appraisal of permanent and temporary construction easements"),
 F('10-05','B13','1.8','L210','A103',"Draft resolution of necessity for Board adoption"),
 F('10-06','B14','1.0','L110','A104',"Review litigation guarantee for parcels 4 and 7 and list lienholders to be named"),
 F('10-07','B12','0.75','L210','A103',"Revise notice of hearing to owners",v=[('minimum_increment','0.75 hour is not a multiple of 0.1','easy')]),
 F('10-08','B11','1.2','L160','A107',"Negotiate with owner's counsel on easement width and restoration terms"),
 F('10-09','B13','2.6','L210','A103',"Draft complaint in eminent domain, speak with title officer about the unrecorded utility license, and write to owner's counsel on possession date",v=[('block_billing','three tasks in one 2.6 hour entry; threshold 1.5 hours','medium')]),
 F('10-12','B11','1.9','L230','A109',"Windshield time to Fenlow for meeting with parcel 7 owner",v=[('travel_time','travel time (driving) with no approval on record for this matter; described as windshield time','hard')]),
 F('10-12','B11','1.5','L160','A109',"Meet with parcel 7 owner and tenant farmer at the property"),
 F('10-13','B14','0.8','L210','A103',"Prepare summons and lis pendens for filing"),
 F('10-14','B12','1.1','L210','A103',"Draft motion for order of prejudgment possession"),
 F('10-14','B12','1.1','L210','A103',"Draft motion for order of prejudgment possession",v=[('duplicate_entries','same as the entry before it','easy')]),
 F('10-15','B19','1.5','L110','A104',"Review county recorder index for easements of record on parcel 4",v=[('unapproved_timekeeper','B19 is not listed in the fee schedule for this matter','easy')]),
 F('10-16','B13','1.0','L210','A103',"Draft declaration of District engineer on project schedule",rate='285.00',v=[('rate_above_card','billed at 285 against an approved 270','easy')]),
 F('07-06','B11','0.5','L120','A106',"Initial call with District engineer on alignment alternatives",v=[('late_time','129 days old on the invoice date; limit 120. The entry is out of date order on the invoice','medium')]),
 F('10-19','B12','2.0','','A103',"Draft proposed order for possession",v=[('required_codes','task code missing','easy')]),
 F('10-20','B12','7.5','L210','A103',"Draft memorandum of points and authorities for possession motion",hn="11.7 hours for B12 on 2026-10-20 across two entries; no daily limit for this client"),
 F('10-20','B12','4.2','L210','A103',"Draft supporting declarations of appraiser and right-of-way agent",hn="second entry of an 11.7 hour day; no daily limit for this client"),
 F('10-22','B11','0.9','L160','A104',"Review owner's counteroffer and appraisal critique"),
 F('10-26','B13','1.4','L210','A103',"Revise complaint after title update"),
 F('10-27','B14','0.7','L210','A103',"Draft proof of service declarations for owners and lienholders"),
 E('10-12',1,'165.00','E110',"Overnight stay, Fenlow Inn",v=[('expense_per_diem','165.00 a night against a 150.00 lodging cap; neither hotel nor lodging is used','hard')]),
 E('10-14',1,'435.00','E112',"Complaint filing fee"),
 E('10-06',1,'350.00','E124',"Litigation guarantee, title company"),
]))
# ---------------------------------------------------------------- Pindlecroft 1
INV.append(dict(id='INV-PCR-9001',client='pindlecroft',matter='PCR-IP-22',date='2026-11-06',start='2026-10-01',end='2026-10-31',rules=P,inc='0.25',lines=[
 F('09-04','C21','0.5','L120','A106',"Call with general counsel on claim construction strategy",ai='no',v=[('late_time','63 days old on the invoice date; limit 60','easy')]),
 F('09-07','C22','1.25','L210','A103',"Draft claim chart for the asserted claims of the '114 patent",ai='no',hn="exactly 60 days old on the invoice date; the memo refuses time 'older than 60 days'"),
 F('10-01','C22','2.5','L210','A103',"Draft invalidity contentions for the '114 patent (GenAI)",ai='yes',hn="AI-assisted, disclosed with the client's marker, and not a task the client refuses to pay for"),
 F('10-02','C23','1.75','L320','A104',"Used the firm's AI assistant to digest the Okafor and Lindqvist deposition transcripts (GenAI)",ai='yes',v=[('ai_nonpayable_task','AI-produced deposition summaries, which the client will not pay for; worded as digest. Disclosure marker is present, so no disclosure finding','hard')]),
 F('10-02','C24','2.0','L320','A104',"Second-level privilege review of engineering emails",ai='yes',v=[('ai_disclosure_required','time system flags the entry as AI-assisted and the narrative has no (GenAI) marker','easy')]),
 F('10-05','C22','1.5','L210','A103',"Outline non-infringement positions with help from a large language model drafting tool",v=[('ai_disclosure_required','narrative says an AI tool was used; no (GenAI) marker; time-system flag blank','medium')]),
 F('10-06','C21','0.75','L120','A105',"Team meeting on claim construction positions",ai='no',v=[('internal_conference_limit','0.75 hour internal meeting against a 0.5 hour limit','medium')]),
 F('10-06','C22','0.75','L120','A101',"Huddle with H. Solano-Brandt and L. Mbatha-Rourke on claim construction positions",ai='no',v=[('internal_conference_limit','0.75 hour internal meeting against a 0.5 hour limit; called a huddle and coded A101','hard')]),
 F('10-07','C23','2.25','L210','A102',"Research claim preclusion effect of the earlier inter partes proceeding",ai='no',res=1),
 F('10-08','C23','2.0','L210','A102',"Survey district decisions on indefiniteness of functional claim language",ai='no',res=1),
 F('10-09','C23','2.25','L210','A104',"Dig into case law on prosecution history estoppel for amended claims",ai='no',res=1,v=[('research_approval','legal research reaches 6.5 hours (lines 9, 10 and 11) against a 6 hour limit, no approval; this line does not use the word research and is coded A104','hard')]),
 F('10-12','C22','3.0','L210','A103',"Draft opening claim construction brief; section on 'compliant member'; section on 'actuation signal'",ai='no',hn="one drafting task described in parts with semicolons"),
 F('10-13','C22','1.5','L210','A103',"Revise claim construction brief and circulate to client",ai='no',hn="two tasks; this client allows up to two in one entry"),
 F('10-14','C24','1.75','L210','A103',"Cite-check claim construction brief, prepare table of authorities, and e-file the brief with exhibits",ai='no',v=[('block_billing','three tasks in one 1.75 hour entry; client allows two','easy')]),
 F('10-15','C21','0.4','L230','A104',"Review court's scheduling order",ai='no',v=[('minimum_increment','0.4 hour is not a multiple of 0.25','medium')]),
 F('10-16','C22','0.5','L120','A103',"Work on matter",ai='no',v=[('vague_description','generic phrase with no object','easy')]),
 F('10-16','C24','0.25','L230','A110',"Docketing",ai='no',v=[('vague_description','one word','medium')]),
 F('10-19','C21','4.0','L230','A109',"Argue claim construction hearing",ai='no'),
 F('10-19','C22','4.0','L230','A109',"Attend claim construction hearing to present technology tutorial",ai='no'),
 F('10-19','C23','4.0','L230','A109',"Sat in on claim construction hearing to take notes",ai='no',v=[('staffing_event_limit','third lawyer at a hearing; client pays for two. The word attend is not used. Any one of lines 18 to 20 is acceptable as the flagged line','hard')],alt=[18,19]),
 F('10-20','C22','5.5','L330','A103',"Prepare H. Solano-Brandt's cross outline for inventor deposition",ai='no',hn="first entry of a 9.75 hour day, under the 10 hour limit"),
 F('10-20','C22','4.25','L320','A104',"Review source code production for actuation firmware modules",ai='no',hn="second entry of a 9.75 hour day, under the 10 hour limit"),
 F('10-21','C22','6.0','L320','A104',"Review source code production for gripper calibration routines",ai='no'),
 F('10-21','C22','4.5','L330','A103',"Draft exhibit-by-exhibit question list for inventor deposition",ai='no',v=[('daily_hour_cap','C22 day total 10.5 hours on 2026-10-21 against a 10 hour limit; 0.5 hour of this entry is over','easy')]),
 F('10-22','C21','1.0','L330','A101',"Prepare for inventor deposition",ai='no',rate='790.00',v=[('rate_above_card','billed at 790 against an approved 760','easy')]),
 F('10-23','C24','1.0','L330','A103',"Prepare deposition exhibit binders for inventor deposition",ai='no'),
 F('10-23','C24','1.0','L330','A103',"Prepare deposition exhibit binders for inventor deposition",ai='no',v=[('duplicate_entries','same as the entry before it','easy')]),
 F('10-26','C23','1.5','L320','A104',"Review documents produced by Tessaly Motion in response to subpoena",ai='no',hn="starts with a generic phrase but names what was reviewed"),
 F('10-27','C21','0.5','L160','A106',"Telephone call with general counsel regarding mediation timing",ai='no',hn="starts with a generic phrase but names who and what"),
 F('10-28','C22','2.0','L330','A109',"Fly to Port Almsley for inventor deposition",ai='no',ne=('PCR-TRAVEL-01',"travel time at full rate. The memo's travel wish is only proposed (not confirmed), so it must not produce a finding")),
 E('10-19',1,'95.00','E106',"Legal database charges, October",v=[('expense_overhead','online research subscription passed through; the word subscription is not used','hard')]),
 E('10-19',1,'1210.00','E116',"Hearing transcript, expedited",cost='1100.00',v=[('expense_markup','billed 1210.00 against a cost of 1100.00','easy')]),
 E('10-20',1,'310.00','E110',"Airfare, Port Almsley (inventor deposition)"),
 E('10-12',1,'60.00','E112',"Court filing fee, claim construction brief"),
]))
# ---------------------------------------------------------------- Pindlecroft 2
INV.append(dict(id='INV-PCR-9002',client='pindlecroft',matter='PCR-EMP-09',date='2026-11-06',start='2026-10-01',end='2026-10-31',rules=P,inc='0.25',lines=[
 F('10-01','C21','1.0','L120','A106',"Strategy call with general counsel and head of engineering",ai='no'),
 F('10-01','C23','2.75','L210','A103',"Draft complaint for misappropriation of motion-planning source code",ai='no'),
 F('10-02','C24','1.5','L110','A104',"Review forensic image report of former engineer's laptop: USB history, cloud uploads, and deleted folders",ai='no',hn="list after a colon; one task"),
 F('10-05','C23','1.25','L250','A103',"Edit chatbot-generated first draft of cease-and-desist letter to new employer",v=[('ai_disclosure_required','narrative says the first draft came from an AI chatbot; no (GenAI) marker; time-system flag blank','hard')]),
 F('10-05','C22','2.0','L250','A103',"Draft application for temporary restraining order (GenAI)",ai='yes',hn="AI-assisted, disclosed, and a payable task"),
 F('10-06','C24','3.0','L320','A104',"(GenAI) First-cut responsiveness review of 4,000 chat messages using the firm's review assistant",ai='yes',v=[('ai_nonpayable_task','AI first-level document review, which the client will not pay for; worded as first-cut responsiveness review. Marker is present','hard')]),
 F('10-06','C22','1.75','L250','A103',"Draft declaration of head of engineering in support of restraining order",ai='no'),
 F('10-07','C23','0.5','L120','A105',"Internal conference with O. Tran-Whitcombe on TRO evidence",ai='no',hn="internal conference of exactly 0.5 hour, which is the limit"),
 F('10-08','C22','1.0','L120','A105',"Discussion with paralegal about organizing forensic exhibits",ai='no',v=[('internal_conference_limit','1.0 hour internal discussion against a 0.5 hour limit','medium')]),
 F('10-08','C23','3.5','L250','A102',"Research standard for inevitable disclosure injunctions",ai='no',res=1,hn="research, but 3.5 hours in total is under the 6 hour limit"),
 F('10-09','C22','2.25','L250','A103',"Finalize TRO papers and coordinate filing with local counsel",ai='no',hn="two tasks; this client allows up to two in one entry"),
 F('10-12','C21','3.0','L250','A109',"Argue TRO application",ai='no'),
 F('10-12','C22','3.0','L250','A109',"Attend TRO hearing in support of H. Solano-Brandt",ai='no',hn="second lawyer at a hearing; this client pays for two"),
 F('10-13','C24','0.75','L320','A104',"Review file",ai='no',v=[('vague_description','generic phrase, no object','easy')]),
 F('10-14','C23','1.5','L310','A103',"Draft expedited discovery requests, negotiate forensic protocol with opposing counsel, and brief the client's IT lead on device collection",ai='no',v=[('block_billing','three tasks in one 1.5 hour entry; client allows two','medium')]),
 F('10-15','C22','0.9','L310','A104',"Review opposing party's proposed protective order",ai='no',v=[('minimum_increment','0.9 hour is not a multiple of 0.25','medium')]),
 F('10-16','C23','4.0','L330','A101',"Prepare outline for deposition of former engineer",ai='no'),
 F('10-19','C22','6.5','L330','A109',"Take deposition of former engineer",ai='no',hn="first entry of a day totalling exactly 10.0 hours; the memo questions 'more than 10'"),
 F('10-19','C22','3.5','L320','A104',"Review engineer's personal email production ahead of afternoon session",ai='no',hn="second entry of a day totalling exactly 10.0 hours"),
 F('10-20','C24','2.5','L250','A103',"Prepare exhibit set for preliminary injunction hearing",ai='no',rate='280.00',v=[('rate_above_card','billed at 280 against an approved 260','easy')]),
 F('10-21','C23','1.0','L250','A103',"Attention to preliminary injunction reply evidence",ai='no',hn="sounds vague but names its object; not the listed phrase"),
 F('08-28','C21','0.75','L110','A108',"Pre-suit call with outside forensic examiner on preservation steps",ai='no',v=[('late_time','70 days old on the invoice date; limit 60. Out of date order on the invoice','medium')]),
 F('10-22','C22','2.0','L120','A109',"Train ride to Port Almsley and back for meeting with client's engineers",ai='no',ne=('PCR-TRAVEL-01',"travel time at full rate. The travel rule is only proposed, so it must not produce a finding")),
 E('10-19',1,'980.00','E115',"Deposition transcript and video, former engineer"),
 E('10-12',1,'60.00','E124',"After-hours secretarial support for TRO filing",v=[('expense_overhead','staff overtime, described without the word overtime','hard')]),
 E('10-06',1,'2400.00','E118',"Forensic examiner, laptop imaging"),
 E('10-22',1,'84.00','E110',"Rail fare, Port Almsley",cost='70.00',v=[('expense_markup','billed 84.00 against a cost of 70.00','easy')]),
]))
MATTERS={"note":"Fictional matter records for held-out batch A: approved timekeepers, rate cards, approvals and budgets.","matters":[]}
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
matter('harrowgate','HCE-5521','Claim 5521, tractor-trailer collision, defense of insured carrier',['A01','A02','A03','A04'],over={'A03':{"last_billed_rate":"200.00","rate_notice_date":"2026-09-01"}})
matter('harrowgate','HCE-5604','Claim 5604, grocery store fall, defense of insured retailer',['A01','A02','A04','A05'])
matter('marrowfen','MSD-2026-07','Outfall replacement: contractor delay claim',['B11','B12','B13','B14'],budget='B07')
matter('marrowfen','MSD-2026-11','Biosolids hauling contract dispute',['B11','B12','B13','B14'],appr={"travel":True},budget={"cap":"40000.00","billed_to_date":"9800.00"})
matter('marrowfen','MSD-2026-15','Force main easement acquisition',['B11','B12','B13','B14'],budget={"cap":"25000.00","billed_to_date":"6000.00"})
matter('pindlecroft','PCR-IP-22','Gripper patent infringement suit',['C21','C22','C23','C24'])
matter('pindlecroft','PCR-EMP-09','Former controls engineer: trade secret claim',['C21','C22','C23','C24'])
WAIVERS={"note":"Fictional client-approved exceptions for held-out batch A.","waivers":[{"waiver_id":"W-A01","client_id":"harrowgate","matter_id":"HCE-5604","rule_id":"HCE-EVENT-01","timekeeper_id":"A02","invoice_id":"","line_no":None,"approved_by":"Senior claims examiner, Harrowgate Casualty Exchange (fictional)","approved_on":"2026-10-14","reference":"Email of 2026-10-14, subject: second attorney at mediation","effective_from":"2026-10-22","expires_on":"2026-10-22","note":"Second attorney approved for the 22 October mediation only."}]}
BATCH='batch_a'
KEYNOTE="Held-out batch A for the billing-guideline check. Every planted violation in the seven invoices, written by hand by an independent test author who did not read the detector code. Fictional data."
NOTES={'BUDGET':"cap 85,000.00, billed to date 68,000.00, this invoice 18,205.65: the matter goes 1,205.65 over the not-to-exceed amount",
       'PHASE':"phase L300 cap 30,000.00, billed to date 18,000.00, L3xx fee lines on this invoice 12,426.25: 426.25 over the phase allotment"}
BUDGETS={'B07':{"cap":"85000.00","billed_to_date":"68000.00","phases":{"L200":{"cap":"20000.00","billed_to_date":"12000.00"},"L300":{"cap":"30000.00","billed_to_date":"18000.00"}}}}
LEDES_NOTE="INV-MSD-3103 is in the LEDES-style layout, which has no receipt, cost or AI flag. Receipt and mark-up rules cannot be checked on it; a 'not checked' notice for those rules is expected and is not a finding."
