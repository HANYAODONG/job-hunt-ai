export const dashboardData = {
  stats: [
    { title: '在管岗位', value: 1286, suffix: '个', trend: '+8.4%', tone: 'cyan' },
    { title: '能力节点', value: 3468, suffix: '项', trend: '+126', tone: 'violet' },
    { title: '待审核任务', value: 18, suffix: '项', trend: '4 项高优先级', tone: 'coral' },
    { title: '数据健康度', value: 92, suffix: '%', trend: '较上周 +2.1%', tone: 'gold' },
  ],
  demandTrend: [
    { month: '2月', ai: 68, data: 52, iot: 40 },
    { month: '3月', ai: 74, data: 59, iot: 43 },
    { month: '4月', ai: 80, data: 63, iot: 47 },
    { month: '5月', ai: 86, data: 70, iot: 51 },
    { month: '6月', ai: 94, data: 76, iot: 56 },
    { month: '7月', ai: 108, data: 83, iot: 62 },
  ],
  reviewTasks: [
    { id: 'RV-1024', name: '具身智能算法工程师', type: '新岗位候选', confidence: 91, updatedAt: '18 分钟前', priority: '高' },
    { id: 'RV-1021', name: '大模型应用工程师', type: '能力版本更新', confidence: 88, updatedAt: '1 小时前', priority: '高' },
    { id: 'RV-1017', name: '工业物联网架构师', type: '数据质量复核', confidence: 74, updatedAt: '3 小时前', priority: '中' },
  ],
  sources: [
    { name: '企业招聘官网', coverage: 94, freshness: '今天 09:30', status: '正常' },
    { name: '主流招聘平台', coverage: 88, freshness: '今天 08:12', status: '正常' },
    { name: '行业报告与白皮书', coverage: 72, freshness: '昨天 18:40', status: '待更新' },
  ],
};

export const discoveryCandidates = [
  {
    id: 'NEW-023',
    name: '具身智能算法工程师',
    domain: '人工智能',
    status: '待审核',
    confidence: 91,
    evidence: 36,
    signals: ['岗位频次环比 +48%', '技能组合出现新聚类', '3 家头部企业新增招聘'],
    skills: ['视觉语言模型', '强化学习', 'ROS 2', '运动规划'],
    updatedAt: '2026-07-25 09:42',
  },
  {
    id: 'NEW-019',
    name: 'AI Agent 应用工程师',
    domain: '人工智能',
    status: '待审核',
    confidence: 88,
    evidence: 42,
    signals: ['近 30 天新增 286 条 JD', '工具调用技能高共现', '职责边界趋于稳定'],
    skills: ['Agent 框架', 'RAG', '工作流编排', '评测'],
    updatedAt: '2026-07-25 08:18',
  },
  {
    id: 'NEW-016',
    name: '工业大模型解决方案工程师',
    domain: '智能系统',
    status: '补充证据',
    confidence: 76,
    evidence: 19,
    signals: ['行业词汇增长明显', '岗位名称存在多种变体'],
    skills: ['工业知识库', '模型部署', 'OT/IT 融合'],
    updatedAt: '2026-07-24 16:20',
  },
];

export const marketChangeCandidates = [
  {
    id: 'CHG-041',
    name: '大模型应用工程师',
    domain: '人工智能',
    status: '待审核',
    confidence: 93,
    evidence: 57,
    version: 'v1.2 -> v1.3',
    signals: ['Agent 工作流提及率提升 42%', '模型评测成为核心要求', '传统 NLP 管线需求持续下降'],
    skills: ['Agent 工作流', '模型评测', '可观测性'],
    added: ['Agent 工作流', '模型评测'],
    removed: ['传统 NLP 管线'],
    modified: ['RAG: 基础使用 -> 检索质量优化'],
    updatedAt: '2026-07-25 10:12',
  },
  {
    id: 'CHG-038',
    name: 'Java 开发工程师',
    domain: '软件工程',
    status: '补充证据',
    confidence: 81,
    evidence: 31,
    version: 'v2.3 -> v2.4',
    signals: ['云原生部署要求上升 18%', '可观测性进入必备能力区间'],
    skills: ['Kubernetes', 'OpenTelemetry', '微服务治理'],
    added: ['OpenTelemetry'],
    removed: [],
    modified: ['Kubernetes: 加分技能 -> 必备技能'],
    updatedAt: '2026-07-24 15:36',
  },
];

