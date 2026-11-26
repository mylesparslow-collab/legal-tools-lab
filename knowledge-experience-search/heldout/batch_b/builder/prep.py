import json,csv,collections,re,pickle
B='/home/claude/legal-tools-lab/knowledge-experience-search/data/synthetic/'
docs=[json.loads(l) for l in open(B+'documents.jsonl')]
ms={m['MatterNo']:m for m in csv.DictReader(open(B+'matters.csv'))}
pats=[r'addresses (.+?) in connection with',r'^Subject: (.+?)\. ',r'and concerns (.+?)\.',r'record the position on (.+?)\.']
exp={}
for d in docs:
    first=d['Text'].split('\n')[0]
    for p in pats:
        m=re.search(p,first)
        if m: exp[d['DocId']]=m.group(1); break
topics=collections.Counter(exp.values())
# subterms: phrases following template cues
cues=[r'worked example of (.+?) is included',r'language on (.+?) after comments',r'position on (.+?) is recorded',r'Open points on (.+?) are listed',r'principal issue is (.+?), with a secondary question about (.+?)\.',r'attention was given to (.+?) because of its effect on (.+?)\.',r'defined term for (.+?) was added to avoid inconsistency with (.+?)\.',r'whether (.+?) should be dealt with separately from (.+?) and kept',r'comments on (.+?) have been incorporated',r'treatment of (.+?) draws on',r'sign-off for (.+?) are allocated',r'call on (.+?) are attached',r'wording for (.+?)\.',r'approach on (.+?) are described',r'relying on (.+?)\.',r'treated (.+?) more briefly',r'explanation of (.+?) suitable',r'how (.+?) and (.+?) were handled',r'how (.+?) was presented',r'Where (.+?) interacts with (.+?),',r'relating to (.+?) were confirmed',r'relevant to (.+?) are summarised']
neg=[r'A related point on (.+?) is noted',r'For (.+?), see the separate document',r'does not cover (.+?), which']
def terms(t,cs):
    out=[]
    for c in cs:
        for m in re.finditer(c,t):
            out+= [g for g in m.groups()]
    return out
tt=collections.defaultdict(collections.Counter)
for d in docs:
    d['terms']=collections.Counter(terms(d['Text'],cues)); d['neg']=terms(d['Text'],neg)
    if d['DocId'] in exp:
        for k,v in d['terms'].items(): tt[exp[d['DocId']]][k]+=v
sub={t:[k for k,v in c.most_common() if v>=3] for t,c in tt.items()}
# distinctiveness: term belongs to topic with max count
own={}
allc=collections.defaultdict(dict)
for t,c in tt.items():
    for k,v in c.items(): allc[k][t]=v
for k,dct in allc.items():
    best=max(dct,key=dct.get)
    if dct[best]>=0.6*sum(dct.values()): own[k]=best
for d in docs:
    if d['DocId'] in exp: d['topic']=exp[d['DocId']]; d['how']='explicit'
    else:
        sc=collections.Counter()
        for k,v in d['terms'].items():
            if k in own: sc[own[k]]+=v
        tl=d['DocName'].lower()
        for t in topics:
            if t in tl: sc[t]+=5
        d['topic']=sc.most_common(1)[0][0] if sc else '?'; d['how']='inferred %s'%sc.most_common(2)
    d['sec']=ms[d['MatterNo']]['SecurityCode']
pickle.dump((docs,ms,sub,own),open('prep.pkl','wb'))
if __name__=='__main__':
    print(len(exp),len(topics))
    bt=collections.Counter(d['topic'] for d in docs)
    for t in sorted(sub): print(t,bt[t],'::',', '.join(k for k in sub[t] if own.get(k)==t))
    print(bt['?'])
