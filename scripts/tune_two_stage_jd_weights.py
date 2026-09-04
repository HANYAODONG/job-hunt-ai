from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'backend-src'))
from evaluate_canonical_matching_two_stage import read_jsonl,read_csv,build_role_classifier,skill_set,normalize_skill
items=json.loads((ROOT/'artifacts/real_upload_matching_pack_v6_100/manifest.json').read_text(encoding='utf8'))['items']; rows=[json.loads(x) for x in (ROOT/'artifacts/real_upload_matching_eval_formal_v1_100/nlp_case_metrics.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]; rowmap={x['sample_id']:x for x in rows}; profiles=read_jsonl(ROOT/'artifacts/dataset_iteration_05/candidate_profiles.jsonl'); jobs=[j for j in read_jsonl(ROOT/'artifacts/canonical_role_pool_v2/canonical_jobs.jsonl') if j.get('role_mapping_status')=='mapped']; rm={r['source_standard_job']:r['role_id'] for r in read_csv(ROOT/'backend-src/app/data/canonical_role_pool/v1/source_role_mapping.csv')}; weights,_=build_role_classifier(profiles,rm)
def score(q,j,w):
 req=skill_set(j.get('required_skills') or j.get('skills')); ov=q&req; rec=len(ov)/len(req) if req else 0; pre=len(ov)/len(q) if q else 0; f=2*rec*pre/(rec+pre) if rec+pre else 0; return w[0]*rec+w[1]*f+w[2]*pre
def run(w):
 h=[0,0,0]; role=0
 for it in items:
  q=skill_set(rowmap[it['sample_id']].get('extracted_skills',[])); scored=[]
  # Formal stage-one role classifier and role aggregation.
  by={}
  for j in jobs:
   s=score(q,j,w); by.setdefault(j.get('canonical_role_id'),[]).append((s,j))
  rr=[]
  for rid,vals in by.items():
   vals.sort(key=lambda x:-x[0]); rr.append((0.7*vals[0][0]+0.3*sum(x[0] for x in vals[:3])/len(vals[:3])+sum(max(0,weights.get(rid,{}).get(s,0)) for s in q),rid,vals))
  rr.sort(key=lambda x:-x[0]); pred=rr[0][1] if rr else ''; role+=pred==it['gold_role']; top=[j for _,j in sorted(rr[0][2],key=lambda x:-x[0])[:3]] if rr else []; acc=set(it.get('accepted_jd_ids') or [])
  for k in range(3): h[k]+=any(j.get('job_id') in acc for j in top[:k+1])
 return [role/len(items),* [x/len(items) for x in h]]
variants=[(0.6,0.25,0.1),(0.75,0.15,0.1),(0.8,0.1,0.1),(0.5,0.4,0.1),(0.45,0.25,0.3),(0.85,0.05,0.1),(0.7,0.2,0.1)]
result={str(v):run(v) for v in variants}; print(json.dumps(result,ensure_ascii=False,indent=2)); (ROOT/'artifacts/real_upload_matching_eval_formal_v1_100/jd_weight_tuning.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
