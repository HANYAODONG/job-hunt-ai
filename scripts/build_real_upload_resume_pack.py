"""Build a 100-resume PDF upload pack from existing candidate profiles.

The PDFs intentionally contain resume evidence only; canonical labels are kept
in the manifest for evaluation and are never written into the documents.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, random
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def choose_profiles(profiles, n, seed):
    rng = random.Random(seed)
    # Stratify by canonical target label, then sample proportionally with a
    # minimum where possible so cross-domain errors remain represented.
    groups = {}
    for p in profiles:
        groups.setdefault(p.get("target_job_family", "未分类"), []).append(p)
    labels = sorted(groups)
    selected = []
    for label in labels:
        pool = groups[label][:]
        rng.shuffle(pool)
        if len(selected) < n and pool:
            selected.append(pool.pop())
        groups[label] = pool
    remaining = [p for pool in groups.values() for p in pool]
    rng.shuffle(remaining)
    selected.extend(remaining[: max(0, n - len(selected))])
    return selected[:n]


def safe_text(value):
    return str(value or "").replace("<", "&lt;").replace(">", "&gt;")


def evidence_only_summary(value):
    blocked = ("求职意向：", "标准岗位：", "岗位大族：", "岗位系统技能画像：")
    return "\n".join(line for line in str(value or "").splitlines() if not line.startswith(blocked))


def make_pdf(profile, path):
    # Embed a CJK font; Helvetica renders Chinese as empty squares/black boxes.
    # Use a standalone TrueType CJK font. TTC subfont embedding can render
    # correctly but omit a reliable ToUnicode map for PDF text extraction.
    font_name = "SimHei"
    pdfmetrics.registerFont(TTFont(font_name, r"C:\Windows\Fonts\simhei.ttf"))
    styles = getSampleStyleSheet()
    body = ParagraphStyle("ResumeBody", parent=styles["BodyText"], fontName=font_name, fontSize=9.5, leading=14, spaceAfter=3)
    heading = ParagraphStyle("ResumeHeading", parent=styles["Heading2"], fontName=font_name, fontSize=12, leading=16, spaceBefore=8, spaceAfter=4)
    title = ParagraphStyle("ResumeTitle", parent=styles["Title"], fontName=font_name, fontSize=17, leading=21, alignment=1, spaceAfter=10)
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=15*mm, bottomMargin=15*mm)
    story = [Paragraph("个人简历", title)]
    # Deliberately omit target_job_family/standard_category fields.
    education = profile.get("education") or {}
    story += [Paragraph("基本信息", heading), Paragraph("候选人：脱敏测试候选人", body), Paragraph(f"教育背景：{safe_text(education.get('education'))}，{safe_text(education.get('degree'))}，{safe_text(education.get('major'))}", body)]
    skills = profile.get("skills_normalized") or profile.get("skills") or []
    story += [Paragraph("个人概述", heading), Paragraph(safe_text(evidence_only_summary(profile.get("summary", ""))), body), Paragraph("技能栈", heading), Paragraph(safe_text("、".join(map(str, skills))), body)]
    story.append(Paragraph("工作经历", heading))
    for exp in profile.get("experience") or []:
        role = "相关岗位经历"
        years = safe_text(exp.get("duration_years"))
        story.append(Paragraph(f"{role}（{years} 年）", body))
        for h in exp.get("highlights") or []: story.append(Paragraph("• " + safe_text(h), body))
    story.append(Paragraph("项目经历", heading))
    for project in profile.get("projects") or []:
        story.append(Paragraph(f"{safe_text(project.get('project_name'))}：{safe_text(project.get('description'))}", body))
        stack = project.get("tech_stack") or []
        if stack: story.append(Paragraph("技术栈：" + safe_text("、".join(map(str, stack))), body))
        if project.get("outcome"): story.append(Paragraph("项目结果：" + safe_text(project.get("outcome")), body))
    doc.build(story)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", type=Path, default=Path("artifacts/dataset_iteration_05/candidate_profiles.jsonl"))
    ap.add_argument("--gold", type=Path, default=Path("artifacts/canonical_matching_review_v1/expert_gpt_cases.csv"))
    ap.add_argument("--output", type=Path, default=Path("artifacts/real_upload_matching_pack_v1_100"))
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260903)
    args = ap.parse_args(); args.output.mkdir(parents=True, exist_ok=True); (args.output/"resumes").mkdir(exist_ok=True)
    profiles = {p.get("candidate_id"): p for p in read_jsonl(args.profiles)}
    gold = list(csv.DictReader(args.gold.open(encoding="utf-8-sig", newline="")))
    gold_by_candidate = {}
    accepted = {}
    for row in gold:
        cid = row.get("candidate_id")
        if not cid:
            continue
        gold_by_candidate.setdefault(cid, row)
        try:
            accepted.setdefault(cid, []).extend(json.loads(row.get("gold_accepted_job_ids") or "[]"))
        except json.JSONDecodeError:
            pass
    candidates = [profiles[cid] for cid in gold_by_candidate if cid in profiles]
    chosen = choose_profiles(candidates, args.limit, args.seed)
    manifest = []
    for i, profile in enumerate(chosen, 1):
        cid = profile["candidate_id"]; name = f"UPLOAD-{i:03d}-{cid}.pdf"; out = args.output/"resumes"/name
        make_pdf(profile, out)
        row = gold_by_candidate[cid]
        manifest.append({"sample_id": f"UPLOAD-{i:03d}", "candidate_id": cid, "pdf": str(Path("resumes")/name), "pdf_sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "gold_role": row.get("target_canonical_role_id") or row.get("gold_canonical_role_id"), "accepted_jd_ids": sorted(set(accepted.get(cid, []))), "source": "derived_from_candidate_profile_without_label_fields"})
    (args.output/"manifest.json").write_text(json.dumps({"version":"real_upload_matching_pack_v1","samples":len(manifest),"seed":args.seed,"label_leakage_guard":"target_job_family and canonical labels omitted from PDFs","items":manifest}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"output":str(args.output),"samples":len(manifest),"roles":len(set(x["gold_role"] for x in manifest))}, ensure_ascii=False))

if __name__ == "__main__": main()
