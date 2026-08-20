import logging
from fastapi import APIRouter
from collections import Counter
from app.services.knowledge_graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)
router = APIRouter()
kg_service = KnowledgeGraphService()

# 每个岗位族最多展示的岗位数（控制在总节点 1000 左右）
MAX_ROLES_PER_FAMILY = 10

# 岗位族 → 一级大类 映射表（9 个大类）
FAMILY_TO_DOMAIN = {
    # 1. 算法
    "算法工程师": "算法",
    "推荐算法工程师": "算法",
    "广告算法工程师": "算法",
    "搜索算法工程师": "算法",
    "控制算法工程师": "算法",
    "风控算法工程师": "算法",
    "数据挖掘算法工程师": "算法",
    "机器人算法工程师": "算法",
    "算法研究员": "算法",
    # 2. 大模型
    "大模型应用工程师": "大模型",
    "大模型算法工程师": "大模型",
    "多模态算法工程师": "大模型",
    "AIGC算法工程师": "大模型",
    "NLP算法工程师": "大模型",
    "语音算法工程师": "大模型",
    "计算机视觉算法工程师": "大模型",
    "机器学习算法工程师": "大模型",
    "AI应用工程师": "大模型",
    "AI安全工程师": "大模型",
    # 3. 后端
    "后端开发工程师": "后端",
    "Java开发工程师": "后端",
    "Python开发工程师": "后端",
    "Go开发工程师": "后端",
    "全栈开发工程师": "后端",
    "软件开发工程师": "后端",
    "系统软件工程师": "后端",
    "软件架构师": "后端",
    "音视频工程师": "后端",
    "图形图像工程师": "后端",
    # 4. 前端
    "前端开发工程师": "前端",
    "客户端开发工程师": "前端",
    "Android开发工程师": "前端",
    "iOS开发工程师": "前端",
    "移动开发工程师": "前端",
    # 5. 数据
    "数据分析师": "数据",
    "数据工程师": "数据",
    "数据开发工程师": "数据",
    "数据治理工程师": "数据",
    "数据平台工程师": "数据",
    "数据仓库工程师": "数据",
    "大数据开发工程师": "数据",
    # 6. 运维
    "运维工程师": "运维",
    "DevOps工程师": "运维",
    "云计算工程师": "运维",
    "网络工程师": "运维",
    "数据库工程师": "运维",
    "技术支持工程师": "运维",
    "解决方案工程师": "运维",
    "AI产品经理": "运维",
    # 7. 安全
    "网络安全工程师": "安全",
    "信息安全工程师": "安全",
    "安全工程师": "安全",
    # 8. 硬件
    "硬件工程师": "硬件",
    "嵌入式软件工程师": "硬件",
    "驱动开发工程师": "硬件",
    "芯片设计工程师": "硬件",
    "芯片验证工程师": "硬件",
    "芯片测试工程师": "硬件",
    "结构工程师": "硬件",
    "电源工程师": "硬件",
    "热设计工程师": "硬件",
    "服务器工程师": "硬件",
    "通信工程师": "硬件",
    # 9. 测试
    "测试开发工程师": "测试",
    "测试工程师": "测试",
    "大模型测试工程师": "测试",
    "质量工程师": "测试",

    "C++开发工程师": "后端",
    "AI Infra工程师": "运维",
    "自动驾驶算法工程师": "算法",
    "机器人软件工程师": "硬件",

    # 兜底：未分类的岗位族归到"其他"
    "未分类": "其他",
}


