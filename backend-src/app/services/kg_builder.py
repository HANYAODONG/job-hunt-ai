import logging
import json
from datetime import datetime
from pathlib import Path
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.models.job import Job, JobType, ExperienceLevel, Location, Salary

logger = logging.getLogger(__name__)
kg_service = KnowledgeGraphService()


def clear_graph():
    """清空Neo4j中的所有数据"""
    try:
        with kg_service.neo4j.get_session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("图谱已清空")
        return True
    except Exception as e:
        logger.error(f"清空图谱失败: {e}")
        return False


def create_job_with_skills(job_data):
    """
    创建一个岗位及其关联的技能
    job_data = {
        "job_id": "job_001",
        "title": "后端开发工程师",
        "description": "负责推荐算法、模型训练",
        "skills": ["Python", "SQL", "Machine Learning"],
        "company": "示例科技",
        "location": {"city": "北京", "state": "北京", "country": "中国"},
        "job_family": "算法工程师",
        "source": "jobs.jsonl"
    }
    """
    try:
        job = Job(
            id=job_data["job_id"],
            title=job_data["title"],
            description=job_data["description"],
            company_name=job_data.get("company", "示例科技"),
            location=Location(
                city=job_data.get("location", {}).get("city", "北京"),
                state=job_data.get("location", {}).get("state", "北京"),
                country=job_data.get("location", {}).get("country", "中国")
            ),
            job_type=JobType.FULL_TIME,
            experience_level=ExperienceLevel.ENTRY,
            salary=None,
            benefits=[],
            required_skills=job_data.get("skills", []),
            preferred_skills=[],
            responsibilities=[],
            requirements=[],
            posted_date=datetime.now(),
            remote_allowed=False,
            visa_sponsorship=False,
            source_url=None,
            job_family=job_data.get("job_family", ""),
            source=job_data.get("source", "jobs.jsonl")
        )
        
        success = kg_service.create_job_node(job)
        if success:
            logger.info(f"岗位 {job.title} 创建成功，关联 {len(job.required_skills)} 个技能")
        return success
    except Exception as e:
        logger.error(f"创建岗位失败: {e}")
        return False


def load_jobs_from_jsonl(file_path):
    """从 JSONL 文件读取岗位数据，返回岗位字典列表"""
    jobs = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    job = json.loads(line)
                    # 兼容不同字段名
                    jobs.append({
                        "job_id": job.get("job_id") or job.get("id", ""),
                        "title": job.get("title", ""),
                        "description": job.get("description", ""),
                        "skills": job.get("skills") or job.get("required_skills", []),
                        "company": job.get("company") or job.get("company_name", "未知公司"),
                        "location": job.get("location", {}) if isinstance(job.get("location"), dict) else {"city": "北京", "state": "北京", "country": "中国"},
                        "job_family": job.get("job_family", ""),
                        "source": job.get("source", "jobs.jsonl")
                    })
        logger.info(f"从 {file_path} 读取了 {len(jobs)} 个岗位")
        return jobs
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        return []


def get_sample_jobs():
    """返回示例数据（备用）"""
    return [
        {
            "job_id": "job_001",
            "title": "后端开发工程师",
            "description": "负责推荐算法、模型训练和数据分析",
            "skills": ["Python", "SQL", "Machine Learning"],
            "company": "示例科技",
            "location": {"city": "北京", "state": "北京", "country": "中国"},
            "job_family": "后端开发",
            "source": "sample"
        },
        {
            "job_id": "job_002",
            "title": "前端开发工程师",
            "description": "负责用户界面开发和交互设计",
            "skills": ["JavaScript", "React", "CSS"],
            "company": "示例科技",
            "location": {"city": "北京", "state": "北京", "country": "中国"},
            "job_family": "前端开发",
            "source": "sample"
        },
        {
            "job_id": "job_003",
            "title": "数据科学家",
            "description": "负责数据分析、建模和可视化",
            "skills": ["Python", "R", "TensorFlow", "Tableau"],
            "company": "示例数据",
            "location": {"city": "上海", "state": "上海", "country": "中国"},
            "job_family": "算法工程师",
            "source": "sample"
        },
        {
            "job_id": "job_004",
            "title": "DevOps工程师",
            "description": "负责CI/CD、容器化和云基础设施",
            "skills": ["Docker", "Kubernetes", "AWS", "Jenkins"],
            "company": "示例云",
            "location": {"city": "深圳", "state": "广东", "country": "中国"},
            "job_family": "运维工程师",
            "source": "sample"
        },
        {
            "job_id": "job_005",
            "title": "Java开发工程师",
            "description": "负责企业级应用开发和系统集成",
            "skills": ["Java", "Spring", "MySQL", "Redis"],
            "company": "示例金融",
            "location": {"city": "上海", "state": "上海", "country": "中国"},
            "job_family": "后端开发",
            "source": "sample"
        }
    ]


def build_sample_graph(file_path=None):
    """构建图谱，优先从 JSONL 文件读取数据"""
    jobs = []
    
    if file_path is None:
        # 尝试默认路径
        default_path = Path("artifacts/dataset_iteration_05/jobs.jsonl")
        if default_path.exists():
            file_path = str(default_path)
        else:
            logger.warning("未指定文件路径，使用示例数据")
    
    if file_path:
        jobs = load_jobs_from_jsonl(file_path)
    
    if not jobs:
        logger.warning("使用示例数据")
        jobs = get_sample_jobs()
    
    clear_graph()
    for job in jobs:
        create_job_with_skills(job)
    logger.info(f"图谱构建完成，共 {len(jobs)} 个岗位")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_sample_graph()