export const roleCatalogData = [
  {
    id: 'agent-app',
    name: 'AI Agent 应用工程师',
    family: '大模型应用',
    domain: '人工智能',
    level: '中级',
    version: 'v1.1',
    status: '已发布',
    updatedAt: '2026-07-18',
    growth: '+42%',
    evidenceCount: 126,
    summary: '面向企业场景设计、开发并持续评估具备规划、工具调用和记忆能力的智能体应用。',
    responsibilities: ['分析业务任务并设计智能体工作流', '实现工具调用、记忆与异常回退机制', '建立智能体质量评测与运行监控'],
    requiredSkills: [
      { name: 'Agent 工作流', level: 86, trend: '+18%' },
      { name: 'RAG', level: 78, trend: '+9%' },
      { name: 'Python', level: 82, trend: '+2%' },
      { name: '模型评测', level: 74, trend: '+21%' },
    ],
    bonusSkills: ['多智能体协作', '可观测性', 'MCP', '模型微调'],
    scenarios: ['企业知识助手', '智能客服与工单流转', '研发效能自动化'],
    versions: [
      { version: 'v1.1', date: '2026-07-18', note: '新增模型评测与运行可观测性' },
      { version: 'v1.0', date: '2026-04-12', note: '首次形成标准岗位定义' },
    ],
  },
  {
    id: 'llm-app',
    name: '大模型应用工程师',
    family: '大模型应用',
    domain: '人工智能',
    level: '中级',
    version: 'v1.2',
    status: '已发布',
    updatedAt: '2026-07-18',
    growth: '+28%',
    evidenceCount: 98,
    summary: '负责大模型能力接入、知识增强、应用服务开发及效果优化。',
    responsibilities: ['建设大模型应用服务', '优化检索增强生成链路', '设计效果评测与反馈闭环'],
    requiredSkills: [
      { name: 'RAG', level: 88, trend: '+12%' },
      { name: 'Python', level: 84, trend: '+3%' },
      { name: 'FastAPI', level: 72, trend: '+4%' },
      { name: '向量数据库', level: 76, trend: '+8%' },
    ],
    bonusSkills: ['Agent 编排', '模型微调', '推理优化'],
    scenarios: ['企业知识库', '内容生成平台', '智能分析助手'],
    versions: [
      { version: 'v1.2', date: '2026-07-18', note: '强化评测与可观测性要求' },
      { version: 'v1.1', date: '2026-04-08', note: '补充向量数据库能力' },
      { version: 'v1.0', date: '2025-12-20', note: '建立岗位初始定义' },
    ],
  },
  {
    id: 'java-engineer',
    name: 'Java 开发工程师',
    family: '后端工程',
    domain: '软件工程',
    level: '中级',
    version: 'v2.3',
    status: '已发布',
    updatedAt: '2026-06-30',
    growth: '+6%',
    evidenceCount: 214,
    summary: '负责企业级后端服务设计、实现、交付及稳定性治理。',
    responsibilities: ['设计并实现微服务接口', '保障服务性能与稳定性', '参与工程规范与交付流程建设'],
    requiredSkills: [
      { name: 'Java', level: 92, trend: '+1%' },
      { name: 'Spring Boot', level: 88, trend: '+2%' },
      { name: 'MySQL', level: 80, trend: '0%' },
      { name: '微服务治理', level: 74, trend: '+7%' },
    ],
    bonusSkills: ['Kubernetes', '消息队列', '可观测性'],
    scenarios: ['企业业务中台', '交易系统', '云原生服务平台'],
    versions: [
      { version: 'v2.3', date: '2026-06-30', note: '提升云原生与稳定性能力权重' },
      { version: 'v2.2', date: '2026-02-16', note: '补充微服务治理能力' },
    ],
  },
];

