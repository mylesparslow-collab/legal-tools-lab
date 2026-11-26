import pickle,sys,collections,re
docs,ms,sub,own=pickle.load(open('prep.pkl','rb'))
CL={'AGR':'agreement','MEM':'memo','FRM':'form','OPN':'opinion letter','CHK':'checklist','BRF':'brief','MOT':'motion','RPT':'staff report'}
def cands(topic,cls=None,terms=None,minc=1):
    out=[]
    for d in docs:
        if d['sec']!='P': continue
        if cls and d['Class'] not in cls: continue
        tc=sum(d['terms'].get(t,0) for t in (terms or []))
        intitle=any(t in d['DocName'].lower() for t in (terms or []))
        if topic and d['topic']!=topic: 
            continue
        if terms and not (tc>=minc or intitle): continue
        out.append((d,tc,intitle))
    return out
def show(topic,cls=None,terms=None,minc=1,full=False):
    c=cands(topic,cls,terms,minc)
    print('### %s cls=%s terms=%s -> %d visible (hidden same-topic: %d)'%(topic,cls,terms,len(c),sum(1 for d in docs if d['topic']==topic and d['sec']!='P')))
    for d,tc,it in c:
        top=', '.join('%s:%d'%kv for kv in d['terms'].most_common(4))
        print(' %s %s %s v%s%s%s%s r%s %s| %s || %s%s'%(d['DocId'],d['MatterNo'],d['Class'],d['Version'],'F' if d['Final']=='Y' else 'd','*' if d['ModelForm']=='Y' else '',' fam'+d['FamilyNum'] if d['FamilyNum'] else '',d['ReuseCount'],d['EditDate'][:4],d['DocName'][:70],top[:90],(' tc=%d'%tc if terms else '')))
        if full: print('     ',d['Text'][:300].replace('\n',' '))
if __name__=='__main__':
    for a in sys.argv[1:]:
        p=a.split('|'); show(p[0] or None, p[1].split(',') if len(p)>1 and p[1] else None, p[2].split(',') if len(p)>2 and p[2] else None)
