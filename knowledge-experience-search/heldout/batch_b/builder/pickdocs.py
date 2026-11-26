import pickle,sys,json,re
from specs import A,B
docs,ms,sub,own=pickle.load(open('prep.pkl','rb'))
def pick(spec):
    qid,cat,var,q,topic,dt,cls,terms,minc=spec
    pool=[d for d in docs if d['sec']=='P' and d['topic']==topic and (not cls or d['Class']==cls)]
    def tc(d): return sum(d['terms'].get(t,0) for t in terms)+sum(2 for t in terms if t in d['DocName'].lower()) if terms else 0
    if terms: strong=[d for d in pool if tc(d)>=minc]; 
    else: strong=pool
    def rank(d):
        named=topic.split(' and ')[0] in d['DocName'].lower()
        return (-(tc(d)) if terms else 0, d['Final']!='Y', 'adapted' in d['DocName'], not named, -int(d['ReuseCount']), d['DocId'])
    strong=sorted(strong,key=rank)
    sel=strong[:10]; rest=[d for d in pool if d not in sel]
    return sel,rest,len([d for d in docs if d['sec']!='P' and d['topic']==topic])
if __name__=='__main__':
    which=A if sys.argv[1]=='A' else B
    full='-f' in sys.argv
    for s in which:
        sel,rest,hid=pick(s)
        print('## %s [%s] %r -> %s | listed %d, other same-topic visible %d, hidden %d'%(s[0],s[2],s[3],s[4],len(sel),len(rest),hid))
        for d in sel:
            print('   %s %s %s%s | %s'%(d['DocId'],d['Class'],'F' if d['Final']=='Y' else 'd','*' if d['ModelForm']=='Y' else '',d['DocName'][:75]))
            if full: print('        '+d['Text'][:260].replace('\n',' '))