export const learningPlanData = {
  profile: '陈同学',
  targetRole: '大模型应用工程师',
  targetVersion: 'v1.2',
  progress: 36,
  currentStage: '阶段 2',
  updatedAt: '2026-07-25 11:20',
  gapCount: 3,
  stages: [
    {
      id: 'stage-1',
      phase: '阶段 1',
      title: 'Agent 工作流基础',
      duration: '1 周',
      status: '已完成',
      goal: '掌握工具调用、记忆与异常回退，形成可运行的最小智能体。',
      tasks: ['完成工具调用练习', '实现短期记忆', '补充失败回退测试'],
      outcome: '可演示的智能体工作流仓库',
      skill: 'Agent 工作流',
    },
    {
      id: 'stage-2',
      phase: '阶段 2',
      title: 'RAG 质量评测',
      duration: '1 周',
      status: '进行中',
      goal: '建立检索与生成质量指标，能够解释每次方案调整的影响。',
      tasks: ['构建 30 条问答评测集', '计算召回率与答案忠实度', '记录三组参数对比'],
      outcome: '可复现的 RAG 评测报告',
      skill: '模型评测',
    },
    {
      id: 'stage-3',
      phase: '阶段 3',
      title: '生产化与可观测性',
      duration: '1 周',
      status: '未开始',
      goal: '为工作流补充链路追踪、成本记录和用户反馈闭环。',
      tasks: ['接入链路追踪', '设计失败类型看板', '加入用户反馈入口'],
      outcome: '端到端作品演示与技术说明',
      skill: '可观测性',
    },
  ],
};

