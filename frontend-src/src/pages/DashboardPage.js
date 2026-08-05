import React, { useEffect, useState } from 'react';
import { Button, Progress, Skeleton } from 'antd';
import { ArrowRightOutlined, BookOutlined, CheckCircleFilled, CompassOutlined, DatabaseOutlined, FileSearchOutlined, RightOutlined, RiseOutlined, SafetyCertificateOutlined, SyncOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Link, useOutletContext } from 'react-router-dom';
import PageHeading from '../components/workbench/PageHeading';
import { getTalentOverview } from '../services/talentApi';

const WorkbenchTrend = ({ data }) => (
  <ResponsiveContainer width="100%" height="100%">
    <AreaChart data={data} margin={{ top: 10, right: 10, left: -24, bottom: 0 }}>
      <defs>
        <linearGradient id="workbenchArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4059c7" stopOpacity={0.2} />
          <stop offset="100%" stopColor="#4059c7" stopOpacity={0} />
        </linearGradient>
      </defs>
      <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#78818c', fontSize: 11 }} />
      <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9098a2', fontSize: 10 }} />
      <Tooltip contentStyle={{ border: '1px solid #dfe3e8', borderRadius: 4, boxShadow: 'none' }} />
      <Area type="monotone" dataKey="ai" stroke="#4059c7" strokeWidth={2} fill="url(#workbenchArea)" isAnimationActive={false} />
      <Area type="monotone" dataKey="data" stroke="#bb6f56" strokeWidth={1.5} fill="none" isAnimationActive={false} />
    </AreaChart>
  </ResponsiveContainer>
);

const CandidateDashboard = () => {
  const route = [
    { state: 'complete', phase: '01', title: '完成能力画像', meta: '已确认 6 项技能证据', action: '查看画像', to: '/diagnosis' },
    { state: 'active', phase: '02', title: '补齐 Agent 工作流', meta: '本周重点，已完成 1 / 3', action: '继续学习', to: '/learning' },
    { state: 'next', phase: '03', title: '形成可验证作品', meta: 'RAG 评测报告与演示仓库', action: '查看计划', to: '/learning' },
  ];
  const matches = [
    { role: '大模型应用工程师', family: '人工智能 / 中级', score: 78 },
    { role: 'AI Agent 工程师', family: '人工智能 / 新兴岗位', score: 71 },
    { role: 'AI 解决方案工程师', family: '智能系统 / 中级', score: 66 },
  ];
  const activity = [
    { tone: 'blue', title: '目标岗位画像已同步', meta: '大模型应用工程师 v1.2 吸收 12 条新增 JD 证据', time: '10:24', to: '/roles' },
    { tone: 'mint', title: '简历技能已确认', meta: 'Python、RAG、模型部署等 6 项能力进入画像', time: '昨天', to: '/diagnosis' },
    { tone: 'amber', title: '本周学习任务待完成', meta: 'Agent 工作流的第 2 个实战任务仍未提交', time: '周一', to: '/learning' },
    { tone: 'violet', title: '发现一个可迁移岗位', meta: 'AI Agent 工程师与目标画像共享 71% 核心技能', time: '周一', to: '/roles' },
  ];

  return (
    <div className="workbench-page candidate-dashboard">
      <PageHeading eyebrow="CAREER DESK / UPDATED 10:24" title="下一步，把能力差距变成可展示的作品" description="岗位需求已更新至今日数据，你的目标岗位画像仍引用已发布版本 v1.2。">
        <Link to="/diagnosis"><Button type="primary" icon={<FileSearchOutlined />}>更新诊断</Button></Link>
      </PageHeading>

      <section className="candidate-focus-band" aria-label="当前职业目标">
        <div className="candidate-target-copy">
          <span>ACTIVE TARGET</span>
          <h2>大模型应用工程师 <small>v1.2</small></h2>
          <p>你已经具备应用开发基础，现在需要补齐智能体编排、模型评测和生产可观测性。</p>
        </div>
        <div className="candidate-match-track">
          <header><span>当前匹配度</span><strong>78 / 100</strong></header>
          <Progress percent={78} showInfo={false} strokeColor="oklch(52% 0.18 266)" />
          <footer><span>上次诊断 76</span><span>建议阈值 85</span></footer>
        </div>
        <div className="candidate-week-focus">
          <span>FOCUS THIS WEEK</span>
          <strong>Agent 工作流</strong>
          <small>岗位要求 82，你的当前能力 49</small>
          <Link to="/learning">继续阶段 2 <ArrowRightOutlined /></Link>
        </div>
      </section>

      <section className="candidate-insight-grid" aria-label="本周职业洞察">
        <article><span><RiseOutlined /> 岗位需求</span><strong>+12.4%</strong><small>Agent 工作流近 30 天增长</small></article>
        <article><span><ThunderboltOutlined /> 优先缺口</span><strong>3 项</strong><small>均可在 3 周内形成作品证据</small></article>
        <article><span><SafetyCertificateOutlined /> 画像可信度</span><strong>89%</strong><small>简历解析结果已确认</small></article>
      </section>

      <div className="candidate-dashboard-grid">
        <section className="candidate-route-panel">
          <header className="section-heading-row"><div><span>YOUR ROUTE</span><h2>从诊断到下一次复诊</h2></div><Link to="/learning">完整路径</Link></header>
          <ol className="candidate-route-list">
            {route.map((item) => <li key={item.phase} className={item.state}>
              <span>{item.state === 'complete' ? <CheckCircleFilled /> : item.phase}</span>
              <div><strong>{item.title}</strong><small>{item.meta}</small></div>
              <Link to={item.to}>{item.action} <RightOutlined /></Link>
            </li>)}
          </ol>
        </section>

        <aside className="candidate-match-panel">
          <header className="section-heading-row"><div><span>ROLE MATCHES</span><h2>适合继续关注</h2></div><Link to="/roles">岗位库</Link></header>
          <div className="candidate-match-list">
            {matches.map((item) => <Link to="/roles" key={item.role}>
              <span><strong>{item.role}</strong><small>{item.family}</small></span>
              <i><b style={{ width: `${item.score}%` }} /></i>
              <em>{item.score}</em>
            </Link>)}
          </div>
        </aside>
      </div>

      <section className="candidate-activity-panel" aria-label="最近职业动态">
        <header className="section-heading-row"><div><span>RECENT ACTIVITY</span><h2>岗位数据与你的成长记录</h2></div><Link to="/roles">查看全部</Link></header>
        <div className="candidate-activity-grid">
          {activity.map((item) => <Link key={item.title} to={item.to} className={`candidate-activity-item tone-${item.tone}`}>
            <i />
            <span><strong>{item.title}</strong><small>{item.meta}</small></span>
            <time>{item.time}<ArrowRightOutlined /></time>
          </Link>)}
        </div>
      </section>

      <section className="candidate-evidence-band" aria-label="个人能力状态">
        <div><CompassOutlined /><span><strong>目标岗位</strong><small>已固定到 v1.2</small></span></div>
        <div><FileSearchOutlined /><span><strong>简历画像</strong><small>89% 提取置信度</small></span></div>
        <div><BookOutlined /><span><strong>学习路径</strong><small>阶段 2，共 3 周</small></span></div>
        <div><SyncOutlined /><span><strong>岗位数据</strong><small>今日 10:24 已同步</small></span></div>
      </section>
    </div>
  );
};

