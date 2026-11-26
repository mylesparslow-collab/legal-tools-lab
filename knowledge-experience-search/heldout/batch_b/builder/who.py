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
('B','WB1','own words','syndicated loan',lambda m:m['MatterType']=='syndicated loan','matter type is syndicated loan'),
('B','WB2','own words','trade secret dispute',lambda m:m['MatterType']=='trade secret dispute','matter type is trade secret dispute'),
('B','WB3','own words','tax controversy',lambda m:m['MatterType']=='tax controversy','matter type is tax controversy'),
('B','WB4','different vocabulary: lay phrasing','financing a building on leased land',lambda m:topic(m)=='ground lease financing','matter description is centred on ground lease financing'),
('B','WB5','different vocabulary: lay phrasing',"taxing a charity's side business income",lambda m:topic(m)=='unrelated business income','matter description is centred on unrelated business income'),
('B','WB6','different vocabulary: lay phrasing','adjusting duties for staff with disabilities',lambda m:topic(m)=='reasonable accommodation','matter description is centred on reasonable accommodation'),
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