export const graphData = {
  jobs: ['大模型应用工程师', '数据工程师', '智能系统工程师'],
  stacks: ['大模型技术栈', '数据智能技术栈', '智能终端技术栈'],
  summary: { domains: 4, families: 12, roles: 38 },
  tree: {
    id: 'root', label: '数字技术岗位图谱', type: 'root', count: 1286, growth: '+8.4%', detail: '汇聚多源招聘、行业报告和技能证据形成的动态岗位关系网络。', skills: ['岗位分类', '能力映射', '动态演化'],
    children: [
      {
        id: 'ai', label: '人工智能', type: 'domain', count: 386, growth: '+18.6%', detail: '覆盖算法研究、模型应用与智能体系统等快速演化岗位。', skills: ['机器学习', '深度学习', '模型工程'],
        children: [
          { id: 'llm-family', label: '大模型应用', type: 'family', count: 126, growth: '+32.4%', detail: '围绕大模型能力落地、知识增强和应用编排形成的岗位族。', skills: ['RAG', 'Agent', '模型评测'], children: [
            { id: 'llm-app', label: '大模型应用工程师', type: 'role', count: 54, growth: '+28%', detail: '负责大模型能力落地、应用编排与质量评测。', skills: ['RAG', 'Prompt', 'FastAPI'] },
            { id: 'agent-app', label: 'AI Agent 工程师', type: 'role', count: 43, growth: '+42%', detail: '构建具备工具调用、规划和记忆能力的智能体系统。', skills: ['Agent 框架', '工具调用', '工作流编排'] },
            { id: 'rag-engineer', label: 'RAG 工程师', type: 'role', count: 29, growth: '+24%', detail: '负责检索增强生成链路、知识库与效果优化。', skills: ['向量数据库', '召回排序', '知识库'] },
          ] },
          { id: 'algo-family', label: '算法研究', type: 'family', count: 148, growth: '+9.8%', detail: '涵盖视觉、语言、多模态和推荐算法研究与工程化。', skills: ['PyTorch', '算法优化', '实验设计'], children: [
            { id: 'cv-algo', label: '视觉算法工程师', type: 'role', count: 58, growth: '+7%', detail: '面向检测、分割和视觉理解的算法研发岗位。', skills: ['计算机视觉', 'OpenCV', '模型部署'] },
            { id: 'multimodal-algo', label: '多模态算法工程师', type: 'role', count: 46, growth: '+19%', detail: '研究视觉、语言与音频信息的联合建模。', skills: ['多模态模型', '对齐学习', '数据构建'] },
          ] },
          { id: 'embodied-family', label: '具身智能', type: 'family', count: 72, growth: '+48%', detail: '连接感知、决策与机器人执行的新兴岗位族。', skills: ['强化学习', '运动规划', 'ROS 2'], children: [
            { id: 'embodied-algo', label: '具身智能算法工程师', type: 'role', count: 36, growth: '+53%', detail: '负责机器人感知决策、世界模型与策略学习。', skills: ['强化学习', '视觉语言模型', '仿真'] },
            { id: 'robot-learning', label: '机器人学习工程师', type: 'role', count: 21, growth: '+35%', detail: '构建机器人模仿学习和强化学习训练系统。', skills: ['模仿学习', '控制算法', '数据采集'] },
          ] },
        ],
      },
      {
        id: 'data', label: '数据智能', type: 'domain', count: 342, growth: '+11.2%', detail: '覆盖数据基础设施、分析决策与数据产品岗位。', skills: ['数据工程', '分析建模', '数据治理'],
        children: [
          { id: 'data-platform', label: '数据平台', type: 'family', count: 132, growth: '+8.2%', detail: '建设稳定、可治理的数据采集与计算平台。', skills: ['Spark', 'Flink', '数据湖'], children: [
            { id: 'data-engineer', label: '数据工程师', type: 'role', count: 76, growth: '+6%', detail: '负责数据管道、计算任务和数据服务建设。', skills: ['SQL', 'Spark', 'ETL'] },
            { id: 'realtime-data', label: '实时计算工程师', type: 'role', count: 31, growth: '+14%', detail: '建设低延迟流式计算和实时数仓。', skills: ['Flink', 'Kafka', '实时数仓'] },
          ] },
          { id: 'analytics-family', label: '商业分析', type: 'family', count: 118, growth: '+10.1%', detail: '用指标、实验与模型支持业务决策。', skills: ['指标体系', 'A/B 实验', '可视化'], children: [
            { id: 'data-analyst', label: '数据分析师', type: 'role', count: 69, growth: '+8%', detail: '负责业务分析、指标监控和专题研究。', skills: ['SQL', '统计分析', 'BI'] },
            { id: 'strategy-analyst', label: '策略分析师', type: 'role', count: 28, growth: '+12%', detail: '将数据洞察转化为运营与增长策略。', skills: ['策略建模', '实验设计', '行业研究'] },
          ] },
          { id: 'governance-family', label: '数据治理', type: 'family', count: 92, growth: '+17.5%', detail: '围绕质量、标准、安全和资产管理构建岗位体系。', skills: ['元数据', '质量规则', '数据安全'], children: [
            { id: 'governance-engineer', label: '数据治理工程师', type: 'role', count: 44, growth: '+18%', detail: '建立数据标准、质量检查和资产目录。', skills: ['数据标准', '血缘分析', '质量监控'] },
            { id: 'data-security', label: '数据安全工程师', type: 'role', count: 25, growth: '+16%', detail: '负责数据分类分级、审计和隐私保护。', skills: ['隐私计算', '权限治理', '合规'] },
          ] },
        ],
      },
      {
        id: 'intelligent-system', label: '智能系统', type: 'domain', count: 296, growth: '+13.7%', detail: '连接软件、终端与工业场景的系统型岗位大类。', skills: ['系统架构', '边缘计算', '软硬协同'],
        children: [
          { id: 'iot-family', label: '工业物联网', type: 'family', count: 96, growth: '+15%', detail: '连接设备、边缘和工业平台的岗位族。', skills: ['IoT', '边缘计算', '工业协议'], children: [
            { id: 'iot-architect', label: '工业物联网架构师', type: 'role', count: 24, growth: '+17%', detail: '设计工业设备接入、边缘协同与平台架构。', skills: ['MQTT', '边缘网关', '工业互联网'] },
            { id: 'edge-engineer', label: '边缘计算工程师', type: 'role', count: 35, growth: '+14%', detail: '负责边缘侧推理、调度与设备管理。', skills: ['边缘推理', '容器化', '设备管理'] },
          ] },
          { id: 'cloud-family', label: '云原生系统', type: 'family', count: 124, growth: '+9%', detail: '建设弹性、可观测的现代软件基础设施。', skills: ['Kubernetes', '微服务', '可观测性'], children: [
            { id: 'cloud-engineer', label: '云原生工程师', type: 'role', count: 57, growth: '+8%', detail: '构建云原生应用交付与运行平台。', skills: ['Kubernetes', 'Service Mesh', 'DevOps'] },
            { id: 'sre', label: 'SRE 工程师', type: 'role', count: 42, growth: '+10%', detail: '负责系统可靠性、容量和故障治理。', skills: ['可观测性', '自动化运维', '稳定性'] },
          ] },
          { id: 'solution-family', label: '智能解决方案', type: 'family', count: 76, growth: '+21%', detail: '将技术能力组合为面向行业的解决方案。', skills: ['需求分析', '技术方案', '项目交付'], children: [
            { id: 'ai-solution', label: 'AI 解决方案工程师', type: 'role', count: 38, growth: '+23%', detail: '负责 AI 方案设计、验证和客户场景落地。', skills: ['方案设计', '原型验证', '行业知识'] },
            { id: 'industrial-solution', label: '工业智能方案工程师', type: 'role', count: 22, growth: '+19%', detail: '面向制造场景设计模型与工业系统融合方案。', skills: ['工业知识库', 'OT/IT 融合', '模型部署'] },
          ] },
        ],
      },
      {
        id: 'product-ops', label: '产品与运营', type: 'domain', count: 262, growth: '+7.1%', detail: '将技术能力转化为产品体验和持续运营结果。', skills: ['产品设计', '增长运营', '用户研究'],
        children: [
          { id: 'ai-product-family', label: 'AI 产品', type: 'family', count: 94, growth: '+22%', detail: '定义 AI 能力边界、交互和商业价值的岗位族。', skills: ['AI 产品设计', '模型评测', '场景规划'], children: [
            { id: 'ai-pm', label: 'AI 产品经理', type: 'role', count: 48, growth: '+24%', detail: '负责 AI 产品规划、模型能力评估与迭代。', skills: ['需求分析', '模型认知', '产品策略'] },
            { id: 'agent-pm', label: 'Agent 产品经理', type: 'role', count: 27, growth: '+37%', detail: '设计智能体工作流、权限和人机协作体验。', skills: ['工作流设计', '人机协作', '评测体系'] },
          ] },
          { id: 'growth-family', label: '增长运营', type: 'family', count: 106, growth: '+5.8%', detail: '围绕获客、留存和商业化持续优化。', skills: ['用户分层', '增长实验', '内容策略'], children: [
            { id: 'growth-ops', label: '增长运营经理', type: 'role', count: 51, growth: '+7%', detail: '通过实验和策略推动用户增长与留存。', skills: ['增长实验', '渠道分析', '用户运营'] },
            { id: 'product-ops-role', label: '产品运营经理', type: 'role', count: 39, growth: '+4%', detail: '连接产品能力、用户反馈和运营策略。', skills: ['产品运营', '数据分析', '用户反馈'] },
          ] },
          { id: 'ux-family', label: '体验设计', type: 'family', count: 62, growth: '+6.3%', detail: '研究并设计复杂智能产品的人机交互。', skills: ['交互设计', '用户研究', '设计系统'], children: [
            { id: 'ai-ux', label: 'AI 交互设计师', type: 'role', count: 26, growth: '+18%', detail: '设计生成式 AI 与智能体产品的人机交互。', skills: ['对话设计', '可解释性', '原型验证'] },
            { id: 'service-designer', label: '服务设计师', type: 'role', count: 18, growth: '+3%', detail: '从完整服务链路设计组织与用户体验。', skills: ['服务蓝图', '旅程地图', '共创工作坊'] },
          ] },
        ],
      },
    ],
  },
};

