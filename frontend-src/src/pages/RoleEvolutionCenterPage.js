import React, { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from 'react-query';
import { App as AntdApp, Button, Card, Input, Progress, Select, Space, Tag, Timeline } from 'antd';
import {
  ArrowRightOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileSearchOutlined,
  NodeIndexOutlined,
  PlusOutlined,
  ReloadOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import PageHeading from '../components/workbench/PageHeading';
import TechnicalInspector from '../components/workbench/TechnicalInspector';
import {
  getRoleEvolutionWorkspace,
  saveRoleOptimization,
  submitRoleJd,
} from '../services/talentApi';
import './RoleEvolutionCenterPage.css';

const views = [
  { key: 'jd-update', label: '单条 JD 更新', hint: '提交岗位信息并生成变化预览' },
  { key: 'live-evolution', label: '实时岗位演化', hint: '查看本次更新影响的岗位能力' },
  { key: 'analytics', label: '时序分析', hint: '追踪趋势、生命周期和迁移' },
  { key: 'optimization', label: '人工优化', hint: '维护岗位定义并发布版本' },
];

const changeGroups = [
  { key: 'added', label: '新增能力', tone: 'added' },
  { key: 'removed', label: '移除能力', tone: 'removed' },
  { key: 'modified', label: '调整说明', tone: 'modified' },
];

const initialForm = {
  processing_mode: 'manual',
  month: '2026-08',
  job_title: '大模型应用工程师',
  responsibility: '',
  requirement: '',
};

const safeList = (value) => (Array.isArray(value) ? value : []);

const ChangeGroup = ({ title, items, tone }) => (
  <div className="role-evolution-change-group">
    <span>{title}</span>
    <div>{safeList(items).length ? safeList(items).map((item) => <Tag key={item} className={`role-evolution-token ${tone}`}>{item}</Tag>) : <span className="role-evolution-muted">无</span>}</div>
  </div>
);

const Metric = ({ label, value, detail }) => (
  <div className="role-evolution-metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
);

const RoleEvolutionCenterPage = () => {
  const { message } = AntdApp.useApp();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeView, setActiveView] = useState('jd-update');
  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitted, setSubmitted] = useState(null);
  const [selectedRole, setSelectedRole] = useState('大模型应用工程师');
  const [editedSkills, setEditedSkills] = useState([]);
  const [newSkill, setNewSkill] = useState('');

  const { data, isLoading, refetch: refreshWorkspace } = useQuery(
    'role-evolution-workspace',
    getRoleEvolutionWorkspace,
    { staleTime: 5 * 60 * 1000, cacheTime: 30 * 60 * 1000 },
  );

  useEffect(() => {
    if (!data) return;
    setSelectedRole((current) => data.jobs.some((job) => job.name === current) ? current : data.optimization?.name || data.analytics.role);
    setEditedSkills(safeList(data.optimization?.requiredSkills).map((skill) => typeof skill === 'string' ? skill : skill.name));
  }, [data]);

  const selectedJob = useMemo(() => data?.jobs?.find((job) => job.name === selectedRole) || data?.optimization, [data, selectedRole]);
  const latest = submitted || data?.latest;
  const updateForm = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.job_title.trim()) {
      message.error('请先填写岗位名称');
      return;
    }
    setSubmitting(true);
    try {
      const result = await submitRoleJd(form);
      setSubmitted(result);
      setActiveView('live-evolution');
      message.success('JD 已完成解析，岗位演化结果已生成');
    } catch (error) {
      message.error(error.message || 'JD 处理失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const result = await saveRoleOptimization({ standard_job: selectedRole, changes: editedSkills.map((skill) => ({ normalized_skill: skill })) });
      message.success(`${result.version || '新版本'} 已保存，等待发布确认`);
      queryClient.setQueryData('role-evolution-workspace', (current) => current ? {
        ...current,
        optimization: { ...current.optimization, requiredSkills: editedSkills.map((name) => ({ name })) },
      } : current);
    } catch (error) {
      message.error(error.message || '岗位优化保存失败');
    } finally {
      setSaving(false);
    }
  };

  const openView = (view) => setActiveView(view);
  const openContextualRoute = (path) => {
    localStorage.setItem('roleEvolutionContext', JSON.stringify({ role: latest.role, version: latest.version, updatedAt: latest.updatedAt }));
    navigate(path);
  };

  if (isLoading || !data) return <div className="workbench-page role-evolution-page"><div className="page-loading">正在加载岗位演化工作区...</div></div>;

  return (
    <div className="workbench-page role-evolution-page">
      <PageHeading eyebrow="ROLE EVOLUTION CENTER" title="岗位演化中心" description="从一条市场 JD 出发，追踪岗位能力变化、版本证据与人工维护结果。">
        <Button icon={<ReloadOutlined />} onClick={() => refreshWorkspace()}>刷新工作区</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openView('jd-update')}>更新一条 JD</Button>
      </PageHeading>

      <section className="role-evolution-overview" aria-label="岗位演化摘要">
        <Metric label="待处理信号" value={data.pending.length} detail="新岗位与能力变化" />
        <Metric label="当前岗位" value={data.analytics.role} detail={`版本 ${latest.version}`} />
        <Metric label="本次变化" value={safeList(latest.added).length + safeList(latest.modified).length} detail="新增与调整能力" />
        <Metric label="待交叉验证" value={latest.candidateSkillCount || 0} detail="候选能力暂不写入基线" />
        <Metric label="证据数量" value={latest.evidence || 0} detail="已关联来源记录" />
      </section>

      <nav className="role-evolution-tabs" aria-label="岗位演化功能">
        {views.map((view) => <button key={view.key} className={activeView === view.key ? 'active' : ''} onClick={() => openView(view.key)}><strong>{view.label}</strong><span>{view.hint}</span></button>)}
      </nav>

      {activeView === 'jd-update' && <section className="role-evolution-grid">
        <form className="role-evolution-panel role-evolution-form" onSubmit={handleSubmit}>
          <header><div><span>INPUT</span><h2>提交一条岗位 JD</h2></div><Tag color="blue">人工确认模式</Tag></header>
          <p className="role-evolution-intro">系统会先完成岗位归类、技能抽取和变化预览，确认后再进入正式岗位版本。</p>
          <div className="role-evolution-form-grid">
            <label>处理模式<Select value={form.processing_mode} onChange={(value) => updateForm('processing_mode', value)} options={[{ value: 'manual', label: '人工确认模式' }, { value: 'auto', label: '自动模式' }]} /></label>
            <label>数据月份<Input value={form.month} onChange={(event) => updateForm('month', event.target.value)} /></label>
          </div>
          <label>岗位名称<Input value={form.job_title} onChange={(event) => updateForm('job_title', event.target.value)} placeholder="例如：大模型应用工程师" /></label>
          <label>岗位职责<Input.TextArea rows={5} value={form.responsibility} onChange={(event) => updateForm('responsibility', event.target.value)} placeholder="粘贴 JD 中的岗位职责" /></label>
          <label>岗位要求<Input.TextArea rows={5} value={form.requirement} onChange={(event) => updateForm('requirement', event.target.value)} placeholder="粘贴 JD 中的技能和任职要求" /></label>
          <footer><span className="role-evolution-muted">支持自动判断，也支持人工确认后再入库</span><Button type="primary" htmlType="submit" loading={submitting} icon={<SendOutlined />}>开始判断 <ArrowRightOutlined /></Button></footer>
        </form>

        <aside className="role-evolution-panel role-evolution-result-panel">
          <header><div><span>LAST RESULT</span><h2>最近一次演化</h2></div><Tag color={latest.status === '已发布' ? 'green' : 'gold'}>{latest.status}</Tag></header>
          <div className="role-evolution-result-title"><div><small>{latest.id} · {latest.updatedAt}</small><h3>{latest.role}</h3></div><strong>{latest.version}</strong></div>
          <p>{latest.summary}</p>
          <div className="role-evolution-change-list">{changeGroups.map((group) => <ChangeGroup key={group.key} title={group.label} items={latest[group.key]} tone={group.tone} />)}</div>
          <div className="role-evolution-next-step"><CheckCircleOutlined /><div><strong>下一步：查看实时岗位演化</strong><span>确认本次变化的来源、影响范围和岗位版本。</span></div><Button type="link" onClick={() => openView('live-evolution')}>查看 <ArrowRightOutlined /></Button></div>
        </aside>
      </section>}

      {activeView === 'live-evolution' && <section className="role-evolution-grid role-evolution-live-grid">
        <main className="role-evolution-panel">
          <header><div><span>LIVE EFFECT</span><h2>{latest.role} · 本次岗位演化</h2></div><Tag color="gold">{latest.status}</Tag></header>
          <div className="role-evolution-effect-header"><div><small>变化版本</small><strong>{latest.version}</strong></div><div><small>更新时间</small><strong>{latest.updatedAt}</strong></div><div><small>关联证据</small><strong>{latest.evidence || 0} 条</strong></div><div><small>候选能力</small><strong>{latest.candidateSkillCount || 0} 项</strong></div></div>
          <p className="role-evolution-summary">{latest.summary}</p>
          <div className="role-evolution-change-columns">{changeGroups.map((group) => <ChangeGroup key={group.key} title={group.label} items={latest[group.key]} tone={group.tone} />)}</div>
          <div className="role-evolution-action-row"><Button onClick={() => openView('analytics')} icon={<BarChartOutlined />}>查看历史趋势</Button><Button onClick={() => openContextualRoute('/graph')} icon={<NodeIndexOutlined />}>打开全景图谱</Button><Button type="primary" onClick={() => openView('optimization')} icon={<FileSearchOutlined />}>进入人工优化</Button></div>
        </main>
        <TechnicalInspector title="岗位演化证据" status="待确认" version={latest.version} confidence={Math.min(99, 70 + Number(latest.evidence || 0))} explanation={[latest.summary, ...safeList(latest.modified)]} evidence={[
          { source: '市场 JD 输入', confidence: '本次提交', excerpt: form.job_title || latest.role, collectedAt: form.month },
          { source: '岗位技能抽取', confidence: `${latest.evidence || 0} 条证据`, excerpt: safeList(latest.added).join('、') || '未发现新增能力', collectedAt: latest.updatedAt },
          { source: '岗位画像版本', confidence: latest.version, excerpt: '变化结果保留新增、删除和修改三类差异。', collectedAt: latest.updatedAt },
        ]} history={[{ label: '完成 JD 解析与岗位归类', time: latest.updatedAt }, { label: latest.candidateSkillCount ? `${latest.candidateSkillCount} 项新增能力进入交叉验证候选池` : '技能均已通过岗位能力验证', time: latest.updatedAt }, { label: '等待人工确认发布', time: '当前' }]} />
      </section>}

      {activeView === 'analytics' && <section className="role-evolution-analytics">
        <div className="role-evolution-analytics-toolbar"><div><span>TIME SERIES</span><h2>岗位技能时序分析</h2><p>从频率、生命周期和迁移路径观察岗位能力如何变化。</p></div><Select value={selectedRole} onChange={setSelectedRole} options={data.jobs.map((job) => ({ value: job.name, label: job.name }))} /></div>
        <div className="role-evolution-analytics-grid">
          <Card title="技能需求趋势" className="role-evolution-card"><div className="role-evolution-trend-chart">{data.analytics.trend.map((point) => <div className="role-evolution-trend-point" key={point.month}><i style={{ height: `${Math.round(point.frequency * 100)}%` }} /><span>{point.month.slice(5)}</span><b>{Math.round(point.frequency * 100)}%</b></div>)}</div></Card>
          <Card title="岗位版本时间轴" className="role-evolution-card"><Timeline items={safeList(data.analytics.versions).map((version) => ({ color: version.version === latest.version ? '#16846b' : '#b8c0c9', children: <div className="role-evolution-version"><strong>{version.version}</strong><span>{version.date}</span><p>{version.summary}</p></div> }))} /></Card>
          <Card title="技能生命周期" className="role-evolution-card"><div className="role-evolution-lifecycle">{safeList(data.analytics.lifecycle).map((item) => <div key={item.skill}><span><strong>{item.skill}</strong><small>{item.status}</small></span><Progress percent={Math.round(item.frequency * 100)} showInfo={false} /><b>{item.change}</b></div>)}</div></Card>
          <Card title="技能迁移路径" className="role-evolution-card"><div className="role-evolution-migrations">{safeList(data.analytics.migration).map((item) => <div key={`${item.from}-${item.to}`}><span>{item.from}</span><ArrowRightOutlined /><strong>{item.to}</strong><Tag>{Math.round(item.weight * 100)}%</Tag></div>)}</div></Card>
        </div>
      </section>}

      {activeView === 'optimization' && <section className="role-evolution-grid">
        <main className="role-evolution-panel role-evolution-optimization"><header><div><span>ROLE DEFINITION</span><h2>人工优化岗位定义</h2></div><Tag color="blue">草稿</Tag></header><label>选择岗位<Select value={selectedRole} onChange={(value) => { setSelectedRole(value); const job = data.jobs.find((item) => item.name === value); setEditedSkills(safeList(job?.requiredSkills).map((skill) => typeof skill === 'string' ? skill : skill.name)); }} options={data.jobs.map((job) => ({ value: job.name, label: job.name }))} /></label><div className="role-evolution-definition"><span>岗位摘要</span><p>{selectedJob?.summary || '当前岗位暂无摘要。'}</p></div><div className="role-evolution-skill-editor"><header><span>必备技能</span><small>可编辑当前岗位能力要求</small></header><div>{editedSkills.map((skill) => <Tag closable key={skill} onClose={() => setEditedSkills((items) => items.filter((item) => item !== skill))}>{skill}</Tag>)}</div><Space.Compact className="role-evolution-add-skill"><Input value={newSkill} onChange={(event) => setNewSkill(event.target.value)} placeholder="新增规范技能" onPressEnter={() => { if (newSkill.trim()) { setEditedSkills((items) => [...items, newSkill.trim()]); setNewSkill(''); } }} /><Button icon={<PlusOutlined />} onClick={() => { if (newSkill.trim()) { setEditedSkills((items) => [...items, newSkill.trim()]); setNewSkill(''); } }}>添加</Button></Space.Compact></div><footer><span className="role-evolution-muted">人工修改会作为独立覆盖层保存，不改写原始历史数据。</span><Button type="primary" loading={saving} icon={<CheckCircleOutlined />} onClick={handleSave}>保存本次变更</Button></footer></main>
        <aside className="role-evolution-panel role-evolution-publish-panel"><header><div><span>PUBLISH CHECK</span><h2>发布前检查</h2></div><ClockCircleOutlined /></header><div className="role-evolution-check-list"><p><CheckCircleOutlined /><span>岗位名称已归一化<strong>{selectedRole}</strong></span></p><p><CheckCircleOutlined /><span>技能项已去重<strong>{editedSkills.length} 项必备技能</strong></span></p><p><ClockCircleOutlined /><span>等待人工确认<strong>保存后生成新版本</strong></span></p></div><div className="role-evolution-publish-note">发布后的岗位版本会同步到全景图谱，并作为人岗诊断的目标岗位依据。</div><Button block onClick={() => openContextualRoute('/diagnosis')} icon={<FileSearchOutlined />}>查看人岗诊断</Button></aside>
      </section>}
    </div>
  );
};

export default RoleEvolutionCenterPage;
