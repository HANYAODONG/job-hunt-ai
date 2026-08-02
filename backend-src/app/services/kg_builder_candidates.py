import logging
import json
import sys
from datetime import datetime
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.models.candidate import Candidate, Skill, Experience

logger = logging.getLogger(__name__)
kg_service = KnowledgeGraphService()


def load_candidates_from_jsonl(file_path):
    """从 JSONL 文件读取候选人数据"""
    candidates = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    candidates.append({
                        "candidate_id": data.get("candidate_id") or data.get("id", ""),
                        "name": data.get("name", "Unknown"),
                        "summary": data.get("summary") or data.get("profile_text", ""),
                        "skills": data.get("skills") or [],
                        "target_job_family": data.get("target_job_family", ""),
                        "location": data.get("preferred_location", ""),
                        "email": data.get("email", ""),
                        "years_experience": data.get("years_experience", 0)
                    })
        print(f"从 {file_path} 读取了 {len(candidates)} 个候选人")
        sys.stdout.flush()
        return candidates
    except Exception as e:
        print(f"读取候选人文件失败: {e}")
        sys.stdout.flush()
        return []


def create_candidate_with_skills(candidate_data):
    """创建一个候选人节点及其技能关系"""
    try:
        skill_objects = []
        for skill_name in candidate_data.get("skills", []):
            skill_objects.append(Skill(
                name=skill_name,
                level="intermediate",
                category="technical"
            ))
        
        candidate = Candidate(
            id=candidate_data["candidate_id"],
            name=candidate_data.get("name", "Unknown"),
            email=candidate_data.get("email", ""),
            location=candidate_data.get("location", ""),
            summary=candidate_data.get("summary", ""),
            skills=skill_objects,
            experience=[],
            education=[],
            certifications=[],
            languages=[],
            visa_status="",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            target_job_family=candidate_data.get("target_job_family", ""),
            years_experience=candidate_data.get("years_experience", 0)
        )
        
        success = kg_service.create_candidate_node(candidate)
        if success:
            print(f"候选人 {candidate.id} 创建成功，关联 {len(candidate.skills)} 个技能")
            sys.stdout.flush()
        return success
    except Exception as e:
        print(f"创建候选人失败: {e}")
        sys.stdout.flush()
        return False


def import_candidates(file_path):
    """全量导入候选人"""
    candidates = load_candidates_from_jsonl(file_path)
    if not candidates:
        print("没有候选人数据可导入")
        sys.stdout.flush()
        return
    
    total = len(candidates)
    batch_size = 100
    total_success = 0
    
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        print(f"正在导入第 {start+1} 到 {end} 条（共 {total} 条）")
        sys.stdout.flush()
        
        batch = candidates[start:end]
        for i, candidate in enumerate(batch):
            if create_candidate_with_skills(candidate):
                total_success += 1
            if (i + 1) % 10 == 0:
                print(f"已处理 {i+1}/{len(batch)} 条")
                sys.stdout.flush()
    
    print(f"全部导入完成，成功 {total_success}/{total} 个候选人")
    sys.stdout.flush()


if __name__ == "__main__":
    import_candidates("artifacts/dataset_iteration_05/candidate_profiles.jsonl")
