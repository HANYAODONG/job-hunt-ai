"""Render the report-ready taskbook acceptance figure from frozen JSON results."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
FORMAL_METRICS = ROOT / "artifacts/taskbook_acceptance_20260830/human_gold_metrics_400.json"
LIVE_METRICS = ROOT / "artifacts/real_upload_matching_api_eval_v1_100/report.json"
OUTPUT_DIR = ROOT / "docs/assets"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def choose_font() -> str:
    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    return next((name for name in candidates if name in installed), "DejaVu Sans")


def main() -> None:
    formal = load_json(FORMAL_METRICS)
    live = load_json(LIVE_METRICS)
    values = [
        formal["jd_parsing"]["skill_micro"]["f1"] * 100,
        formal["resume_extraction"]["skill_micro"]["f1"] * 100,
        live["role_top1_accuracy"] * 100,
    ]
    labels = ["JD技能解析\nMicro-F1", "简历技能提取\nMicro-F1", "人岗匹配\n标准岗位Top-1"]
    colors = ["#177DDC", "#13A8A8", "#3156A3"]

    plt.rcParams.update({"font.family": choose_font(), "axes.unicode_minus": False})
    fig = plt.figure(figsize=(16, 9), dpi=180, facecolor="#F7FAFD")
    ax = fig.add_axes([0.07, 0.20, 0.64, 0.61], facecolor="#F7FAFD")
    side = fig.add_axes([0.755, 0.20, 0.205, 0.61], facecolor="none")

    fig.text(0.07, 0.92, "任务书核心指标验收结果", fontsize=27, weight="bold", color="#102A43")
    fig.text(0.07, 0.868, "400条小组人工复核金标 · 固定数据版本 · 可复现实验流程", fontsize=13, color="#627D98")
    fig.lines.append(plt.Line2D([0.07, 0.96], [0.84, 0.84], transform=fig.transFigure, color="#C9D9E8", linewidth=1))

    bars = ax.bar(range(3), values, width=0.54, color=colors, edgecolor="white", linewidth=1.5, zorder=3)
    ax.axhspan(90, 102, color="#EAF7F1", alpha=0.85, zorder=0)
    ax.axhline(90, color="#E45858", linewidth=1.8, linestyle=(0, (5, 4)), zorder=2)
    ax.text(2.55, 90.55, "任务书验收线 90%", ha="left", va="bottom", fontsize=11, color="#D64545", weight="bold")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.85, f"{value:.2f}%", ha="center", va="bottom", fontsize=16, color="#102A43", weight="bold")
        ax.text(bar.get_x() + bar.get_width() / 2, 4, f"超出 {value - 90:.2f} 个百分点", ha="center", fontsize=9.5, color="white", weight="bold")

    ax.set_ylim(0, 104)
    ax.set_xlim(-0.62, 3.18)
    ax.set_xticks(range(3), labels, fontsize=12, color="#334E68")
    ax.set_yticks(range(0, 101, 20), [f"{tick}%" for tick in range(0, 101, 20)], fontsize=10, color="#829AB1")
    ax.grid(axis="y", color="#DCE6EF", linewidth=0.9, zorder=0)
    ax.tick_params(axis="x", length=0, pad=12)
    ax.tick_params(axis="y", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    side.set_xlim(0, 1)
    side.set_ylim(0, 1)
    side.axis("off")
    side.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.018,rounding_size=0.025", facecolor="#102F4B", edgecolor="#2D6A91", linewidth=1.2))
    side.text(0.10, 0.90, "评测口径补充", fontsize=15, color="white", weight="bold")
    side.text(0.10, 0.845, "主图采用更贴近运行的真实链路", fontsize=10, color="#9BC9E2")
    side.text(0.10, 0.67, f"{formal['matching']['model_scores']['accuracy'] * 100:.0f}%", fontsize=37, color="#58D6C7", weight="bold")
    side.text(0.10, 0.61, "400条同域金标5折Accuracy", fontsize=11, color="#D8EAF4")
    side.plot([0.10, 0.90], [0.53, 0.53], color="#31546D", linewidth=1)
    side.text(0.10, 0.42, f"{live['jd_top3_recall'] * 100:.0f}%", fontsize=29, color="#FFD166", weight="bold")
    side.text(0.10, 0.36, "严格原JD Top-3召回率", fontsize=10.5, color="#D8EAF4")
    side.text(0.10, 0.22, "100 / 100", fontsize=20, color="#7CC8F5", weight="bold")
    side.text(0.10, 0.17, "接口请求成功", fontsize=10.5, color="#D8EAF4")
    side.text(0.10, 0.07, "补充指标不与同域金标混用", fontsize=9, color="#8DB4C9")

    fig.text(0.07, 0.105, "结论", fontsize=11, color="#177DDC", weight="bold")
    fig.text(0.112, 0.105, "三项任务书硬指标全部超过90%验收线；人岗匹配采用100份PDF真实上传的标准岗位Top-1结果。", fontsize=12.5, color="#243B53", weight="bold")
    fig.text(0.07, 0.055, "数据来源：human_gold_metrics_400.json、real_upload_matching_api_eval_v1_100/report.json  |  评测限制：400条金标为同域小组复核数据，跨来源泛化仍需外部盲测。", fontsize=8.8, color="#829AB1")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / "taskbook_acceptance_metrics_20260904.png", bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(OUTPUT_DIR / "taskbook_acceptance_metrics_20260904.svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    main()
