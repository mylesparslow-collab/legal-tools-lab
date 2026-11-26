"""Builder for held-out billing invoices. Not the tool. Writes CSV / LEDES-style files and the
answer key from hand annotations on each line, and prints my own consistency checks."""
import csv, json, os, datetime, collections
from decimal import Decimal as D
HEAD='invoice_id,invoice_date,client_id,matter_id,invoice_total,billing_start,billing_end,line_no,kind,date,timekeeper_id,timekeeper_name,classification,units,rate,adjustment,amount,task_code,activity_code,expense_code,narrative,receipt,cost,ai_assisted'.split(',')
LH='INVOICE_DATE|INVOICE_NUMBER|CLIENT_ID|LAW_FIRM_MATTER_ID|INVOICE_TOTAL|BILLING_START_DATE|BILLING_END_DATE|INVOICE_DESCRIPTION|LINE_ITEM_NUMBER|EXP/FEE/INV_ADJ_TYPE|LINE_ITEM_NUMBER_OF_UNITS|LINE_ITEM_ADJUSTMENT_AMOUNT|LINE_ITEM_TOTAL|LINE_ITEM_DATE|LINE_ITEM_TASK_CODE|LINE_ITEM_EXPENSE_CODE|LINE_ITEM_ACTIVITY_CODE|TIMEKEEPER_ID|LINE_ITEM_DESCRIPTION|LAW_FIRM_ID|LINE_ITEM_UNIT_COST|TIMEKEEPER_NAME|TIMEKEEPER_CLASSIFICATION|CLIENT_MATTER_ID'
def q(x): return D(x).quantize(D('0.01'))
def F(date,tk,h,task,act,narr,**o): return dict(kind='fee',date=date,tk=tk,units=str(h),task=task,act=act,narr=narr,**o)
def E(date,units,unit,code,narr,receipt='yes',cost=None,**o): return dict(kind='expense',date=date,tk='',units=str(units),rate=str(unit),ecode=code,narr=narr,receipt=receipt,cost=cost,**o)
def build(batch_dir, year, TK, invoices, prefix, extra_names=None):
    names=dict(extra_names or {})
    key=[]; clean=[]; hard=[]; counts={}; notenf=[]; report=[]
    os.makedirs(batch_dir+'/invoices',exist_ok=True)
    for inv in invoices:
        rows=[]; total=D(0)
        cid=inv['client']; card=TK[cid]
        for i,l in enumerate(inv['lines'],1):
            l['no']=i
            d=l['date'] if len(l['date'])==10 else '%s-%s'%(year,l['date'])
            l['fdate']=d
            if l['kind']=='fee':
                tk=l['tk']; nm,cl,rt=card.get(tk) or names[tk]
                rate=D(str(l.get('rate',rt)))
            else:
                nm=cl=''; rate=D(l['rate'])
            units=D(l['units']); amt=q(units*rate)
            if 'amount' in l: amt=q(l['amount'])
            l['amt']=amt; l['r']=rate; total+=amt
            cost=l.get('cost'); 
            if l['kind']=='expense' and cost is None: cost=q(units*rate)
            rows.append(dict(line_no=i,kind=l['kind'],date=d,timekeeper_id=l['tk'],timekeeper_name=nm,classification=cl,units=l['units'],rate='%.2f'%rate,adjustment='0.00',amount='%.2f'%amt,task_code=l.get('task',''),activity_code=l.get('act',''),expense_code=l.get('ecode',''),narrative=l['narr'],receipt=l.get('receipt','') if l['kind']=='expense' else '',cost=('' if cost in (None,'') else '%.2f'%D(str(cost))) if l['kind']=='expense' else '',ai_assisted=l.get('ai','')))
            vs=l.get('v',[])
            for v in vs:
                rt_,note=v[0],v[1]; diff=v[2] if len(v)>2 else 'easy'; status=v[3] if len(v)>3 else 'open'
                rid=rt_ if rt_.startswith('ARITH') else inv['rules'][rt_]
                key.append(dict(invoice_id=inv['id'],line_no=i,timekeeper_id=l['tk'],rule_type=rt_,rule_id=rid,expected_status=status,note=note,difficulty=diff))
            if not vs or all(len(v)>3 and v[3]=='waived' for v in vs):
                if not vs: clean.append((inv['id'],i))
            if 'hn' in l:
                h=dict(invoice_id=inv['id'],line_no=i,note=l['hn'],narrative=l['narr'])
                if l.get('schema_limit'): h['schema_limit']=True
                hard.append(h)
            if 'ne' in l: notenf.append(dict(invoice_id=inv['id'],line_no=i,rule_id=l['ne'][0],note=l['ne'][1]))
        declared=total+D(str(inv.get('total_off','0')))
        for v in inv.get('inv_v',[]):
            rid=v[0] if v[0].startswith('ARITH') else inv['rules'][v[0]]
            key.append(dict(invoice_id=inv['id'],line_no=None,timekeeper_id=v[2] if len(v)>2 else '',rule_type=v[0],rule_id=rid,expected_status='open',note=v[1],difficulty=v[3] if len(v)>3 else 'easy'))
        counts[inv['id']]=len(rows)
        if inv.get('fmt')=='ledes':
            out=['LEDES1998B[]',LH+'[]']
            c=lambda s:s.replace('-','')
            for r in rows:
                typ={'fee':'F','expense':'E'}[r['kind']]
                f=[c(inv['date']),inv['id'],cid,inv['matter'],'%.2f'%declared,c(inv['start']),c(inv['end']),inv['desc'],str(r['line_no']),typ,r['units'],'0.00',r['amount'],c(r['date']),r['task_code'],r['expense_code'],r['activity_code'],r['timekeeper_id'],r['narrative'],'FIRM-EX01',r['rate'],r['timekeeper_name'],r['classification'],inv['matter']]
                assert all('|' not in x and '[]' not in x for x in f), f
                out.append('|'.join(f)+'[]')
            open('%s/invoices/%s.ledes.txt'%(batch_dir,inv['id']),'w').write('\n'.join(out)+'\n')
        else:
            with open('%s/invoices/%s.csv'%(batch_dir,inv['id']),'w',newline='') as fh:
                w=csv.DictWriter(fh,HEAD); w.writeheader()
                for r in rows:
                    r.update(invoice_id=inv['id'],invoice_date=inv['date'],client_id=cid,matter_id=inv['matter'],invoice_total='%.2f'%declared,billing_start=inv['start'],billing_end=inv['end']); w.writerow(r)
        # my own checks
        ls=inv['lines']; idate=datetime.date.fromisoformat(inv['date'])
        day=collections.defaultdict(D); tks=collections.defaultdict(list); ph=collections.defaultdict(D)
        for l in ls:
            if l['kind']=='fee':
                day[(l['tk'],l['fdate'])]+=D(l['units']); tks[l['tk']].append(D(l['units'])); ph[(l.get('task') or '??')[:2]]+=l['amt']
        rep=['== %s lines=%d sum=%s declared=%s'%(inv['id'],len(ls),total,declared)]
        rep.append(' fee by phase: '+', '.join('%s=%s'%(k,v) for k,v in sorted(ph.items())))
        rep.append(' timekeepers: '+', '.join('%s n=%d half=%d'%(k,len(v),sum(1 for x in v if x%D('0.5')==0)) for k,v in sorted(tks.items())))
        rep.append(' max days: '+', '.join('%s %s=%s'%(k[0],k[1][5:],v) for k,v in sorted(day.items(),key=lambda kv:-kv[1])[:4]))
        rep.append(' oldest ages: '+', '.join('L%d=%dd'%(l['no'],(idate-datetime.date.fromisoformat(l['fdate'])).days) for l in ls if (idate-datetime.date.fromisoformat(l['fdate'])).days>40))
        inc=D(inv.get('inc','0.1'))
        rep.append(' off-increment lines: '+', '.join('L%d'%l['no'] for l in ls if l['kind']=='fee' and D(l['units'])%inc!=0))
        rep.append(' research-tagged cum: '+', '.join('L%d'%l['no']+'+'+l['units'] for l in ls if l.get('res')))
        report.append('\n'.join(rep))
    return key,clean,hard,counts,notenf,report