const DashboardPage = () => {
  const [data, setData] = useState(null);
  const { workspaceRole = 'candidate' } = useOutletContext() || {};

  useEffect(() => {
    getTalentOverview().then(setData).catch(() => setData({ stats: [], demandTrend: [], reviewTasks: [], sources: [] }));
  }, []);

  if (workspaceRole === 'candidate') return <CandidateDashboard />;
  if (!data) return <div className="page-loading"><Skeleton active paragraph={{ rows: 10 }} /></div>;

  return (
    <div className="workbench-page workflow-dashboard">
      <PageHeading eyebrow="WORKBENCH / 07.25" title="今天，从 18 项市场信号开始" description="先完成高价值信号审核，再观察它们对岗位版本、能力图谱和人才诊断的影响。">
        <Link to="/signals"><Button type="primary">进入审核队列 <ArrowRightOutlined /></Button></Link>
      </PageHeading>

      <section className="lifecycle-strip" aria-label="岗位知识生产流程">
        {[
          ['01', '市场信号', '18 项待审核'],
          ['02', '人工定义', '4 份草稿'],
          ['03', '版本发布', '本周 7 次'],
          ['04', '图谱同步', '刚刚完成'],
          ['05', '诊断应用', '23 份报告'],
        ].map(([index, label, meta], itemIndex) => <React.Fragment key={label}><div className={itemIndex === 0 ? 'active' : ''}><span>{index}</span><strong>{label}</strong><small>{meta}</small></div>{itemIndex < 4 && <i />}</React.Fragment>)}
      </section>

      <section className="enterprise-metric-grid" aria-label="岗位情报指标">
        <article className="metric-accent-blue"><span>待处理市场信号</span><strong>18</strong><small><RiseOutlined /> 较昨日新增 4 项</small></article>
        <article className="metric-accent-mint"><span>本周发布岗位版本</span><strong>07</strong><small><CheckCircleFilled /> 图谱同步正常</small></article>
        <article className="metric-accent-amber"><span>需要人工确认的技能</span><strong>26</strong><small><FileSearchOutlined /> 6 项优先级较高</small></article>
        <article className="metric-accent-violet"><span>有效岗位数据覆盖</span><strong>94.7%</strong><small><DatabaseOutlined /> 12 个数据源在线</small></article>
      </section>

      <div className="dashboard-workspace">
        <section className="dashboard-primary">
          <header className="section-heading-row">
            <div><span>MARKET MOVEMENT</span><h2>Agent 工作流正在重写应用岗位的能力边界</h2></div>
            <strong className="trend-indicator">近 90 天 +42%</strong>
          </header>
          <div className="dashboard-chart"><WorkbenchTrend data={data.demandTrend} /></div>
          <footer className="chart-footnote"><span><i className="series-ai" />人工智能岗位</span><span><i className="series-data" />数据智能岗位</span><small>来源：公开招聘数据与行业报告，今日 10:24 更新</small></footer>
        </section>

        <aside className="review-queue-panel">
          <header className="section-heading-row"><div><span>REVIEW QUEUE</span><h2>优先处理</h2></div><Link to="/signals">全部</Link></header>
          <ol className="review-queue-list">
            {data.reviewTasks.map((task, index) => <li key={task.id}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{task.name}</strong><small>{task.type} · {task.updatedAt}</small></div><b>{task.confidence}%</b></li>)}
          </ol>
        </aside>
      </div>

      <section className="dashboard-bottom-band">
        <div className="system-pulse"><span>系统脉冲</span><strong><SyncOutlined /> 数据链路运行正常</strong><small>最近一次完整同步耗时 08:42</small></div>
        {data.sources.map((source) => <div className="source-brief" key={source.name}><DatabaseOutlined /><span><strong>{source.name}</strong><small>{source.freshness}</small></span><b>{source.coverage}%</b></div>)}
        <div className="source-brief"><CheckCircleFilled /><span><strong>岗位版本</strong><small>图谱已同步</small></span><b>1.2</b></div>
      </section>
    </div>
  );
};

export default DashboardPage;
