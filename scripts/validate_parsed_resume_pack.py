"""Validate data-group PDF parser JSONL before matching evaluation."""
import argparse,json
from pathlib import Path
REQUIRED=('sample_id','candidate_id','skills','experience','projects','education','years_experience')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('path',type=Path); args=ap.parse_args(); rows=[json.loads(x) for x in args.path.read_text(encoding='utf8').splitlines() if x.strip()]; errors=[]
 for i,r in enumerate(rows,1):
  miss=[k for k in REQUIRED if k not in r]
  forbidden=[k for k in ('target_job_family','canonical_role_id','gold_role','accepted_jd_ids') if k in r]
  if miss or forbidden: errors.append({'line':i,'missing':miss,'forbidden':forbidden})
 result={'rows':len(rows),'unique_candidate_ids':len({r.get('candidate_id') for r in rows}),'nonempty_skills':sum(bool(r.get('skills')) for r in rows),'errors':errors,'status':'passed' if len(rows)==100 and not errors else 'failed'}; print(json.dumps(result,ensure_ascii=False,indent=2));
if __name__=='__main__': main()
