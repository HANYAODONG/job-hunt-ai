"""
批量抽取技能脚本
从 jobs.jsonl 或 candidate_profiles.jsonl 中抽取技能并保存为 CSV
"""
import sys
import json
import csv
from pathlib import Path

# 将项目根目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.skill_extractor import SkillExtractor


def extract_from_jobs():
    """从岗位数据中抽取技能"""
    extractor = SkillExtractor()
    
    input_path = Path("artifacts/dataset_iteration_04/jobs.jsonl")
    output_path = Path("skills_output_jobs.csv")
    
    if not input_path.exists():
        print(f"文件不存在: {input_path}")
        return
    
    with open(input_path, 'r', encoding='utf-8') as f_in, \
         open(output_path, 'w', newline='', encoding='utf-8') as f_out:
        
        writer = csv.writer(f_out)
        writer.writerow(['job_id', 'title', 'extracted_skills', 'skill_count'])
        
        for line in f_in:
            job = json.loads(line)
            text = job.get('title', '') + ' ' + job.get('description', '')
            skills = extractor.extract(text)
            writer.writerow([
                job.get('job_id', ''),
                job.get('title', ''),
                ';'.join(skills),
                len(skills)
            ])
    
    print(f"完成！输出文件: {output_path}")


def extract_from_resumes():
    """从简历数据中抽取技能"""
    extractor = SkillExtractor()
    
    input_path = Path("artifacts/dataset_iteration_04/candidate_profiles.jsonl")
    output_path = Path("skills_output_resumes.csv")
    
    if not input_path.exists():
        print(f"文件不存在: {input_path}")
        return
    
    with open(input_path, 'r', encoding='utf-8') as f_in, \
         open(output_path, 'w', newline='', encoding='utf-8') as f_out:
        
        writer = csv.writer(f_out)
        writer.writerow(['candidate_id', 'summary', 'extracted_skills', 'skill_count'])
        
        for line in f_in:
            candidate = json.loads(line)
            text = candidate.get('summary', '') + ' ' + candidate.get('profile_text', '')
            skills = extractor.extract(text)
            writer.writerow([
                candidate.get('candidate_id', ''),
                candidate.get('summary', '')[:50] + '...',
                ';'.join(skills),
                len(skills)
            ])
    
    print(f"完成！输出文件: {output_path}")


if __name__ == "__main__":
    print("开始从岗位数据抽取技能...")
    extract_from_jobs()
    print("\n开始从简历数据抽取技能...")
    extract_from_resumes()
    print("\n全部完成！")