export const evolutionData = {
  role: '大模型应用工程师',
  versions: [
    { version: 'v1.2', date: '2026-07-18', status: '当前版本', summary: '新增 Agent 工作流与模型评测能力，职责中强化可观测性要求。', added: ['Agent 工作流', '模型评测', '可观测性'], removed: ['传统 NLP 管线'], modified: ['RAG: 基础使用 -> 检索质量优化'], evidence: 27 },
    { version: 'v1.1', date: '2026-04-08', status: '已发布', summary: '根据春招数据补全向量数据库和大模型微调能力。', added: ['向量数据库', '大模型微调'], removed: [], modified: ['提示工程: 加入安全规范'], evidence: 18 },
    { version: 'v1.0', date: '2025-12-20', status: '基线版本', summary: '建立岗位初始定义，覆盖应用开发与基础模型调用。', added: ['Python', 'LLM API', '提示工程'], removed: [], modified: [], evidence: 34 },
  ],
};

export const diagnosisData = {
  profile: {
    name: '陈同学',
    target: '大模型应用工程师',
    confidence: 89,
    skills: ['Python', 'LangChain', 'RAG', 'FastAPI', 'Docker', 'SQL'],
    experience: '有 2 段 AI 应用项目经历，具备从数据处理到服务部署的基础实践。',
  },
  match: 78,
  matches: [
    {
      id: 'llm-app-engineer', role: '大模型应用工程师', family: '人工智能 / 大模型应用', version: 'v1.2', score: 78,
      reason: 'RAG、Python 与应用服务经验和岗位核心要求高度重合。',
      gaps: [
        { skill: 'Agent 工作流', priority: '高', current: 49, target: 82, reason: '目标岗位近 30 天需求增长 42%，简历中尚未发现相关项目证据。' },
        { skill: '模型评测', priority: '高', current: 56, target: 78, reason: '岗位要求中出现频率 41%，建议补充检索与生成质量评测实践。' },
        { skill: '可观测性', priority: '中', current: 44, target: 70, reason: '生产化岗位常见要求，可在项目中补充链路追踪与反馈分析。' },
      ],
    },
    {
      id: 'agent-engineer', role: 'AI Agent 工程师', family: '人工智能 / 新兴岗位', version: 'v1.0', score: 72,
      reason: '具备智能体应用基础，但多智能体协作和系统评测证据不足。',
      gaps: [
        { skill: '多智能体协作', priority: '高', current: 38, target: 84, reason: '岗位强调任务拆分、角色协作和冲突处理，当前简历未出现对应实践。' },
        { skill: 'Agent 评测', priority: '高', current: 42, target: 79, reason: '需要补充任务完成率、工具调用正确率和失败类型分析。' },
        { skill: '权限与安全', priority: '中', current: 35, target: 68, reason: '企业场景要求明确工具权限、敏感数据和人工确认边界。' },
      ],
    },
    {
      id: 'ai-solution-engineer', role: 'AI 解决方案工程师', family: '智能系统 / 解决方案', version: 'v1.1', score: 66,
      reason: '技术实现能力匹配，但行业需求分析和方案交付证据较少。',
      gaps: [
        { skill: '方案设计', priority: '高', current: 46, target: 76, reason: '需要把技术能力组织为可验证的客户方案和实施边界。' },
        { skill: '行业知识', priority: '高', current: 40, target: 72, reason: '目标岗位要求理解至少一个行业的流程、数据和交付约束。' },
        { skill: '原型验证', priority: '中', current: 58, target: 74, reason: '建议补充需求到原型、评测和复盘的完整交付记录。' },
      ],
    },
  ],
  strengths: ['RAG 项目经历与目标岗位高度相关', '具备完整的后端服务部署经验', 'Python 与数据处理基础扎实'],
  gaps: [
    { skill: 'Agent 工作流', priority: '高', reason: '目标岗位近 30 天需求增长 42%，简历中尚未发现相关项目证据。' },
    { skill: '模型评测', priority: '高', reason: '岗位要求中出现频率 41%，建议补充检索与生成质量评测实践。' },
    { skill: '可观测性', priority: '中', reason: '生产化岗位常见要求，可在项目中补充链路追踪与反馈分析。' },
  ],
  roadmap: [
    { phase: '第 1 周', title: '构建可调用的 Agent', detail: '完成工具调用、记忆与失败回退的最小工作流。' },
    { phase: '第 2 周', title: '补齐 RAG 评测', detail: '为检索命中率、答案可信度建立可复现的评测集。' },
    { phase: '第 3 周', title: '完成项目闭环', detail: '接入日志、追踪和用户反馈，沉淀为可展示项目。' },
  ],
};

