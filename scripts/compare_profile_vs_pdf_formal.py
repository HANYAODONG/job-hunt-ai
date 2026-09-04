from pathlib import Path
import json,csv,time
import PyPDF2
from evaluate_canonical_matching_two_stage import read_jsonl,read_csv,build_role_classifier,rank_case,skill_set

ROOT=Path(__file__).resolve().parents[1]; pack=ROOT/'artifacts/real_upload_matching_pack_v3_100'; out=ROOT/'artifacts/real_upload_matching_eval_formal_v1_100'
items=json.loads((pack/'manifest.json').read_text(encoding='utf8'))['items']; profiles={p['candidate_id']:p for p in read_jsonl(ROOT/'artifacts/dataset_iteration_05/candidate_profiles.jsonl')}; jobs=[j for j in read_jsonl(ROOT/'artifacts/canonical_role_pool_v2/canonical_jobs.jsonl') if j.get('role_mapping_status')=='mapped']; role_map={r['source_standard_job']:r['role_id'] for r in read_csv(ROOT/'backend-src/app/data/canonical_role_pool/v1/source_role_mapping.csv')}; weights,_=build_role_classifier(list(profiles.values()),role_map)
vocab=set(); [vocab.update(map(str,p.get('skills_normalized') or p.get('skills') or [])) for p in profiles.values()]
def eval_one(skills,item):
 ranked,roles=rank_case(skill_set(skills),jobs,10,weights); role=roles[0]['canonical_role_id'] if roles else ''; acc=set(item.get('accepted_jd_ids') or []); return role==item['gold_role'], [any(x['job_id'] in acc for x in ranked[:k]) for k in (1,2,3)]
stats={'profile': [0,0,0,0], 'pdf': [0,0,0,0]}; rows=[]; start=time.perf_counter()
for item in items:
 p=profiles[item['candidate_id']]; a,h=eval_one(p.get('skills_normalized') or p.get('skills') or [],item); stats['profile'][0]+=a; stats['profile'][1:4]=[stats['profile'][i]+h[i-1] for i in range(1,4)]
 text='\n'.join(x.extract_text() or '' for x in PyPDF2.PdfReader(str(pack/item['pdf'])).pages).casefold(); extracted=[s for s in vocab if s.casefold() in text]; a2,h2=eval_one(extracted,item); stats['pdf'][0]+=a2; stats['pdf'][1:4]=[stats['pdf'][i]+h2[i-1] for i in range(1,4)]
 rows.append({'sample_id':item['sample_id'],'profile_role_hit':a,'pdf_role_hit':a2,'profile_jd_hits':h,'pdf_jd_hits':h2,'profile_skill_count':len(p.get('skills_normalized') or p.get('skills') or []),'pdf_skill_count':len(extracted)})
n=len(items); result={'samples':n,'profile':{k:round(v/n,4) for k,v in zip(['role_top1','jd_top1','jd_top2','jd_top3'],stats['profile'])},'pdf':{k:round(v/n,4) for k,v in zip(['role_top1','jd_top1','jd_top2','jd_top3'],stats['pdf'])},'elapsed_ms':round((time.perf_counter()-start)*1000,2)}
(out/'profile_vs_pdf_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(json.dumps(result,ensure_ascii=False,indent=2))
