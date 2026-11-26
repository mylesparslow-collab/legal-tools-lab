import json,pickle,os
from pickdocs import pick, docs
from specs import A,B
import who
K='/home/claude/legal-tools-lab/knowledge-experience-search/heldout/'
EXP={ # test author's judgement of who should rank near the top: (strongest, other top people, also reasonable)
'WA1':(['U109'],['U111','U110'],['U112','U113']),
'WA2':(['U051'],['U050','U053'],['U049','U054']),
'WA3':(['U061'],['U063','U070'],['U069','U072']),
'WA4':(['U037'],['U042','U038'],['U041','U045']),
'WA5':(['U038'],['U044','U045'],['U037']),
'WA6':(['U074'],['U073','U075'],['U078','U080']),
}
for batch,specs,L in (('batch_a',A,'A'),('batch_b',B,'B')):
    qs=[]
    for s in specs:
        qid,cat,var,q,topic,dt,cls,terms,minc=s
        sel,rest,hid=pick(s)
        ids=[d['DocId'] for d in sel]
        other=sorted(d['DocId'] for d in docs if d['sec']=='P' and d['topic']==topic and d['DocId'] not in ids)
        e={"id":qid,"category":cat,"query":q,"as_user":"U102","topic":topic,"doc_type":dt,"relevant":sorted(ids),"variation":var}
        if terms: e["focus_terms"]=terms
        e["same_topic_not_listed"]=other
        how="main topic is '%s'"%topic
        if cls: how+=", document type is %s"%dt
        if terms: how+="; listed documents discuss %s as more than a passing mention"%(' / '.join(terms))
        e["judged_by"]=how
        qs.append(e)
    ex=[]
    for b,qid,var,q,f,why in who.W:
        if b!=L: continue
        mm,hid,agg=who.analyse(f)
        first,top,also=EXP[qid]
        def row(u):
            a=agg[u]; p=who.ppl[u]
            return {"user_id":u,"name":p['FullName'],"title":p['Title'],"lead_on":sorted(a['lead']),"support_on":sorted(a['support']),"hours_recorded":round(a['hours'],1)}
        ex.append({"id":qid,"query":q,"as_user":"U102","variation":var,"matter_rule":why,
                   "matters":sorted(m['MatterNo'] for m in mm),
                   "strongest":[row(u) for u in first],"should_rank_near_top":[row(u) for u in top],"also_reasonable":[row(u) for u in also]})
    key={"about":"Held-out %s for the knowledge and experience search. Relevance judged by hand by an independent test author who did not read the search code or the corpus generator and did not run the tool. Lists are NOT exhaustive: see heldout/README.md. Fictional data."%batch,
         "as_of":"2026-11-26","eval_user":"U102",
         "scoring":"Score precision at 5 and whether any listed document is in the top 10. A result that is not in 'relevant' is unjudged, not wrong; if it is in 'same_topic_not_listed' it is very likely relevant. Drafts and adapted copies count as their final or original, using the 'equivalents' map in data/synthetic/ANSWER_KEY.json.",
         "extra_fields":{"variation":"how the query differs from the documents' own words","focus_terms":"the narrower point the query is about, in the documents' words","same_topic_not_listed":"other documents U102 can open whose main topic is the same but which are not in 'relevant': either the list was capped at 10, or the document is a different type from the one asked for, or it mentions the focus point only in passing. Treat as unjudged.","judged_by":"the test the author applied when reading","experience_queries":"'who has done this' queries: the matters that justify the answer and the people the author judges should rank near the top"},
         "queries":qs,"experience_queries":ex}
    os.makedirs(K+batch,exist_ok=True)
    json.dump(key,open(K+batch+'/ANSWER_KEY.json','w'),indent=1)
    import collections
    print(batch,len(qs),collections.Counter(q['category'] for q in qs),'min/max listed',min(len(q['relevant']) for q in qs),max(len(q['relevant']) for q in qs),'who',len(ex))
