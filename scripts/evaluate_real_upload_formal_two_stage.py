"""Run the formal 400-case two-stage matcher after real PDF extraction."""
from __future__ import annotations
import argparse,csv,json,re,time
from pathlib import Path
import PyPDF2
from evaluate_canonical_matching_two_stage import read_jsonl,read_csv,build_role_classifier,rank_case,skill_set

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pack',type=Path,default=Path('artifacts/real_upload_matching_pack_v3_100')); ap.add_argument('--profiles',type=Path,default=Path('artifacts/dataset_iteration_05/candidate_profiles.jsonl')); ap.add_argument('--jobs',type=Path,default=Path('artifacts/canonical_role_pool_v2/canonical_jobs.jsonl')); ap.add_argument('--role-map',type=Path,default=Path('backend-src/app/data/canonical_role_pool/v1/source_role_mapping.csv')); ap.add_argument('--out',type=Path,default=Path('artifacts/real_upload_matching_eval_formal_v1_100')); args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((args.pack/'manifest.json').read_text(encoding='utf8'))['items']; profiles=read_jsonl(args.profiles); role_map={r['source_standard_job']:r['role_id'] for r in read_csv(args.role_map)}; weights,train=build_role_classifier(profiles,role_map)
    jobs=[]
    for line in args.jobs.read_text(encoding='utf8').splitlines():
        try:
            j=json.loads(line)
            if j.get('role_mapping_status')=='mapped': jobs.append(j)
        except json.JSONDecodeError: pass
    vocab=set()
    for p in profiles:
        vocab.update(str(x) for x in (p.get('skills_normalized') or p.get('skills') or []))
    rows=[]; start=time.perf_counter()
    for item in manifest:
        t0=time.perf_counter(); text='\n'.join(p.extract_text() or '' for p in PyPDF2.PdfReader(str(args.pack/item['pdf'])).pages); parse_ms=(time.perf_counter()-t0)*1000
        # Simulate the production extractor's normalized skill output by matching
        # only vocabulary present in the parsed PDF text.
        lower=text.casefold(); extracted=[s for s in vocab if s.casefold() in lower]; ranked,roles=rank_case(skill_set(extracted),jobs,10,weights); predicted_role=roles[0]['canonical_role_id'] if roles else ''; accepted=set(item.get('accepted_jd_ids') or []); hits=[any(x['job_id'] in accepted for x in ranked[:k]) for k in (1,2,3)]; rows.append({'sample_id':item['sample_id'],'candidate_id':item['candidate_id'],'gold_role':item['gold_role'],'predicted_role':predicted_role,'role_hit':predicted_role==item['gold_role'],'jd_hit_at_1':hits[0],'jd_hit_at_2':hits[1],'jd_hit_at_3':hits[2],'extracted_skill_count':len(extracted),'top_job_ids':[x['job_id'] for x in ranked[:3]],'parse_ms':round(parse_ms,2),'total_ms':round((time.perf_counter()-t0)*1000,2)})
    total=(time.perf_counter()-start)*1000; n=len(rows); result={'status':'completed','mode':'real_pdf_upload_formal_two_stage','samples':n,'training_profiles':train,'role_top1_accuracy':sum(x['role_hit'] for x in rows)/n,'jd_top1_recall':sum(x['jd_hit_at_1'] for x in rows)/n,'jd_top2_recall':sum(x['jd_hit_at_2'] for x in rows)/n,'jd_top3_recall':sum(x['jd_hit_at_3'] for x in rows)/n,'total_ms':round(total,2),'average_total_ms':round(total/n,2),'average_parse_ms':round(sum(x['parse_ms'] for x in rows)/n,2),'average_extracted_skill_count':round(sum(x['extracted_skill_count'] for x in rows)/n,2),'notes':'Uses the formal rank_case/build_role_classifier/score_job implementation from the 400-case evaluator; gold is used only after ranking.'}
    (args.out/'case_metrics.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows)+'\n',encoding='utf8'); (args.out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
