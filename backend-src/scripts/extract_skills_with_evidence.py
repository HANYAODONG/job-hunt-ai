"""技能证据链抽取脚本 — 产出 JD / 简历技能抽取样例（分工6 §4）

用法：
    # 抽取一段 JD 文本（默认关闭推断，仅保留有证据技能）
    python backend-src/scripts/extract_skills_with_evidence.py \
        --text "负责数据管道建设，要求 Python、SQL、Spark，熟悉 Machine Learning"

    # 从文件读取
    python backend-src/scripts/extract_skills_with_evidence.py --file resume.txt

    # 开启模型推断（演示降权与高阶技能拦截）
    python backend-src/scripts/extract_skills_with_evidence.py --text "做过 AI 项目" --allow-inference
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.skill_evidence_service import (
    SkillEvidenceService,
    HIGH_LEVEL_SKILLS,
)

# 演示用语义相似度函数（无真实模型时用规则模拟"模型推断"行为）
# 刻意模拟"过度联想"的模型：只要文本提到 AI/模型，就认为很多高阶技能也相关。
# 这样 --allow-inference 才能演示"高阶技能被拦截 + 推断降权"。
_DEMO_OVERCONFIDENT_SKILLS = {
    "机器学习", "深度学习", "大模型训练", "RLHF", "RAG", "Prompt Engineering",
}


def demo_semantic_similarity(skill: str, text: str) -> float:
    """模拟模型推断：文本含 AI/模型 时，对相关技能返回高相似度。"""
    text_cf = text.casefold()
    if "ai" in text_cf or "模型" in text:
        if skill in _DEMO_OVERCONFIDENT_SKILLS:
            return 0.9
    return 0.1


def run(text: str, allow_inference: bool, min_confidence: float) -> Dict:
    service = SkillEvidenceService()
    similarity_fn = demo_semantic_similarity if allow_inference else None
    report = service.extract_with_report(
        text,
        allow_inference=allow_inference,
        min_confidence=min_confidence,
        semantic_similarity_fn=similarity_fn,
    )
    report["input_text"] = text
    report["high_level_guard"] = sorted(HIGH_LEVEL_SKILLS)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="技能证据链抽取（分工6 §4）")
    parser.add_argument("--text", help="待抽取文本")
    parser.add_argument("--file", type=Path, help="从文件读取文本（UTF-8）")
    parser.add_argument("--allow-inference", action="store_true", help="开启模型推断（演示降权/拦截）")
    parser.add_argument("--min-confidence", type=float, default=0.5, help="最低置信度")
    parser.add_argument("--output", type=Path, help="输出 JSON 文件路径（可选）")
    args = parser.parse_args()

    if args.text:
        text = args.text
    elif args.file:
        text = args.file.read_text(encoding="utf-8")
    else:
        text = "负责大模型应用开发，要求 Python、FastAPI、RAG、Prompt Engineering，熟悉 Machine Learning"

    report = run(text, args.allow_inference, args.min_confidence)
    payload = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"报告已保存: {args.output}")

    print(payload)


if __name__ == "__main__":
    main()
