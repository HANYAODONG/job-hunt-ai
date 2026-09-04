"""Evaluate the local two-stage matcher on the real PDF upload pack."""
from __future__ import annotations
import argparse, json, re, time
from pathlib import Path
from collections import defaultdict
import PyPDF2

def norm(s): return re.sub(r"[^\w\u4e00-\u9fff+#.]", "", str(s or "").casefold())
def toks(s): return {norm(x) for x in re.split(r"[,，;；、/|\s]+", str(s or "")) if norm(x)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pack',type=Path,default=Path('artifacts/real_upload_matching_pack_v3_100')); ap.add_argument('--jobs',type=Path,default=Path('artifacts/canonical_role_pool_v2/canonical_jobs.jsonl')); ap.add_argument('--roles',type=Path,default=Path('artifacts/canonical_role_pool_v2/canonical_roles.csv')); ap.add_argument('--out',type=Path,default=Path('artifacts/real_upload_matching_eval_v1_100')); args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((args.pack/'manifest.json').read_text(encoding='utf8'))['items']
    jobs=[]
    for line in args.jobs.read_text(encoding='utf8').splitlines():
        if not line.strip(): continue
        try: jobs.append(json.loads(line))
        except json.JSONDecodeError: continue
    by_role=defaultdict(list)
    for j in jobs: by_role[str(j.get('canonical_role_id') or '')].append(j)
    role_skills={r['role_id']: toks(r.get('role_definition','')+' '+r.get('core_boundary','')+' '+r.get('role_name','')) for r in __import__('csv').DictReader(open(args.roles,encoding='utf8')) if r.get('status')=='active'}
    rows=[]; started=time.perf_counter()
    for item in manifest:
        t0=time.perf_counter(); text='\n'.join(p.extract_text() or '' for p in PyPDF2.PdfReader(str(args.pack/item['pdf'])).pages); parse_ms=(time.perf_counter()-t0)*1000
        q=toks(text); role_scores=[]
        for rid, rs in role_skills.items():
            # Evidence-only role prediction: title/role words and skills; no gold fields.
            name=toks(next((j.get('canonical_role') for j in jobs if j.get('canonical_role_id')==rid),''))
            name_hit=len(q&name); skill_hit=sum(1 for j in by_role[rid][:30] for s in toks(' '.join(j.get('required_skills') or j.get('skills') or [])) if s in q)
            role_scores.append((name_hit*4+min(skill_hit,30)/10, rid))
        role_scores.sort(reverse=True); predicted=role_scores[0][1] if role_scores else ''
        ranked=[]
        for j in by_role.get(predicted,[]):
            js=toks(' '.join(j.get('required_skills') or j.get('skills') or [])); overlap=q&js
            # Required-skill coverage is the primary within-role signal.
            cov=len(overlap)/len(js) if js else 0; precision=len(overlap)/len(q) if q else 0
            title_bonus=1 if norm(j.get('canonical_role') or j.get('standard_job')) in norm(text) else 0
            ranked.append((0.65*cov+0.25*precision+0.1*title_bonus,j))
        ranked.sort(key=lambda x:(-x[0],str(x[1].get('job_id')))); top=[j for _,j in ranked[:10]]
        role_hit=predicted==item['gold_role']; accepted=set(item.get('accepted_jd_ids') or [])
        hits=[any(j.get('job_id') in accepted for j in top[:k]) for k in (1,2,3)]
        rows.append({'sample_id':item['sample_id'],'candidate_id':item['candidate_id'],'gold_role':item['gold_role'],'predicted_role':predicted,'role_hit':role_hit,'jd_hit_at_1':hits[0],'jd_hit_at_2':hits[1],'jd_hit_at_3':hits[2],'top_job_ids':[j.get('job_id') for j in top[:3]],'parse_ms':round(parse_ms,2),'total_ms':round((time.perf_counter()-t0)*1000,2),'candidate_count':len(by_role.get(predicted,[]))})
    total_ms=(time.perf_counter()-started)*1000
    result={'status':'completed','mode':'real_pdf_upload_local_two_stage','samples':len(rows),'role_top1_accuracy':sum(r['role_hit'] for r in rows)/len(rows),'jd_top1_recall':sum(r['jd_hit_at_1'] for r in rows)/len(rows),'jd_top2_recall':sum(r['jd_hit_at_2'] for r in rows)/len(rows),'jd_top3_recall':sum(r['jd_hit_at_3'] for r in rows)/len(rows),'total_ms':round(total_ms,2),'average_total_ms':round(total_ms/len(rows),2),'average_parse_ms':round(sum(r['parse_ms'] for r in rows)/len(rows),2),'cross_role_errors':sum(not r['role_hit'] for r in rows),'zero_hit_top1':sum(not r['jd_hit_at_1'] for r in rows),'notes':'Gold is used only after prediction for evaluation; PDFs omit canonical label fields.'}
    (args.out/'case_metrics.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf8'); (args.out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
