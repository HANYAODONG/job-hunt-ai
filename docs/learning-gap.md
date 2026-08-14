# /learning 学习路径页 — 后端缺口说明

**负责人**: 叶骑瑞  
**日期**: 2026-08-11  
**状态**: 前端 Mock 数据，后端无对应接口

---

## 一、当前状态

| 项目 | 详情 |
|------|------|
| 页面路径 | `/learning` |
| 页面功能 | 展示基于诊断结果的分阶段学习计划，含阶段任务、进度、交付物 |
| 当前调用 | `getLearningPlan()` → `mockTalentData.learningPlanData` |
| 数据来源 | 前端硬编码 Mock |
| 入参来源 | `/diagnosis` 页面通过 `localStorage.setItem('careerTarget', ...)` 传入目标岗位和缺失技能 |
| 后端接口 | 无 |

---

## 二、前端已有的 Mock 数据结构

前端 `LearningPlanPage.js` 当前使用的字段：

```json
{
  "profile": "陈同学",
  "targetRole": "大模型应用工程师",
  "targetVersion": "v1.2",
  "matchScore": 78,
  "progress": 36,
  "currentStage": "阶段 2",
  "updatedAt": "2026-07-25 11:20",
  "stages": [
    {
      "id": "stage-1",
      "phase": "阶段 1",
      "title": "Agent 工作流基础",
      "skill": "Agent 工作流",
      "duration": "1 周",
      "status": "已完成",
      "goal": "掌握工具调用、记忆与异常回退，形成可运行的最小智能体。",
      "tasks": ["完成工具调用练习", "实现短期记忆", "补充失败回退测试"],
      "outcome": "可演示的智能体工作流仓库"
    }
  ]
}
```

---

## 三、需要后端提供的接口

### 建议接口

```
POST /api/v1/learning/plan
```

### 请求参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|:---:|------|
| candidate_id | string | ✅ | 候选人 ID |
| target_job_id | string | ✅ | 目标岗位 ID |
| missing_skills | string[] | 否 | 缺失技能列表（从 /diagnosis 传入） |

### 需要返回的字段

| 字段 | 类型 | 优先级 | 说明 |
|------|------|:---:|------|
| `target_role` | string | P0 | **目标岗位**名称 |
| `missing_skills` | string[] | P0 | **缺失技能**列表 |
| `skill_priority` | object | P1 | **技能优先级**，如 `{"Agent 工作流": "高", "模型评测": "中"}` |
| `stages[]` | array | P0 | **学习阶段**列表 |
| `stages[].phase` | string | P0 | 阶段序号，如"阶段 1" |
| `stages[].title` | string | P0 | 阶段标题 |
| `stages[].skill` | string | P0 | 该阶段对应的缺失技能 |
| `stages[].duration` | string | P1 | 预计耗时，如"1 周" |
| `stages[].status` | string | P1 | 初始状态固定为"未开始" |
| `stages[].goal` | string | P0 | 阶段学习目标 |
| `stages[].tasks` | string[] | P0 | 具体任务清单 |
| `stages[].outcome` | string | P1 | 预期交付物 |
| `learning_suggestions` | string[] | P2 | **学习建议**，如"建议先完成基础项目再深入框架" |
| `recommended_resources` | array | P2 | **推荐资源**列表 |
| `recommended_resources[].title` | string | P2 | 资源标题（书名/课程名/项目名） |
| `recommended_resources[].type` | string | P2 | 资源类型（book/course/project） |
| `recommended_resources[].url` | string | P2 | 资源链接（可选） |

---

## 四、建议实现方案

由大模型根据技能缺口动态生成分阶段学习计划：

```
Prompt 输入：
  - 目标岗位：{{target_role}}
  - 缺失技能：{{missing_skills}}（含优先级）
  - 候选人当前能力：{{candidate_skills}}

期望输出：固定 JSON 格式的分阶段学习计划

降级策略：大模型不可用时，使用规则模板生成（按优先级排列技能，每个技能生成一个阶段）
```

---

## 五、依赖关系

```
/diagnosis（人岗诊断）
  │
  ├─ 目标岗位 role
  ├─ 缺失技能 gaps[].skill
  └─ 匹配度 score
        │
        ▼  localStorage.setItem('careerTarget', ...)
        │
/learning（学习路径）                          ← 本页
  │
  └─ 需要: POST /api/v1/learning/plan          ← 缺失接口
```
