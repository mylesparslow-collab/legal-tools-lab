"""Writes the held-out RFP answer keys from hand-entered values. Exact requirement text and
source lines are copied out of the RFP file by start and end markers typed by hand; the script
checks that every quoted string really is in the document. It does not import the tool."""
import json,re,sys
P='/home/claude/legal-tools-lab/proposal-desk/heldout/'
def norm(s): return re.sub(r'\s+',' ',s).strip()
class Doc:
    def __init__(s,batch,name):
        s.batch=batch; s.name=name; s.raw=open(P+batch+'/rfps/'+name).read(); s.lines=s.raw.split('\n'); s.n=norm(s.raw)
    def grab(s,start,end,after=None):
        n=s.n; base=n.index(norm(after)) if after else 0
        i=n.index(norm(start),base); j=n.index(norm(end),i+len(norm(start)))
        return n[i:j].strip()
    def line(s,snip,nth=0):
        hits=[(k+1,l.strip()) for k,l in enumerate(s.lines) if snip in l]
        assert hits,(s.name,snip)
        return hits[nth]
    def has(s,t): assert norm(t) in s.n,(s.name,t); return t
def DL(d,kind,date,time,snip,nth=0,**x):
    ln,txt=d.line(snip,nth); o={"kind":kind,"date":date,"time":time,"source_line":txt,"source_line_no":ln}; o.update(x); return o
def RQ(d,label,qtype,section,start,end,numbered=True,after=None,**x):
    o={"label":label,"qtype":qtype,"section":section,"numbered":numbered,"text":d.grab(start,end,after)}; o.update(x); return o
def MQ(d,starts,kind,value,**x): d.has(starts); o={"starts":starts,"check_kind":kind,"value":value}; o.update(x); return o
def INS(d,contains,amount,val): d.has(contains); (amount and d.has(amount)); return {"contains":contains,"amount":amount,"amount_value":val}
def EV(d,name,w,**x): assert norm(name).lower() in d.n.lower(),(d.name,name); o={"name":name,"weight":w}; o.update(x); return o
def FM(d,names): [d.has(n) for n in names]; return names
def PT(d,rows): [d.has(n) for n,c in rows]; return [{"name":n,"category":c} for n,c in rows]
EXTRA={"source_line / source_line_no":"on each deadline: the line of the RFP file (stripped, 1-based number) that states the date in force. For a date changed by addendum it is the addendum line; original_source_line is the line in the body.",
 "section, numbered, text":"on each requirement: the section it sits in, whether the RFP gives it a number or label, and its exact text with runs of white space collapsed to one space (the label itself is left out).",
 "alt_labels, alt_qtypes":"other labels or question types that a scorer should also accept. Question types are the test author's judgement.",
 "deleted_requirements":"requirements removed by addendum. They must NOT appear in the parsed requirement list.",
 "evaluation_as_issued, forms_as_issued, before_addenda":"values before any addendum, for checking that the change is shown.",
 "addendum (on addendum_changes)":"which addendum made the change. Kinds beyond the existing keys: requirement_deleted, criterion_removed, weight_changed, insurance_changed, form_removed; time_from and time_to are given where an addendum changes the time of day.",
 "amount_value":"insurance amount as a whole number of dollars.",
 "dates_that_are_not_deadlines":"dates in the text that must not be read as schedule deadlines.",
 "not_requirements":"numbered or lettered items that are not proposal requirements (scope of services, general conditions, table of contents). Reading them as requirements is an error.",
 "kind_not_in_existing_keys":"marks a deadline kind the existing keys do not use; score it separately."}
def write(d,key):
    key={"rfp":d.name,**key,"extra_fields":EXTRA}
    out=P+d.batch+'/answer_keys/'+d.name.replace('.txt','.json')
    json.dump(key,open(out,'w'),indent=1)
    print(d.name,'deadlines',len(key['deadlines']),'reqs',len(key['requirements']),'numbered',sum(r['numbered'] for r in key['requirements']),'forms',len(key['forms']),'criteria',len(key['evaluation']),'mq',len(key['min_quals']),'ins',len(key['insurance']),'parties',len(key['parties']),'weights',sum(e['weight'] for e in key['evaluation']))
    if '-v' in sys.argv:
        for r in key['requirements']+key.get('deleted_requirements',[]): print('  ',r['label'],'|',r['qtype'],'|',r['text'][:70],'...',r['text'][-45:])
        for x in key['deadlines']: print('  ',x['kind'],x['date'],x['time'],'|',x['source_line_no'],x['source_line'][:80])
MK=["copies","format","packaging","delivery","not_accepted","page_limit","page_exclusions","font","margins"]
