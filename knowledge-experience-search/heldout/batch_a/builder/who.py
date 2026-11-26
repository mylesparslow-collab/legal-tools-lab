import csv,collections,re,json
B='/home/claude/legal-tools-lab/knowledge-experience-search/data/synthetic/'
ms={m['MatterNo']:m for m in csv.DictReader(open(B+'matters.csv'))}
ppl={p['UserId']:p for p in csv.DictReader(open(B+'people.csv'))}
team=list(csv.DictReader(open(B+'matter_team.csv')))
te=list(csv.DictReader(open(B+'time_entries.csv')))
hk=[k for k in te[0] if 'our' in k][0]; uk=[k for k in te[0] if 'User' in k or 'Timekeeper' in k][0]
hrs=collections.defaultdict(float)
for t in te: hrs[(t['MatterNo'],t[uk])]+=float(t[hk])
def topic(m): return re.search(r'centred on (.*)\.$',m['Description']).group(1)
W=[('A','WA1','own words','trust administration',lambda m:m['MatterType']=='trust administration','matter type is trust administration'),
('A','WA2','own words','wage claim defense',lambda m:m['MatterType']=='wage claim defense','matter type is wage claim defense'),
('A','WA3','different vocabulary: synonym','cybersquatting',lambda m:topic(m)=='domain name dispute','matter description is centred on domain name dispute'),
('A','WA4','different vocabulary: British lay phrasing','holiday let regulation',lambda m:topic(m)=='short-term rental ordinance','matter description is centred on short-term rental ordinance'),
('A','WA5','own words','subdivision map',lambda m:topic(m)=='subdivision map','matter description is centred on subdivision map'),
('A','WA6','different vocabulary: lay phrasing','lending against receivables and inventory',lambda m:topic(m)=='borrowing base' or m['MatterType']=='asset-based loan','matter is an asset-based loan or is centred on borrowing base'),
]
def analyse(f):
    mm=[m for m in ms.values() if f(m) and m['SecurityCode']=='P']
    hid=[m['MatterNo'] for m in ms.values() if f(m) and m['SecurityCode']!='P']
    agg=collections.defaultdict(lambda:{'lead':[], 'support':[], 'hours':0.0,'last':''})
    for t in team:
        if t['MatterNo'] in {m['MatterNo'] for m in mm}:
            a=agg[t['UserId']]; a['lead' if t['Role']=='L' else 'support'].append(t['MatterNo']); a['hours']+=hrs.get((t['MatterNo'],t['UserId']),0)
            m=ms[t['MatterNo']]; a['last']=max(a['last'],m['CloseDate'] or '9999-open',m['OpenDate'])
    return mm,hid,agg
if __name__=='__main__':
    print(te[0])
    for b,qid,var,q,f,why in W:
        mm,hid,agg=analyse(f)
        print('##',qid,q,'| matters',[(m['MatterNo'],m['OpenDate'][:4],(m['CloseDate'] or 'open')[:4]) for m in mm],'hidden',hid)
        for u,a in sorted(agg.items(),key=lambda kv:(-len(kv[1]['lead'])-len(kv[1]['support']),-kv[1]['hours']))[:9]:
            print('   %s %-22s %s %s lead=%s support=%s hours=%.0f last=%s'%(u,ppl[u]['FullName'],ppl[u]['Title'][:9],ppl[u]['Status'],a['lead'],a['support'],a['hours'],a['last']))
