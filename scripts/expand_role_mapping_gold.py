"""Screen the complete review queue for role-mapping review candidates.

This is a conservative, rule-adjudicated draft. It is deliberately marked as
requiring human sign-off; the rules are used to separate clear cases from
records that still need a reviewer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend-src"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.canonical_role_pool import CanonicalRolePool  # noqa: E402


DEFAULT_INPUT = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" / "role_mapping_review.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" / "role_mapping_gold_v2"
DEFAULT_SEED = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" / "role_mapping_gold_v1" / "role_mapping_gold_v1.jsonl"

EXCLUDE_TITLE = re.compile(
    r"客户经理|销售|采销|采购|商务拓展|核保|售后安装|维修培训|供应商管理|品类运营|类目运营|服务运营|用户增长产品运营|艺术产品专员|PMO|经营策略",
    re.IGNORECASE,
)
TECHNICAL_SECURITY = re.compile(
    r"安全|漏洞|渗透|攻防|(?<![A-Za-z])SOC(?![A-Za-z])|(?<![A-Za-z])SIEM(?![A-Za-z])|(?<![A-Za-z])WAF(?![A-Za-z])|(?<![A-Za-z])RASP(?![A-Za-z])|(?<![A-Za-z])EDR(?![A-Za-z])|应急响应|日志|云安全|代码审计|隐私",
    re.IGNORECASE,
)

NEW_ROLE_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("数据科学家", re.compile(r"数据科学家|AB实验|A/B测试|因果推断|统计建模|实验设计", re.I), "统计实验与因果建模是独立的数据科学交付"),
    ("地图数据工程师", re.compile(r"GIS|地图采集|地图数据|POI|道路拓扑|地图维护|地图质量", re.I), "地图采集、维护和质量评估构成独立的数据工程边界"),
    ("数据中心暖通工程师", re.compile(r"暖通|制冷|冷却|DCIM|PUE|机房空调|数据中心设施设计", re.I), "数据中心暖通制冷与能效交付不属于软件或服务器工程"),
    ("安全运营工程师", re.compile(r"(?<![A-Za-z])SOC(?![A-Za-z])|(?<![A-Za-z])SIEM(?![A-Za-z])|安全运营|应急响应|告警研判|(?<![A-Za-z])MTTD(?![A-Za-z])|(?<![A-Za-z])MTTR(?![A-Za-z])|安全监控", re.I), "SOC、SIEM、应急响应和安全运营构成独立能力边界"),
    ("安全治理运营工程师", re.compile(r"安全战略|安全文化|安全治理|风险治理|安全体系建设|安全项目交付", re.I), "安全治理与运营交付区别于安全研发和攻防"),
    ("导航定位算法工程师", re.compile(r"GNSS|INS|组合导航|导航定位|定位算法|多传感器定位", re.I), "导航定位与组合导航具有稳定的算法岗位边界"),
    ("游戏技术美术", re.compile(r"技术美术|Unity.*Shader|Shader.*Unity|美术工具链|渲染工具链", re.I), "Unity、Shader和美术工具链构成技术美术岗位"),
    ("智能硬件产品经理", re.compile(r"硬件产品经理|消费硬件产品|机器人产品规划|硬件产品规划|硬件.*上市", re.I), "硬件产品规划和上市管理不是硬件设计交付"),
    ("智能驾驶产品经理", re.compile(r"智能驾驶产品经理|NOA产品|智驾产品规划|自动驾驶产品", re.I), "智驾产品规划与量产管理不是算法研发"),
    ("隐私合规工程师", re.compile(r"隐私合规|PIA|DPIA|个人信息保护|数据隐私法规", re.I), "隐私法规、PIA/DPIA和合规治理构成独立岗位边界"),
    ("电磁兼容工程师", re.compile(r"EMC|电磁兼容|EMI整改|辐射抗扰度", re.I), "EMC测试整改具有独立工程边界"),
    ("业务架构师", re.compile(r"业务架构师|流程体系.*CRM|CRM.*SRM.*PLM|业务流程架构", re.I), "业务流程和企业系统整合以业务架构为主要交付"),
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def text_of(record: dict[str, Any]) -> str:
    values = [record.get("title"), record.get("description"), record.get("domain_context")]
    values.extend(record.get("skills") or [])
    return " ".join(str(value or "") for value in values).casefold()


def role_name(pool: CanonicalRolePool, role_id: str) -> str:
    role = pool.roles.get(role_id)
    return role.role_name if role else ""


def active_role(pool: CanonicalRolePool, role_id: str) -> bool:
    return bool(pool.roles.get(role_id) and pool.roles[role_id].status == "active")


def excluded(record: dict[str, Any], text: str) -> bool:
    title = str(record.get("title") or "")
    if not EXCLUDE_TITLE.search(title):
        return False
    # Security operations and technical support are technical when their JD
    # contains concrete security systems or engineering signals.
    if TECHNICAL_SECURITY.search(text):
        return False
    return True


def score_generic(pool: CanonicalRolePool, source: str, record: dict[str, Any], text: str) -> list[tuple[str, int]]:
    scores: Counter[str] = Counter()
    for rule in pool.refinement_rules.get(source, []):
        if rule.title_pattern.search(str(record.get("title") or "")):
            scores[rule.role_id] += 4
    for rule in pool.skill_refinement_rules.get(source, []):
        matches = sum(signal in text for signal in rule.signals)
        if matches >= rule.minimum_matches:
            scores[rule.role_id] += min(5, matches)

    if source == "算法工程师":
        extra = {
            "ml_algorithm": ("机器学习", "深度学习", "模型训练", "模型部署", "预测模型", "建模"),
            "algorithm_research": ("算法研究", "论文", "科研", "前沿研究", "原型验证"),
            "model_testing": ("模型评测", "模型测试", "benchmark", "评测指标"),
        }
    else:
        extra = {
            "backend_engineering": ("后端", "服务端", "微服务", "api", "分布式", "spring", "redis", "rpc"),
            "software_architecture": ("系统架构", "技术架构", "架构设计", "架构演进", "领域模型"),
            "data_engineering": ("数据管道", "etl", "hive", "spark", "flink", "kafka", "流批"),
            "frontend_engineering": ("前端", "react", "vue", "typescript", "浏览器", "html", "css"),
            "client_engineering": ("客户端", "ios", "android", "安卓", "flutter", "桌面端"),
            "system_software": ("操作系统", "编译器", "内核", "runtime", "sdk", "系统编程"),
            "embedded_software": ("嵌入式", "固件", "rtos", "单片机", "bsp"),
            "driver_software": ("驱动开发", "驱动程序", "内核模块", "硬件适配"),
            "hardware_engineering": ("电路", "原理图", "pcb", "单板", "硬件设计"),
            "test_development": ("自动化测试", "测试框架", "测试开发", "测试工具"),
        }
    for role_id, signals in extra.items():
        scores[role_id] += sum(signal.casefold() in text for signal in signals)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def adjudicate(pool: CanonicalRolePool, record: dict[str, Any]) -> dict[str, str]:
    source = str(record.get("source_standard_job") or record.get("standard_job") or "").strip()
    text = text_of(record)
    if excluded(record, text):
        return {"review_decision": "exclude_out_of_scope", "evidence": "标题和职责属于销售、采购、运营或非技术职能"}

    for name, pattern, evidence in NEW_ROLE_RULES:
        if pattern.search(text):
            if name == "安全运营工程师" and not re.search(
                r"安全|漏洞|渗透|攻防|告警|应急|WAF|RASP|EDR|云安全|代码审计|隐私",
                text,
                re.I,
            ):
                # SOC is also the common abbreviation for system-on-chip;
                # never infer a security role from that token alone.
                continue
            if name == "数据科学家" and not (
                re.search(r"数据科学家|AB实验|A/B测试|统计建模|实验设计", text, re.I)
                or (source in {"数据分析师", "数据工程师"} and re.search(r"因果推断", text, re.I))
            ):
                continue
            if name == "安全治理运营工程师" and source not in {
                "安全工程师", "网络安全工程师", "信息安全工程师", "AI安全工程师"
            }:
                continue
            if name == "隐私合规工程师" and not re.search(
                r"隐私合规|PIA|DPIA|个人信息保护|数据隐私法规|合规治理", text, re.I
            ):
                continue
            # Map-data and navigation roles share vocabulary with autonomous
            # driving. Only treat map work as a missing data role outside an
            # explicit algorithm/automotive source.
            if name == "地图数据工程师" and (source == "算法工程师" or "自动驾驶" in text or "智驾" in text):
                continue
            if name == "导航定位算法工程师" and source not in {"算法工程师", "自动驾驶算法工程师"}:
                continue
            if name in {"游戏技术美术"} and source not in {"软件开发工程师", "算法工程师"}:
                continue
            if name in {"数据中心暖通工程师", "电磁兼容工程师"} and source not in {"硬件工程师", "服务器工程师", "解决方案工程师", "软件开发工程师"}:
                continue
            # Existing canonical roles take precedence when the title is an
            # unmistakable active role; otherwise retain the missing-role signal.
            if name in {"安全运营工程师", "隐私合规工程师"} and source in {"安全工程师", "网络安全工程师", "信息安全工程师"}:
                break
            return {"review_decision": "new_role_candidate", "new_role_candidate_name": name, "evidence": evidence}

    if source in {"软件开发工程师", "算法工程师"}:
        scored = score_generic(pool, source, record, text)
        if scored and scored[0][1] >= 2 and (len(scored) == 1 or scored[0][1] > scored[1][1]):
            role_id = scored[0][0]
            if active_role(pool, role_id):
                return {
                    "review_decision": "replace_existing",
                    "final_canonical_role_id": role_id,
                    "evidence": f"通用来源标签由标题/职责唯一指向{role_name(pool, role_id)}",
                }
        return {"review_decision": "insufficient_evidence", "evidence": "通用岗位职责缺少唯一的功能边界或存在多个并列方向"}

    # A non-generic source with a concrete active mapping is acceptable unless
    # the title is clearly commercial (handled above).
    proposed = str(record.get("canonical_role_id") or "")
    if active_role(pool, proposed):
        return {"review_decision": "accept_proposal", "final_canonical_role_id": proposed, "evidence": "来源标签与职责边界一致，且对应正式激活岗位"}
    return {"review_decision": "insufficient_evidence", "evidence": "当前岗位池没有可验证的激活岗位映射"}


def build(input_path: Path, output_dir: Path, seed_path: Path | None = DEFAULT_SEED) -> dict[str, Any]:
    pool = CanonicalRolePool()
    source = read_jsonl(input_path)
    seed = {str(item.get("job_id")): item for item in read_jsonl(seed_path)} if seed_path and seed_path.exists() else {}
    output: list[dict[str, Any]] = []
    for record in source:
        seeded = seed.get(str(record.get("job_id") or ""))
        if seeded:
            # Preserve the first-round case-by-case adjudication exactly.
            output.append({**record, **{key: seeded.get(key, "") for key in (
                "review_decision", "final_canonical_role_id", "final_canonical_role",
                "final_domain", "final_direction", "new_role_candidate_name", "review_evidence",
            )}, "annotator_id": seeded.get("annotator_id", "codex_role_pool_adjudication"),
                "reviewed_at": seeded.get("reviewed_at", "2026-08-31"),
                "label_source": seeded.get("label_source", "codex_adjudicated_gold_draft"),
                "label_status": seeded.get("label_status", "requires_human_signoff_before_external_claims"),
            })
            continue
        result = adjudicate(pool, record)
        role_id = result.get("final_canonical_role_id", "")
        role = pool.roles.get(role_id)
        output.append({
            **record,
            "review_decision": result["review_decision"],
            "final_canonical_role_id": role_id,
            "final_canonical_role": role.role_name if role else "",
            "final_domain": role.domain if role else "",
            "final_direction": role.direction if role else "",
            "new_role_candidate_name": result.get("new_role_candidate_name", ""),
            "review_evidence": result["evidence"],
            "annotator_id": "codex_role_pool_adjudication_v2_rules",
            "reviewed_at": "2026-08-31",
            "label_source": "rule_screening_draft_v2",
            "label_status": "not_gold_requires_case_by_case_human_review",
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "role_mapping_gold_v2.jsonl"
    write_jsonl(path, output)
    report = {
        "label_type": "jd_to_role_screening_candidates",
        "label_source": "rule_screening_draft_v2",
        "label_status": "not_gold_requires_case_by_case_human_review",
        "input_records": len(source),
        "output_records": len(output),
        "decision_counts": dict(sorted(Counter(item["review_decision"] for item in output).items())),
        "accepted_existing_roles": len({item["final_canonical_role_id"] for item in output if item["final_canonical_role_id"]}),
        "new_role_candidates": dict(sorted(Counter(item["new_role_candidate_name"] for item in output if item["new_role_candidate_name"]).items())),
        "output": str(path),
    }
    (output_dir / "role_mapping_gold_v2_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen the review queue for role-mapping review candidates.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output_dir, args.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
