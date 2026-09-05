# 单元测试覆盖率最终结果

本目录保存 2026-09-05 版本的前后端单元测试覆盖率明细，作为最终材料的覆盖率证据。覆盖率统一按语句数统计。

## 结果

| 模块 | 已覆盖语句 | 语句总数 | 覆盖率 |
| --- | ---: | ---: | ---: |
| 后端 | 4,556 | 7,623 | 59.77% |
| 前端 | 2,184 | 3,452 | 63.26% |
| 综合 | 6,740 | 11,075 | 60.86% |

综合覆盖率按前后端语句数加权计算：

```text
(4,556 + 2,184) / (7,623 + 3,452) = 60.86%
```

## 明细文件

- `backend_coverage_final.json`：后端覆盖率明细，字段 `totals.covered_lines`、`totals.num_statements` 和 `totals.percent_covered`。
- `frontend_coverage_summary.json`：前端覆盖率汇总，字段 `total.statements.covered`、`total.statements.total` 和 `total.statements.pct`。

前端报告同时包含代码行、函数和分支覆盖率；综合结果按与后端一致的语句覆盖率口径计算。
