"""Generate extractable CJK PDFs with MuPDF's embedded TrueType mapping."""
from pathlib import Path
import argparse, json, hashlib, random, csv
import fitz

def read_jsonl(p): return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()]
def esc(s): return str(s or '')
def choose(ps,n,seed):
 r=random.Random(seed); groups={}
 for p in ps: groups.setdefault(p.get('target_job_family',''),[]).append(p)
 out=[]
 for g in groups.values(): r.shuffle(g); out.extend(g[:1])
 rest=[p for g in groups.values() for p in g[1:]]; r.shuffle(rest); return (out+rest)[:n]
def make(profile,path,font):
 doc=fitz.open(); page=doc.new_page(width=595,height=842); y=48
 def line(value,size=10,leading=15):
  nonlocal page,y
  value=str(value or '')
  for chunk in [value[i:i+42] for i in range(0,len(value),42)] or ['']:
   if y>805: page=doc.new_page(width=595,height=842); y=42
   page.insert_text((48,y),chunk,fontfile=font,fontname='cjk',fontsize=size); y+=leading
 def add(title,text=''):
  nonlocal y
  if y>775: page=doc.new_page(width=595,height=842); y=42
   line(title,12,18)
  for part in str(text or '').splitlines(): line(part,10,15)
  y+=8
 line('个人简历',20,28); y+=18
 e=profile.get('education') or {}; skills=profile.get('skills_normalized') or profile.get('skills') or []
 add('基本信息','候选人：脱敏测试候选人\n教育背景：'+str(e.get('education',''))+'，'+str(e.get('degree',''))+'，'+str(e.get('major','')))
 summary='\n'.join(x for x in str(profile.get('summary','')).splitlines() if not x.startswith(('求职意向：','标准岗位：','岗位大族：','岗位系统技能画像：')))
 add('个人概述',summary); add('技能栈','、'.join(map(str,skills)))
 add('工作经历','\n'.join('相关岗位经历：'+ '；'.join(map(str,x.get('highlights') or [])) for x in profile.get('experience') or []))
 add('项目经历','\n'.join(str(x.get('project_name',''))+'：'+str(x.get('description',''))+'；技术栈：'+ '、'.join(map(str,x.get('tech_stack') or [])) for x in profile.get('projects') or []))
 doc.save(str(path)); doc.close()
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--limit',type=int,default=100); ap.add_argument('--output',type=Path,default=Path('artifacts/real_upload_matching_pack_v5_100')); ap.add_argument('--seed',type=int,default=20260903); a=ap.parse_args(); a.output.joinpath('resumes').mkdir(parents=True,exist_ok=True)
 ps={p['candidate_id']:p for p in read_jsonl(Path('artifacts/dataset_iteration_05/candidate_profiles.jsonl'))}; gold=list(csv.DictReader(open('artifacts/canonical_matching_review_v1/expert_gpt_cases.csv',encoding='utf-8-sig'))); first={}; acc={}
 for g in gold:
  cid=g['candidate_id']; first.setdefault(cid,g); acc.setdefault(cid,[]).extend(json.loads(g.get('gold_accepted_job_ids') or '[]'))
 chosen=choose([ps[c] for c in first if c in ps],a.limit,a.seed); font=r'C:\Windows\Fonts\simhei.ttf'; items=[]
 for i,p in enumerate(chosen,1):
  fn=f'UPLOAD-{i:03d}-{p["candidate_id"]}.pdf'; out=a.output/'resumes'/fn; make(p,out,font); g=first[p['candidate_id']]; items.append({'sample_id':f'UPLOAD-{i:03d}','candidate_id':p['candidate_id'],'pdf':f'resumes/{fn}','pdf_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'gold_role':g.get('gold_canonical_role_id'),'accepted_jd_ids':sorted(set(acc[p['candidate_id']]))})
 (a.output/'manifest.json').write_text(json.dumps({'version':'v5_pymupdf_extractable','samples':len(items),'items':items},ensure_ascii=False,indent=2)+'\n',encoding='utf8'); print(len(items))
if __name__=='__main__': main()
