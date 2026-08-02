import React, { useEffect, useMemo, useState } from 'react';
import { App as AntdApp, Button, Input, Progress, Skeleton, Upload } from 'antd';
import { ArrowRightOutlined, CheckOutlined, EditOutlined, PlusOutlined, SendOutlined } from '@ant-design/icons';
import PageHeading from '../components/workbench/PageHeading';
import TechnicalInspector from '../components/workbench/TechnicalInspector';
import {
  getDiscoveryCandidates,
  getLiveMarketTrend,
  getMarketChangeCandidates,
  getMarketRuntimeStatus,
  importMarketCsv,
  reviewDiscoveryCandidate,
} from '../services/talentApi';

const { TextArea } = Input;

const statusClass = { '待审核': 'review', '补充证据': 'evidence', '已发布': 'published' };

const buildEvidence = (item, liveTrend, trendSkill) => [
  { source: '企业招聘官网', confidence: '可信度 0.94', excerpt: item.signals[0], collectedAt: item.updatedAt },
  { source: '主流招聘平台', confidence: '交叉验证', excerpt: `与“${item.skills.slice(0, 2).join('、')}”相关的能力组合连续四周高频共现。`, collectedAt: '2026-07-25 08:30' },
  { source: '行业报告与白皮书', confidence: '专家复核', excerpt: `${item.name}的职责边界与应用场景正在形成稳定表达。`, collectedAt: '2026-07-24 18:40' },
  ...(liveTrend && trendSkill ? [{
    source: '市场趋势接口',
    confidence: '后端实时查询',
    excerpt: `${trendSkill} 当前关联岗位/技能关系数：${liveTrend.skill_demand?.[trendSkill] ?? '未返回'}。`,
    collectedAt: '本次页面查询',
  }] : []),
];

const normalizeRelatedSkills = (items) => (Array.isArray(items) ? items : [])
  .map((item) => typeof item === 'string' ? item : item?.skill || item?.name)
  .filter(Boolean)
  .slice(0, 6);

const MarketSignalItem = ({ item, active, onClick }) => (
  <button className={`signal-list-item ${active ? 'active' : ''}`} onClick={onClick}>
    <span className="signal-item-top"><b>{item.id}</b><i className={`status-dot-inline ${statusClass[item.status]}`}>{item.status}</i></span>
    <strong>{item.name}</strong>
    <small>{item.signals[0]}</small>
    <span className="signal-item-foot"><em>{item.evidence} 条证据</em><b>{item.confidence}%</b></span>
  </button>
);

const SkillToken = ({ children, tone = 'required' }) => <span className={`definition-skill ${tone}`}>{children}</span>;

