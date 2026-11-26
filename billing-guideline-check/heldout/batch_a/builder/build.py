import sys, json, importlib
from decimal import Decimal as D
from lib import build
name=sys.argv[1]; out=sys.argv[2]
b=importlib.import_module(name)
key,clean,hard,counts,notenf,report=build(out,b.YEAR,b.TK,b.INV,None,b.EXTRA)
print('\n'.join(report))
if '--write' in sys.argv:
    for k in key:
        if k['note'] in b.NOTES: k['note']=b.NOTES[k['note']]
    for m in b.MATTERS['matters']:
        if isinstance(m.get('budget'),str): m['budget']=b.BUDGETS[m['budget']]
    json.dump(b.MATTERS,open(out+'/matters.json','w'),indent=2)
    json.dump(b.WAIVERS,open(out+'/waivers.json','w'),indent=2)
    alt=[]
    for inv in b.INV:
        for l in inv['lines']:
            if 'alt' in l: alt.append(dict(invoice_id=inv['id'],line_no=l['no'],also_acceptable_lines=l['alt']))
    mnf={}
    for i,n in clean: mnf.setdefault(i,[]).append(n)
    K={"note":b.KEYNOTE,"batch":b.BATCH,"written":"By hand, before any tool run. The builder script only did the arithmetic and wrote the files from annotations typed next to each invoice line.",
       "extra_fields":{"difficulty":"easy = the narrative or data uses the obvious word or value; medium = ordinary wording a keyword list may or may not hold; hard = described as what was done, without the usual keyword, or a boundary value",
                       "alternate_lines":"for staffing_event_limit the document does not say which attendee is cut; a finding of that rule on any listed line counts as the planted one and is not a false positive, even though the line is also in must_not_flag for every other rule",
                       "must_not_flag":"every line with no planted violation, by invoice. A finding of any rule on these lines is a false positive, except invoice-level findings listed in planted with line_no null",
                       "invoice_files":"file name and layout of each invoice"},
       "invoice_files":{inv['id']:('invoices/%s.ledes.txt'%inv['id'] if inv.get('fmt')=='ledes' else 'invoices/%s.csv'%inv['id']) for inv in b.INV},
       "invoice_guidelines":{inv['id']:'guidelines/%s.json'%inv['client'] for inv in b.INV},
       "invoice_line_counts":counts,"planted":key,"alternate_lines":alt,"not_enforced":notenf,"hard_cases_clean":hard,"must_not_flag":mnf,"not_checkable_in_ledes":b.LEDES_NOTE}
    json.dump(K,open(out+'/ANSWER_KEY.json','w'),indent=1)
    print('planted',len(key),'clean lines',len(clean),'hard negatives',len(hard))
    import collections; print(collections.Counter(k['rule_type'] for k in key)); print(collections.Counter(k['difficulty'] for k in key))