export const governanceData = {
  sources: [
    { key: '1', source: '企业招聘官网', records: 486, valid: 96, duplicate: 2.1, freshness: '2 小时内', owner: '采集任务 A-03' },
    { key: '2', source: '主流招聘平台', records: 624, valid: 91, duplicate: 5.8, freshness: '5 小时内', owner: '采集任务 A-07' },
    { key: '3', source: '行业报告与白皮书', records: 176, valid: 87, duplicate: 1.2, freshness: '1 天前', owner: '人工导入 B-02' },
  ],
  issues: [
    { title: '岗位名称标准化待确认', detail: '“AI 应用工程师”与“大模型应用工程师”存在合并候选。', level: '待处理' },
    { title: '低可信度来源', detail: '2 个来源近 7 天有效记录不足 60%，已降低权重。', level: '关注' },
  ],
};

export const evaluationData = {
  metrics: [
    { label: 'JD 解析 F1', value: 91.6, target: 90, tone: 'cyan' },
    { label: '简历技能提取 F1', value: 90.8, target: 90, tone: 'violet' },
    { label: '人岗匹配准确率', value: 89.4, target: 90, tone: 'coral' },
    { label: '测试 JD 覆盖量', value: 126, target: 100, tone: 'gold' },
  ],
  errors: [
    { category: '近义技能归一', count: 8, example: '“智能体”与“Agent”未完全合并' },
    { category: '隐式项目经验', count: 5, example: '简历中未显式列出但项目描述可推断' },
    { category: '岗位名称变体', count: 4, example: '“LLM 应用工程师”标准化不足' },
  ],
};
