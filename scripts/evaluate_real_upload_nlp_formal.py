from pathlib import Path
import sys,json,time
import PyPDF2
try:
 import fitz
except ImportError:
 fitz = None
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'backend-src'))
from app.services.nlp_service import NLPService
from evaluate_canonical_matching_two_stage import read_jsonl,read_csv,build_role_classifier,rank_case,skill_set
from canonical_job_title import canonical_job_title
def main():
 pack=ROOT/'artifacts/real_upload_matching_pack_v6_100'; out=ROOT/'artifacts/real_upload_matching_eval_formal_v1_100'; out.mkdir(parents=True,exist_ok=True); items=json.loads((pack/'manifest.json').read_text(encoding='utf8'))['items']; profiles=read_jsonl(ROOT/'artifacts/dataset_iteration_05/candidate_profiles.jsonl'); jobs=[j for j in read_jsonl(ROOT/'artifacts/canonical_role_pool_v2/canonical_jobs.jsonl') if j.get('role_mapping_status')=='mapped']; by_id={str(j.get('job_id') or j.get('id') or ''):j for j in jobs}; rm={r['source_standard_job']:r['role_id'] for r in read_csv(ROOT/'backend-src/app/data/canonical_role_pool/v1/source_role_mapping.csv')}; weights,_=build_role_classifier(profiles,rm); nlp=NLPService(); rows=[]; start=time.perf_counter()
 def extract(path):
  if fitz:
   d=fitz.open(str(path)); value='\n'.join(page.get_text('text') for page in d); d.close(); return value
  return '\n'.join(p.extract_text() or '' for p in PyPDF2.PdfReader(str(path)).pages)
 for item in items:
  t=time.perf_counter(); text=extract(pack/item['pdf']); parsed=nlp.extract_candidate_profile(text); parse_ms=(time.perf_counter()-t)*1000; ranked,roles=rank_case(skill_set(parsed.get('skills')),jobs,10,weights); rid=roles[0]['canonical_role_id'] if roles else ''; acc=set(item.get('accepted_jd_ids') or []); accepted_titles={canonical_job_title(by_id[jid]) for jid in acc if jid in by_id}; id_hits=[any(x['job_id'] in acc for x in ranked[:k]) for k in (1,2,3)]; title_hits=[any(canonical_job_title(by_id.get(x['job_id'],x)) in accepted_titles for x in ranked[:k]) for k in (1,2,3)]; rows.append({'sample_id':item['sample_id'],'candidate_id':item['candidate_id'],'gold_role':item['gold_role'],'predicted_role':rid,'role_hit':rid==item['gold_role'],'jd_hit_at_1':id_hits[0],'jd_hit_at_2':id_hits[1],'jd_hit_at_3':id_hits[2],'title_hit_at_1':title_hits[0],'title_hit_at_2':title_hits[1],'title_hit_at_3':title_hits[2],'extracted_skills':parsed.get('skills',[]),'parse_ms':round(parse_ms,2),'total_ms':round((time.perf_counter()-t)*1000,2)})
 total=(time.perf_counter()-start)*1000; N=len(rows); result={'status':'completed','mode':'real_pdf_system_nlp_formal_two_stage','samples':N,'role_top1_accuracy':sum(x['role_hit'] for x in rows)/N,'jd_top1_recall':sum(x['jd_hit_at_1'] for x in rows)/N,'jd_top2_recall':sum(x['jd_hit_at_2'] for x in rows)/N,'jd_top3_recall':sum(x['jd_hit_at_3'] for x in rows)/N,'normalized_title_top1_recall':sum(x['title_hit_at_1'] for x in rows)/N,'normalized_title_top2_recall':sum(x['title_hit_at_2'] for x in rows)/N,'normalized_title_top3_recall':sum(x['title_hit_at_3'] for x in rows)/N,'total_ms':round(total,2),'average_total_ms':round(total/N,2),'average_parse_ms':round(sum(x['parse_ms'] for x in rows)/N,2),'average_nlp_skill_count':round(sum(len(x['extracted_skills']) for x in rows)/N,2),'metric_note':'JD ID metrics are strict record-level checks; normalized title metrics treat equivalent JD records under the same canonical job name as a hit.'}; (out/'nlp_case_metrics.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows)+'\n',encoding='utf8'); (out/'nlp_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
