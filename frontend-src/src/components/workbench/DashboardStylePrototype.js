import React, { useEffect } from 'react';
import { Button } from 'antd';
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  ArrowUpOutlined,
  CloseOutlined,
  ExpandOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import './dashboard-prototype.css';

const variants = [
  { key: 'A', name: 'Signal Desk' },
  { key: 'B', name: 'Research Atlas' },
  { key: 'C', name: 'Index Ledger' },
];

const byTitle = (stats, title) => stats.find((item) => item.title === title) || {};

const DemandChart = ({ data, accent, minimal = false }) => (
  <ResponsiveContainer width="100%" height="100%">
    <AreaChart data={data} margin={{ top: 8, right: 2, left: minimal ? -34 : -20, bottom: 0 }}>
      {!minimal && <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#65716f', fontSize: 11 }} />}
      <Tooltip cursor={{ stroke: accent, strokeWidth: 1 }} contentStyle={{ borderRadius: 0, border: '1px solid #cbd1cf', boxShadow: 'none' }} />
      <Area type="monotone" dataKey="ai" stroke={accent} strokeWidth={2.4} fill={accent} fillOpacity={0.1} />
      <Area type="monotone" dataKey="data" stroke="#9b8bd8" strokeWidth={1.5} fill="none" />
    </AreaChart>
  </ResponsiveContainer>
);

const Queue = ({ tasks, dark = false }) => (
  <ol className={`prototype-queue ${dark ? 'prototype-queue-dark' : ''}`}>
    {tasks.slice(0, 4).map((task, index) => (
      <li key={task.id}>
        <span className="queue-index">0{index + 1}</span>
        <div><strong>{task.name}</strong><small>{task.type} · {task.updatedAt}</small></div>
        <span className="queue-score">{task.confidence}%</span>
      </li>
    ))}
  </ol>
);

const SignalDesk = ({ data, showSwitcher }) => {
  const positions = byTitle(data.stats, '在管岗位');
  const review = byTitle(data.stats, '待审核任务');

  return (
    <main className="prototype-page prototype-a">
      <header className="prototype-masthead">
        <div><p className="prototype-kicker">FIELD NOTES / 07.25</p><h1>岗位信号台</h1></div>
        <div className="prototype-header-actions"><span>市场脉冲已刷新 <b>10:24</b></span><Button type="primary"><Link to="/discovery">审核队列 <RightOutlined /></Link></Button></div>
      </header>

      <section className="signal-hero">
        <div className="signal-hero-number"><p>今日新发现</p><strong>+{review.value || 18}</strong><span>条需人工确认的岗位与能力变更</span></div>
        <div className="signal-hero-copy"><p>先处理高置信度变化，再进入关联图谱查看影响范围。</p><div><span>已收录 <b>{positions.value || 1286}</b> 个岗位</span><span>覆盖 <b>{byTitle(data.stats, '能力节点').value || 3468}</b> 个能力节点</span></div></div>
      </section>

      <section className="signal-main-grid">
        <div className="signal-trend">
          <div className="prototype-section-title"><div><p>MARKET TEMPERATURE</p><h2>需求热度正在转向 Agent 工作流</h2></div><span><ArrowUpOutlined /> 8.4%</span></div>
          <div className="signal-chart"><DemandChart data={data.demandTrend} accent="#2548d8" /></div>
          <div className="signal-caption"><span><i className="dot-blue" />人工智能</span><span><i className="dot-lilac" />大数据</span><span>按近 6 个月公开岗位信号汇总</span></div>
        </div>
        <aside className="signal-queue"><div className="prototype-section-title"><div><p>REVIEW DESK</p><h2>优先处理</h2></div><Link to="/discovery">查看全部 <RightOutlined /></Link></div><Queue tasks={data.reviewTasks} /></aside>
      </section>

      <section className="signal-sources"><p>DATA FEEDS</p>{data.sources.map((source) => <div key={source.name}><strong>{source.name}</strong><span>{source.freshness}</span><b>{source.coverage}%</b></div>)}</section>
      {showSwitcher && <PrototypeSwitcher variant="A" />}
    </main>
  );
};

const ResearchAtlas = ({ data, showSwitcher }) => {
  const nodes = byTitle(data.stats, '能力节点');

  return (
    <main className="prototype-page prototype-b">
      <header className="atlas-head"><div><p>RESEARCH ATLAS / XH-202621</p><h1>人才市场的变化，不止一条趋势。</h1></div><Link to="/graph" className="atlas-link"><ExpandOutlined /> 打开关系图谱</Link></header>
      <section className="atlas-stage">
        <div className="atlas-brief"><p>ACTIVE FIELD</p><strong>{nodes.value || 3468}</strong><span>能力节点正在被持续校准</span><div className="atlas-rule" /><small>本周，岗位与能力之间新增 672 条有效关系。</small></div>
        <div className="atlas-map" aria-label="岗位能力关系预览"><span className="atlas-node atlas-node-main">大模型应用工程师</span><span className="atlas-node atlas-node-a">RAG</span><span className="atlas-node atlas-node-b">Agent 工作流</span><span className="atlas-node atlas-node-c">模型评测</span><span className="atlas-node atlas-node-d">提示工程</span><i className="atlas-line atlas-line-a" /><i className="atlas-line atlas-line-b" /><i className="atlas-line atlas-line-c" /><i className="atlas-line atlas-line-d" /></div>
        <div className="atlas-context"><p>OBSERVATION</p><h2>“Agent 工作流”正在从技术栈变成岗位描述中的核心能力。</h2><span>来自招聘平台、行业报告与技术社区的交叉证据</span><Link to="/evolution">查看演化证据 <RightOutlined /></Link></div>
      </section>
      <section className="atlas-footer"><div><p>待审核</p><strong>{byTitle(data.stats, '待审核任务').value || 18}</strong><span>项高价值信号</span></div><div><p>来源健康度</p><strong>{byTitle(data.stats, '数据健康度').value || 92}%</strong><span>可用于本次分析</span></div><div className="atlas-mini-chart"><p>热度轨迹</p><div><DemandChart data={data.demandTrend} accent="#ef5d4b" minimal /></div></div></section>
      {showSwitcher && <PrototypeSwitcher variant="B" />}
    </main>
  );
};

const IndexLedger = ({ data, showSwitcher }) => (
  <main className="prototype-page prototype-c">
    <header className="ledger-head"><div><p>THE JOB INDEX</p><h1>岗位不是静态描述，<br />而是一组正在移动的证据。</h1></div><div><span>2026 / 07 / 25</span><Link to="/discovery">进入发现库 <ArrowRightOutlined /></Link></div></header>
    <section className="ledger-strip">
      {data.stats.map((stat, index) => <div key={stat.title}><small>0{index + 1}</small><span>{stat.title}</span><strong>{stat.value}{stat.suffix}</strong><em>{stat.trend}</em></div>)}
    </section>
    <section className="ledger-body">
      <div className="ledger-editorial"><p>EDITOR'S SIGNAL</p><h2>本周最值得关注的不是岗位数量，而是岗位中能力表达的变化。</h2><span>制造业与企业服务领域中，模型评测、数据治理和 Agent 协作开始同时出现。</span><Link to="/evolution">查看岗位版本 <RightOutlined /></Link></div>
      <div className="ledger-list"><div className="ledger-list-head"><p>待进入研究队列</p><Link to="/discovery">全部任务</Link></div><Queue tasks={data.reviewTasks} /></div>
    </section>
    <section className="ledger-chart"><div><p>6 MONTHS / DEMAND INDEX</p><h2>人工智能岗位热度</h2></div><div className="ledger-chart-frame"><DemandChart data={data.demandTrend} accent="#2f4dc7" /></div></section>
    {showSwitcher && <PrototypeSwitcher variant="C" />}
  </main>
);

const PrototypeSwitcher = ({ variant }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const currentIndex = variants.findIndex((item) => item.key === variant);
  const move = (offset) => {
    const next = variants[(currentIndex + offset + variants.length) % variants.length];
    const search = new URLSearchParams(location.search);
    search.set('variant', next.key);
    navigate({ pathname: location.pathname, search: `?${search.toString()}` });
  };

  useEffect(() => {
    const onKeyDown = (event) => {
      const tag = document.activeElement?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable) return;
      if (event.key === 'ArrowLeft') move(-1);
      if (event.key === 'ArrowRight') move(1);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  if (process.env.NODE_ENV === 'production') return null;
  const item = variants[currentIndex];
  return <div className="prototype-switcher"><Button type="text" icon={<ArrowLeftOutlined />} aria-label="上一种原型" onClick={() => move(-1)} /><span><b>{item.key}</b> {item.name}</span><Button type="text" icon={<ArrowRightOutlined />} aria-label="下一种原型" onClick={() => move(1)} /><Link to="/"><CloseOutlined /></Link></div>;
};

const DashboardStylePrototype = ({ data, variant, showSwitcher = false }) => {
  if (variant === 'B') return <ResearchAtlas data={data} showSwitcher={showSwitcher} />;
  if (variant === 'C') return <IndexLedger data={data} showSwitcher={showSwitcher} />;
  return <SignalDesk data={data} showSwitcher={showSwitcher} />;
};

export default DashboardStylePrototype;
