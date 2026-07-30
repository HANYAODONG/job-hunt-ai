import json
from pathlib import Path
from app.services.skill_extractor import SkillExtractor
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.models.job import Job, JobType, ExperienceLevel, Location, Salary
from datetime import datetime

se = SkillExtractor()
kg = KnowledgeGraphService()

def import_jobs_with_skills(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            job_id = data.get("job_id") or data.get("id")
            if not job_id:
                continue
            
            # 抽取技能
            skills = data.get("skills") or []
            if not skills:
                text = data.get("title", "") + " " + data.get("description", "")
                skills = se.extract(text)
                if not skills:
                    continue
            
            # 创建岗位节点
            job = Job(
                id=job_id,
                title=data.get("title", ""),
                description=data.get("description", ""),
                company_name=data.get("company") or data.get("company_name", "未知"),
                location=Location(city="北京", state="北京", country="中国"),
                job_type=JobType.FULL_TIME,
                experience_level=ExperienceLevel.ENTRY,
                salary=None,
                benefits=[],
                required_skills=skills,
                preferred_skills=[],
                responsibilities=[],
                requirements=[],
                posted_date=datetime.now(),
                remote_allowed=False,
                visa_sponsorship=False,
                source_url=None,
                job_family=data.get("job_family", ""),
                source="direct_import"
            )
            
            success = kg.create_job_node(job)
            if success:
                print(f"✅ {job.title} -> {skills[:5]}...")
            else:
                print(f"❌ {job.title} 失败")

if __name__ == "__main__":
    import_jobs_with_skills("/app/jobs.jsonl")