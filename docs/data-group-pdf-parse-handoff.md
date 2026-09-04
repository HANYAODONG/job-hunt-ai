# 数据组 PDF 简历解析交付与匹配测试流程

## 目标

数据组只负责把 100 份 PDF 转成结构化候选人画像；岗位金标不写入解析结果。算法/评测组再使用这些画像运行两阶段人岗匹配。

## 每份简历至少输出

```json
{
  "sample_id": "UPLOAD-001",
  "candidate_id": "resume_xxx",
  "name": "脱敏测试候选人",
  "summary": "个人概述文本",
  "skills": ["Python", "SQL"],
  "experience": [{"title": "相关岗位经历", "description": "..."}],
  "projects": [{"name": "项目名", "description": "...", "skills": ["Python"]}],
  "education": [{"school": "脱敏学校", "degree": "本科", "major": "计算机相关"}],
  "years_experience": 2,
  "parser": {"name": "parser_name", "version": "parser_version"}
}
```

禁止输出或填入：`target_job_family`、`canonical_role_id`、`gold_role`、`accepted_jd_ids`。这些字段只保存在评测 manifest 中。

## 运行方式

1. 下载/使用 `artifacts/real_upload_matching_pack_v3_100/resumes/` 中的 PDF。
2. 对每个 PDF 执行数据组现有解析器。
3. 将 100 行 JSON 写入 `parsed_profiles.jsonl`，UTF-8 编码。
4. 同时返回解析日志：成功数、失败数、平均解析耗时、每份 `parse_ms`。
5. 把 `parsed_profiles.jsonl` 和日志交给评测组。

评测组随后把 `skills/experience/projects` 输入正式两阶段匹配，并与 `manifest.json` 的金标比较。

## 验收指标

- 100/100 可解析；
- 技能字段非空率；
- 与原始画像的技能召回率；
- 三级岗位 Top-1；
- JD Top-1/Top-2/Top-3；
- 总耗时和平均耗时（必须包含 PDF 解析）。