const DiscoveryPage = () => {
  const { message } = AntdApp.useApp();
  const [newRoles, setNewRoles] = useState([]);
  const [changes, setChanges] = useState([]);
  const [activeTab, setActiveTab] = useState('new');
  const [selectedId, setSelectedId] = useState(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ name: '', summary: '' });
  const [runtime, setRuntime] = useState(null);
  const [liveTrend, setLiveTrend] = useState(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    Promise.all([getDiscoveryCandidates(), getMarketChangeCandidates()]).then(([roles, updates]) => {
      setNewRoles(roles);
      setChanges(updates);
      setSelectedId(roles[0]?.id);
    });
  }, []);

  useEffect(() => {
    let active = true;
    getMarketRuntimeStatus().then((status) => {
      if (active) setRuntime(status);
    }).catch(() => {
      if (active) setRuntime({ available: false, ingestion: null, bm25: null });
    });
    return () => { active = false; };
  }, []);

  const visibleItems = activeTab === 'new' ? newRoles : activeTab === 'change' ? changes : [...newRoles, ...changes].filter((item) => item.status === '已发布');
  const selected = useMemo(() => visibleItems.find((item) => item.id === selectedId) || visibleItems[0], [visibleItems, selectedId]);

  useEffect(() => {
    if (!selected) return;
    setDraft({
      name: selected.name,
      summary: activeTab === 'change'
        ? '根据最新市场证据调整岗位能力要求，并保留完整版本差异。'
        : `负责${selected.skills.slice(0, 2).join('、')}相关系统的设计、开发、评估与持续优化。`,
    });
    setEditing(false);
  }, [selected, activeTab]);

  const trendSkill = selected?.skills?.[0] || null;
  useEffect(() => {
    let active = true;
    setLiveTrend(null);
    if (!trendSkill) return () => { active = false; };
    setTrendLoading(true);
    getLiveMarketTrend(trendSkill)
      .then((result) => { if (active && Object.keys(result || {}).length) setLiveTrend(result); })
      .catch(() => {})
      .finally(() => { if (active) setTrendLoading(false); });
    return () => { active = false; };
  }, [trendSkill]);

  const relatedSkills = normalizeRelatedSkills(liveTrend?.related_skills?.[trendSkill]);
  const indexedJobs = runtime?.bm25?.document_count ?? runtime?.ingestion?.total_jobs_elasticsearch;

  const importCsv = async (file) => {
    if (!/\.csv$/i.test(file.name || '')) {
      message.error('请选择 CSV 格式的市场 JD 文件');
      return false;
    }
    setImporting(true);
    try {
      const result = await importMarketCsv(file);
      message.success(result.message || `${file.name} 已提交后台导入`);
      const status = await getMarketRuntimeStatus();
      setRuntime(status);
    } catch (importError) {
      message.error(importError.message || '市场 JD 导入失败');
    } finally {
      setImporting(false);
    }
    return false;
  };

  const switchTab = (tab) => {
    setActiveTab(tab);
    const items = tab === 'new' ? newRoles : tab === 'change' ? changes : [...newRoles, ...changes].filter((item) => item.status === '已发布');
    setSelectedId(items[0]?.id || null);
  };

  const review = async (decision) => {
    if (!selected) return;
    await reviewDiscoveryCandidate(selected.id, decision);
    const updater = (items) => items.map((item) => item.id === selected.id ? { ...item, status: decision === 'publish' ? '已发布' : '补充证据' } : item);
    if (activeTab === 'new') setNewRoles(updater);
    else setChanges(updater);
    message.success(decision === 'publish' ? `${selected.name} 已发布，图谱同步任务已创建` : '已退回补充证据');
  };

  if (!newRoles.length && !changes.length) return <div className="page-loading"><Skeleton active paragraph={{ rows: 12 }} /></div>;

  return (
    <div className="workbench-page signal-center-page">
      <PageHeading eyebrow="JOB MARKET RADAR" title="岗位市场雷达" description="把外部市场 JD 的新岗位、技能变化和岗位演变转化为带证据的人工审核建议。">
        <span className={`market-runtime-badge ${runtime?.available ? 'live' : 'offline'}`}>
          {runtime?.available ? `岗位索引 ${indexedJobs ?? '已连接'}` : '数据服务未连接'}
        </span>
        <Upload accept=".csv,text/csv" maxCount={1} showUploadList={false} beforeUpload={importCsv} disabled={importing}>
          <Button icon={<PlusOutlined />} loading={importing}>导入市场 JD</Button>
        </Upload>
      </PageHeading>

      <nav className="workflow-tabs" aria-label="市场信号类型">
        <button className={activeTab === 'new' ? 'active' : ''} onClick={() => switchTab('new')}>新岗位信号 <b>{newRoles.length}</b></button>
        <button className={activeTab === 'change' ? 'active' : ''} onClick={() => switchTab('change')}>能力变化信号 <b>{changes.length}</b></button>
        <button className={activeTab === 'processed' ? 'active' : ''} onClick={() => switchTab('processed')}>已处理记录</button>
      </nav>

      {selected ? <section className="signal-review-workspace">
        <aside className="signal-list-panel">
          <header><span>{activeTab === 'new' ? 'NEW ROLES' : activeTab === 'change' ? 'ROLE CHANGES' : 'PROCESSED'}</span><b>{visibleItems.length} 项</b></header>
          <div>{visibleItems.map((item) => <MarketSignalItem key={item.id} item={item} active={item.id === selected.id} onClick={() => setSelectedId(item.id)} />)}</div>
        </aside>

        <main className="definition-workspace">
          <header className="definition-header">
            <div><span>{selected.id} · {selected.domain}</span>{editing ? <Input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /> : <h2>{draft.name}</h2>}</div>
            <div className="definition-header-actions"><span className={`definition-state ${statusClass[selected.status]}`}>{selected.status}</span><Button icon={<EditOutlined />} onClick={() => setEditing((value) => !value)}>{editing ? '完成编辑' : '编辑定义'}</Button></div>
          </header>

          <div className="signal-scoreline">
            <div><span>综合置信度</span><strong>{selected.confidence}%</strong></div>
            <Progress percent={selected.confidence} showInfo={false} strokeColor="#4059c7" />
            <small>基于 {selected.evidence} 条有效证据，覆盖 3 类数据源</small>
          </div>

          <section className="live-market-snapshot">
            <header><span>LIVE MARKET SNAPSHOT</span><strong>{trendSkill || '待选择技能'}</strong></header>
            {trendLoading ? <Skeleton active paragraph={{ rows: 1 }} title={false} /> : liveTrend ? <div>
              <p><span>关联关系数</span><b>{liveTrend.skill_demand?.[trendSkill] ?? 0}</b></p>
              <p><span>图谱相关技能</span><strong>{relatedSkills.join('、') || '接口暂未返回相关技能'}</strong></p>
            </div> : <p className="live-market-empty">市场趋势接口当前不可用，审核候选仍为演示数据。</p>}
          </section>

          {activeTab === 'change' && <section className="version-diff">
            <header><span>VERSION DIFF</span><strong>{selected.version}</strong></header>
            <div><span>新增</span><p>{selected.added.map((skill) => <SkillToken tone="added" key={skill}>{skill}</SkillToken>)}</p></div>
            <div><span>删除</span><p>{selected.removed.length ? selected.removed.map((skill) => <SkillToken tone="removed" key={skill}>{skill}</SkillToken>) : '无'}</p></div>
            <div><span>修改</span><p>{selected.modified.map((skill) => <SkillToken tone="modified" key={skill}>{skill}</SkillToken>)}</p></div>
          </section>}

          <section className="definition-section">
            <span className="definition-label">岗位定义</span>
            {editing ? <TextArea rows={3} value={draft.summary} onChange={(event) => setDraft((current) => ({ ...current, summary: event.target.value }))} /> : <p>{draft.summary}</p>}
          </section>
          <section className="definition-section">
            <span className="definition-label">核心职责</span>
            <ol><li>分析业务场景并定义系统能力边界</li><li>设计、实现并验证核心技术链路</li><li>建立质量评测、监控与持续改进机制</li></ol>
          </section>
          <div className="definition-two-column">
            <section className="definition-section"><span className="definition-label">必备技能</span><div>{selected.skills.map((skill) => <SkillToken key={skill}>{skill}</SkillToken>)}</div></section>
            <section className="definition-section"><span className="definition-label">加分技能</span><div><SkillToken tone="bonus">行业知识</SkillToken><SkillToken tone="bonus">工程化交付</SkillToken><SkillToken tone="bonus">技术评测</SkillToken></div></section>
          </div>
          <section className="definition-section"><span className="definition-label">典型行业应用场景</span><div className="scenario-row"><span>企业服务</span><span>智能制造</span><span>研发效能</span></div></section>

          <footer className="definition-actions">
            <Button icon={<SendOutlined />} onClick={() => review('return')}>退回补证</Button>
            <Button type="primary" icon={<CheckOutlined />} onClick={() => review('publish')}>审核并发布 <ArrowRightOutlined /></Button>
          </footer>
        </main>

        <TechnicalInspector
          title="市场变化信号"
          status={selected.status === '已发布' ? '人工审核' : 'AI 生成'}
          version={activeTab === 'change' ? selected.version : '定义草稿 v0.1'}
          confidence={selected.confidence}
          explanation={selected.signals}
          evidence={buildEvidence(selected, liveTrend, trendSkill)}
          history={[
            { label: '完成多源交叉验证', time: selected.updatedAt },
            { label: '生成岗位定义草稿', time: '2026-07-25 09:36' },
            { label: '进入人工审核队列', time: '2026-07-25 09:42' },
          ]}
        />
      </section> : <div className="workflow-empty">当前分类下暂无已处理记录。</div>}
    </div>
  );
};

export default DiscoveryPage;
