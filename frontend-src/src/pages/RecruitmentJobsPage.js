import React, { useEffect, useMemo, useState } from 'react';
import { App as AntdApp, Button, Input, InputNumber, Modal, Select, Skeleton } from 'antd';
import {
  ArrowRightOutlined,
  EditOutlined,
  PauseCircleOutlined,
  PlusOutlined,
  SaveOutlined,
  SearchOutlined,
  SendOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import PageHeading from '../components/workbench/PageHeading';
import { getRecruitmentJobs, saveRecruitmentJob } from '../services/talentApi';
import '../components/workbench/recruitment.css';

const statusClass = { '招聘中': 'live', '草稿': 'draft', '已暂停': 'paused' };

const RecruitmentJobsPage = () => {
  const { message } = AntdApp.useApp();
  const [jobs, setJobs] = useState([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [dataSource, setDataSource] = useState('loading');
  const [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('全部状态');
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [newJob, setNewJob] = useState({ title: '', department: '', location: '', openings: 1 });

  useEffect(() => {
    getRecruitmentJobs().then((result) => {
      setJobs(result.items);
      setJobTotal(result.total);
      setDataSource(result.source);
      setSelectedId(result.items[0]?.id || null);
      if (result.warning) message.warning('后端未连接，当前展示 Mock 回退数据');
    });
  }, [message]);

  const visibleJobs = useMemo(() => jobs.filter((job) => {
    const matchesQuery = `${job.title} ${job.department} ${job.id}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (status === '全部状态' || job.status === status);
  }), [jobs, query, status]);
  const selected = jobs.find((job) => job.id === selectedId) || visibleJobs[0];

  useEffect(() => {
    setEditing(false);
    setDraft(selected ? { ...selected } : null);
  }, [selectedId, selected]);

  const updateDraft = (key, value) => setDraft((current) => ({ ...current, [key]: value }));

  const saveDraft = async () => {
    try {
      const saved = await saveRecruitmentJob({ ...draft, updatedAt: '刚刚' });
      setJobs((current) => current.map((job) => job.id === saved.id ? saved : job));
      setDraft(saved);
      setEditing(false);
      message.success(saved.warning ? '仅在当前 Mock 页面中更新' : 'JD 修改已持久化保存');
    } catch (error) {
      message.error(error.message || 'JD 保存失败');
    }
  };

  const changeStatus = async () => {
    const nextStatus = selected.status === '招聘中' ? '已暂停' : '招聘中';
    try {
      const saved = await saveRecruitmentJob({ ...selected, status: nextStatus, publishedAt: nextStatus === '招聘中' && selected.publishedAt === '尚未发布' ? '今天' : selected.publishedAt, updatedAt: '刚刚' });
      setJobs((current) => current.map((job) => job.id === saved.id ? saved : job));
      message.success(nextStatus === '招聘中' ? '招聘 JD 已发布' : '招聘已暂停');
    } catch (error) {
      message.error(error.message || '招聘状态保存失败');
    }
  };

  const createJob = async () => {
    if (!newJob.title.trim() || !newJob.department.trim()) {
      message.warning('请填写岗位名称和所属部门');
      return;
    }
    const id = `JD-2026-${String(jobs.length + 20).padStart(3, '0')}`;
    const created = {
      ...newJob,
      id,
      employmentType: '全职',
      status: '草稿',
      version: 'JD v0.1',
      roleVersion: '待关联标准岗位',
      publishedAt: '尚未发布',
      updatedAt: '刚刚',
      applications: 0,
      newApplications: 0,
      summary: '请补充该招聘岗位的业务背景、目标和职责边界。',
      responsibilities: ['补充核心职责'],
      requiredSkills: [],
      bonusSkills: [],
      revisions: [{ version: 'v0.1', date: '今天', note: '创建招聘 JD 草稿' }],
      marketSuggestion: null,
      dataSource: dataSource === 'mock-fallback' ? 'mock-fallback' : 'live-standard-dataset',
    };
    try {
      const saved = await saveRecruitmentJob(created);
      setJobs((current) => [saved, ...current]);
      setJobTotal((current) => current + 1);
      setSelectedId(id);
      setCreateOpen(false);
      setNewJob({ title: '', department: '', location: '', openings: 1 });
      message.success(saved.warning ? 'Mock 草稿已在当前页面创建' : 'JD 草稿已持久化创建');
    } catch (error) {
      message.error(error.message || 'JD 草稿创建失败');
    }
  };

  if (!jobs.length) return <div className="page-loading"><Skeleton active paragraph={{ rows: 12 }} /></div>;

  return <div className="workbench-page recruitment-page">
    <PageHeading eyebrow="RECRUITMENT JD POOL" title="我的招聘" description="读取标准企业岗位池，维护 JD 人工调整、发布状态和市场更新建议。">
      <span className={`market-runtime-badge ${dataSource === 'mock-fallback' ? 'offline' : 'live'}`}>
        {dataSource === 'mock-fallback' ? 'Mock 回退' : '标准数据已连接'}
      </span>
      <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建 JD</Button>
    </PageHeading>

    <div className="recruitment-toolbar">
      <Input prefix={<SearchOutlined />} placeholder="搜索岗位、部门或 JD 编号" value={query} onChange={(event) => setQuery(event.target.value)} allowClear />
      <Select value={status} onChange={setStatus} options={['全部状态', '招聘中', '草稿', '已暂停'].map((value) => ({ value }))} />
      <span>当前显示 {visibleJobs.length} 个 · 企业岗位池共 {jobTotal} 个</span>
    </div>

    <section className="recruitment-workspace">
      <aside className="recruitment-job-list">
        <header><span>MY JOB POSTINGS</span><b>{visibleJobs.length}</b></header>
        <div>{visibleJobs.map((job) => <button type="button" key={job.id} className={job.id === selected?.id ? 'active' : ''} onClick={() => setSelectedId(job.id)}>
          <span><i className={`job-status-dot ${statusClass[job.status]}`} />{job.status}<small>{job.id}</small></span>
          <strong>{job.title}</strong>
          <small>{job.department} · {job.location}</small>
          <footer><b>{job.sourceType === 'enterprise' ? '企业岗位' : job.sourceType}</b><em>{job.publishedAt}</em></footer>
        </button>)}</div>
      </aside>

      {selected && draft && <main className="recruitment-job-detail">
        <header className="recruitment-detail-header">
          <div><span>{selected.id} · {selected.roleVersion}</span><h2>{selected.title}</h2><p>{selected.department} · {selected.location} · {selected.employmentType}</p></div>
          <div className="recruitment-detail-actions">
            {editing ? <Button icon={<SaveOutlined />} onClick={saveDraft}>保存修改</Button> : <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑 JD</Button>}
            <Button icon={selected.status === '招聘中' ? <PauseCircleOutlined /> : <SendOutlined />} onClick={changeStatus}>{selected.status === '招聘中' ? '暂停招聘' : '发布招聘'}</Button>
            <Link to={`/candidates?job=${selected.id}`}><Button className="candidate-view-button" type="primary" icon={<TeamOutlined />}>查看候选人 <ArrowRightOutlined /></Button></Link>
          </div>
        </header>

        <section className="recruitment-facts">
          <div><span>招聘状态</span><strong className={`job-state-text ${statusClass[selected.status]}`}>{selected.status}</strong></div>
          <div><span>招聘人数</span>{editing ? <InputNumber min={1} value={draft.openings} onChange={(value) => updateDraft('openings', value)} /> : <strong>{selected.openings} 人</strong>}</div>
          <div><span>候选结果</span><strong>进入匹配页计算</strong></div>
          <div><span>当前修订</span><strong>{selected.version}</strong></div>
        </section>

        <section className="recruitment-content-section">
          <span>岗位说明</span>
          {editing ? <Input.TextArea rows={4} value={draft.summary} onChange={(event) => updateDraft('summary', event.target.value)} /> : <p>{selected.summary}</p>}
        </section>
        <section className="recruitment-content-section">
          <span>核心职责</span>
          {editing ? <Input.TextArea rows={4} value={draft.responsibilities.join('\n')} onChange={(event) => updateDraft('responsibilities', event.target.value.split('\n').filter(Boolean))} /> : <ol>{selected.responsibilities.map((item) => <li key={item}>{item}</li>)}</ol>}
        </section>
        <section className="recruitment-content-section">
          <span>必备技能</span>
          <div className="jd-skill-grid">{selected.requiredSkills.length ? selected.requiredSkills.map((skill) => <div key={skill.name}><header><strong>{skill.name}</strong><b>{skill.level}</b></header><i><u style={{ width: `${skill.level}%` }} /></i></div>) : <p>尚未配置，请从标准岗位画像中选择技能并人工调整。</p>}</div>
        </section>
        <section className="recruitment-content-section recruitment-revisions">
          <span>JD 修订记录</span>
          {selected.revisions.map((revision) => <div key={revision.version}><b>{revision.version}</b><time>{revision.date}</time><p>{revision.note}</p></div>)}
        </section>
      </main>}

      {selected && <aside className="recruitment-context-panel">
        <header><span>RECRUITMENT STATUS</span><b>{selected.version}</b></header>
        <section><span>投递处理</span><strong>{selected.newApplications}</strong><p>份新简历等待筛选</p><Link to={`/candidates?job=${selected.id}`}>进入候选匹配 <ArrowRightOutlined /></Link></section>
        <section className="market-advice">
          <span>市场更新建议</span>
          {selected.marketSuggestion ? <><strong>{selected.marketSuggestion.title}</strong><p>{selected.marketSuggestion.detail}</p><footer><b>{selected.marketSuggestion.confidence}% 置信度</b><small>{selected.marketSuggestion.evidence} 条证据</small></footer><Link to="/signals">查看市场依据 <ArrowRightOutlined /></Link></> : <p>当前没有需要处理的市场更新建议。</p>}
        </section>
        <section><span>最近更新</span><strong className="context-date">{selected.updatedAt}</strong><p>所有修改均保留人工操作记录。</p></section>
      </aside>}
    </section>

    <Modal title="新建招聘 JD" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={createJob} okText="创建草稿" cancelText="取消">
      <div className="create-jd-form">
        <label>岗位名称<Input value={newJob.title} onChange={(event) => setNewJob((current) => ({ ...current, title: event.target.value }))} placeholder="例如：大模型应用工程师" /></label>
        <label>所属部门<Input value={newJob.department} onChange={(event) => setNewJob((current) => ({ ...current, department: event.target.value }))} placeholder="例如：AI 应用平台部" /></label>
        <label>工作地点<Input value={newJob.location} onChange={(event) => setNewJob((current) => ({ ...current, location: event.target.value }))} placeholder="例如：合肥 · 混合办公" /></label>
        <label>招聘人数<InputNumber min={1} value={newJob.openings} onChange={(value) => setNewJob((current) => ({ ...current, openings: value }))} /></label>
      </div>
    </Modal>
  </div>;
};

export default RecruitmentJobsPage;
