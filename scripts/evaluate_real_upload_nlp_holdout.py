"""80/20 holdout evaluation for the lightweight PDF->NLP->two-stage path."""
from pathlib import Path
import json,random,sys
import PyPDF2
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'backend-src'))
from app.services.nlp_service import NLPService
from evaluate_canonical_matching_two_stage import read_jsonl,read_csv,build_role_classifier,rank_case,skill_set

def main():
 pack=ROOT/'artifacts/real_upload_matching_pack_v3_100'; out=ROOT/'artifacts/real_upload_matching_eval_formal_v1_100'; items=json.loads((pack/'manifest.json').read_text(encoding='utf8'))['items']; rng=random.Random(20260903); rng.shuffle(items); dev,holdout=items[:80],items[80:]
 profiles=read_jsonl(ROOT/'artifacts/dataset_iteration_05/candidate_profiles.jsonl'); jobs=[j for j in read_jsonl(ROOT/'artifacts/canonical_role_pool_v2/canonical_jobs.jsonl') if j.get('role_mapping_status')=='mapped']; rm={r['source_standard_job']:r['role_id'] for r in read_csv(ROOT/'backend-src/app/data/canonical_role_pool/v1/source_role_mapping.csv')}; weights,_=build_role_classifier(profiles,rm); nlp=NLPService()
 def run(group):
  vals=[]
  for item in group:
   text='\n'.join(p.extract_text() or '' for p in PyPDF2.PdfReader(str(pack/item['pdf'])).pages); parsed=nlp.extract_candidate_profile(text); ranked,roles=rank_case(skill_set(parsed.get('skills')),jobs,10,weights); rid=roles[0]['canonical_role_id'] if roles else ''; acc=set(item.get('accepted_jd_ids') or []); vals.append((rid==item['gold_role'],*[any(x['job_id'] in acc for x in ranked[:k]) for k in (1,2,3)],len(parsed.get('skills') or [])))
  n=len(vals); return {'samples':n,'role_top1_accuracy':sum(x[0] for x in vals)/n,'jd_top1_recall':sum(x[1] for x in vals)/n,'jd_top2_recall':sum(x[2] for x in vals)/n,'jd_top3_recall':sum(x[3] for x in vals)/n,'average_skill_count':sum(x[4] for x in vals)/n}
 result={'protocol':'fixed 80/20 holdout','seed':20260903,'development':run(dev),'holdout':run(holdout),'notes':'No gold labels are passed to the parser or ranker; holdout is evaluated only after parsing/ranking.'}; (out/'holdout_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); (out/'holdout_manifest.json').write_text(json.dumps({'development_sample_ids':[x['sample_id'] for x in dev],'holdout_sample_ids':[x['sample_id'] for x in holdout]},ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