@router.get("/graph")
async def get_capability_graph():
    """
    从 Neo4j 查询岗位层级数据，组装成前端 GraphPage 需要的树形结构
    每个岗位族最多返回 10 个具体岗位，总节点控制在 1000 左右
    """
    try:
        with kg_service.neo4j.get_session() as session:
            query = """
            MATCH (j:Job)
            WHERE j.job_family IS NOT NULL AND j.job_family <> ''
            RETURN j.id AS id,
                   j.title AS title,
                   j.job_family AS job_family,
                   j.required_skills AS skills
            """
            result = session.run(query)
            records = list(result)

            if not records:
                logger.warning("图谱中没有找到岗位数据")
                return _empty_graph()

            families_map = {}
            roles = []

            for record in records:
                job_id = record.get("id")
                title = record.get("title") or job_id
                job_family = record.get("job_family") or "未分类"
                skills = record.get("skills") or []

                roles.append({
                    "id": job_id,
                    "label": title,
                    "type": "role",
                    "detail": f"{job_family} 岗位",
                    "count": 1,
                    "growth": "+0%",
                    "skills": skills[:5] if isinstance(skills, list) else []
                })

                if job_family not in families_map:
                    families_map[job_family] = []
                families_map[job_family].append(job_id)

            # 按 domain 分组
            domains_map = {}
            for family_name, job_ids in families_map.items():
                domain = FAMILY_TO_DOMAIN.get(family_name, "其他")
                if domain not in domains_map:
                    domains_map[domain] = {}
                domains_map[domain][family_name] = job_ids

            # 组装树形结构
            tree = {
                "id": "root",
                "label": "岗位银河",
                "type": "root",
                "count": len(roles),
                "growth": "+0%",
                "detail": f"当前图谱包含 {len(roles)} 个岗位，覆盖 {len(families_map)} 个岗位族，{len(domains_map)} 个岗位大类。",
                "skills": ["岗位分类", "能力映射", "动态演化"],
                "children": []
            }

            for domain_name, families in domains_map.items():
                domain_node = {
                    "id": f"domain_{domain_name}",
                    "label": domain_name if domain_name else "未命名大类",
                    "type": "domain",
                    "count": sum(len(job_ids) for job_ids in families.values()),
                    "growth": "+0%",
                    "detail": f"{domain_name}，包含 {len(families)} 个岗位族",
                    "skills": [],
                    "children": []
                }
                for family_name, job_ids in families.items():
                    family_roles = [r for r in roles if r["id"] in job_ids][:MAX_ROLES_PER_FAMILY]
                    family_node = {
                        "id": f"family_{family_name}",
                        "label": family_name if family_name else "未命名岗位族",
                        "type": "family",
                        "count": len(job_ids),
                        "display_count": len(family_roles),
                        "total": len(job_ids),
                        "growth": "+0%",
                        "detail": f"{family_name}，包含 {len(job_ids)} 个岗位（展示前 {len(family_roles)} 个）",
                        "skills": [],
                        "children": family_roles
                    }
                    domain_node["children"].append(family_node)
                tree["children"].append(domain_node)

            summary = {
                "domains": len(domains_map),
                "families": len(families_map),
                "roles": len(roles)
            }

            all_skills = []
            for role in roles:
                all_skills.extend(role.get("skills", []))
            skill_counter = Counter(all_skills)
            top_skills = [skill for skill, _ in skill_counter.most_common(10)]

            stacks = ["大模型技术栈", "数据智能技术栈", "智能终端技术栈"]
            if top_skills:
                if any('模型' in s or 'LLM' in s or 'Agent' in s for s in top_skills[:5]):
                    stacks.insert(0, "人工智能技术栈")

            return {
                "tree": tree,
                "summary": summary,
                "stacks": stacks,
                "jobs": [r["label"] for r in roles[:10]]
            }

    except Exception as e:
        logger.error(f"获取图谱数据失败: {e}")
        return _empty_graph()


def _empty_graph():
    return {
        "tree": {
            "id": "root",
            "label": "岗位银河",
            "type": "root",
            "count": 0,
            "growth": "+0%",
            "detail": "暂无岗位数据，请先导入岗位。",
            "skills": [],
            "children": []
        },
        "summary": {"domains": 0, "families": 0, "roles": 0},
        "stacks": [],
        "jobs": []
    }