import React, { useEffect, useMemo, useState } from 'react';
import { App as AntdApp, Button, Segmented, Select, Skeleton, Upload } from 'antd';
import { CheckOutlined, FileAddOutlined, FilePdfOutlined, SafetyCertificateOutlined, TeamOutlined, UserOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import PageHeading from '../components/workbench/PageHeading';
import { getJobCandidates, getRecruitmentJobs, updateCandidateStage } from '../services/talentApi';
import '../components/workbench/recruitment.css';

const stages = ['待筛选', '待沟通', '入围', '不匹配'];

const CandidateMatchingPage = () => {
  const { message } = AntdApp.useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState(searchParams.get('job'));
  const [candidates, setCandidates] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [stageFilter, setStageFilter] = useState('全部');

  useEffect(() => {
    getRecruitmentJobs().then((items) => {
      setJobs(items);
      const requested = searchParams.get('job');
      const nextId = items.some((job) => job.id === requested) ? requested : items.find((job) => job.status === '招聘中')?.id || items[0]?.id;
      setJobId(nextId);
    });
  }, [searchParams]);

  useEffect(() => {
    if (!jobId) return;
    setCandidates(null);
    getJobCandidates(jobId).then((items) => {
      setCandidates(items);
      setSelectedId(items[0]?.id || null);
      setSearchParams({ job: jobId }, { replace: true });
    });
  }, [jobId, setSearchParams]);

  const job = jobs.find((item) => item.id === jobId);
  const visibleCandidates = useMemo(() => (candidates || []).filter((candidate) => stageFilter === '全部' || candidate.status === stageFilter), [candidates, stageFilter]);
  const selected = (candidates || []).find((candidate) => candidate.id === selectedId) || visibleCandidates[0];

  const changeStage = async (nextStatus) => {
    if (!selected) return;
    await updateCandidateStage(jobId, selected.id, nextStatus);
    setCandidates((current) => current.map((candidate) => candidate.id === selected.id ? { ...candidate, status: nextStatus } : candidate));
    message.success(`${selected.name} 已更新为“${nextStatus}”`);
  };

  const importResume = (file) => {
    const imported = {
      id: `CAN-${Date.now()}`,
      name: file.name.replace(/\.[^.]+$/, '').split('-')[0] || '新候选人',
      degree: '待确认', experience: '待确认', location: '待确认', score: 68, confidence: 72, status: '待筛选', appliedAt: '刚刚', resume: file.name,
      summary: '简历已导入，当前为快速解析结果；请在人工确认能力画像后重新计算正式匹配分。',
      matchedSkills: ['Python'], gaps: ['能力画像待确认'],
      dimensions: [{ label: '技能匹配', value: 72 }, { label: '项目经历', value: 64 }, { label: '经验层级', value: 66 }, { label: '教育背景', value: 70 }],
      evidence: ['已完成简历文本抽取', '技能画像处于待人工确认状态', '正式匹配将在确认后生成'],
    };
    setCandidates((current) => [imported, ...(current || [])]);
    setSelectedId(imported.id);
    message.success('简历已导入候选池');
    return false;
  };

  if (!jobs.length || candidates === null) return <div className="page-loading"><Skeleton active paragraph={{ rows: 12 }} /></div>;

  return <div className="workbench-page candidate-matching-page">
    <PageHeading eyebrow="APPLICATION REVIEW" title="候选匹配" description="围绕企业实际招聘 JD 查看投递者的匹配结论、简历证据和人工筛选状态。">
      <Select className="candidate-job-select" value={jobId} onChange={setJobId} options={jobs.map((item) => ({ value: item.id, label: `${item.title} · ${item.id}` }))} />
      <Upload accept=".pdf,.doc,.docx" showUploadList={false} beforeUpload={importResume}><Button type="primary" icon={<FileAddOutlined />}>导入简历</Button></Upload>
    </PageHeading>

    {job && <section className="candidate-job-context">
      <div><span>CURRENT JOB</span><strong>{job.title}</strong><small>{job.department} · {job.version} · {job.location}</small></div>
      <div><span>招聘人数</span><strong>{job.openings}</strong></div>
      <div><span>累计投递</span><strong>{job.applications}</strong></div>
      <div><span>待处理</span><strong>{(candidates || []).filter((candidate) => candidate.status === '待筛选').length}</strong></div>
    </section>}

    <nav className="candidate-stage-filter" aria-label="候选人筛选状态">
      {['全部', ...stages].map((item) => <button type="button" key={item} className={stageFilter === item ? 'active' : ''} onClick={() => setStageFilter(item)}>{item}<b>{item === '全部' ? candidates.length : candidates.filter((candidate) => candidate.status === item).length}</b></button>)}
    </nav>

    {selected ? <section className="candidate-review-workspace">
      <aside className="candidate-review-list">
        <header><span>APPLICANTS</span><b>{visibleCandidates.length}</b></header>
        <div>{visibleCandidates.map((candidate) => <button type="button" key={candidate.id} className={candidate.id === selected.id ? 'active' : ''} onClick={() => setSelectedId(candidate.id)}>
          <span><UserOutlined /><small>{candidate.status}</small></span>
          <strong>{candidate.name}<b>{candidate.score}</b></strong>
          <p>{candidate.degree} · {candidate.experience}</p>
          <footer><time>{candidate.appliedAt}</time><em>{candidate.confidence}% 可信</em></footer>
        </button>)}</div>
      </aside>

      <main className="candidate-review-detail">
        <header className="candidate-profile-header">
          <div><span>{selected.id} · {selected.resume}</span><h2>{selected.name}</h2><p>{selected.degree} · {selected.experience} · {selected.location}</p></div>
          <div className="candidate-match-score"><strong>{selected.score}</strong><span>JD 匹配度</span><small><SafetyCertificateOutlined /> 画像置信度 {selected.confidence}%</small></div>
        </header>
        <p className="candidate-summary">{selected.summary}</p>

        <section className="candidate-dimension-section">
          <header><span>MATCH BREAKDOWN</span><strong>多维匹配</strong></header>
          {selected.dimensions.map((dimension) => <div key={dimension.label}><span>{dimension.label}</span><i><u style={{ width: `${dimension.value}%` }} /></i><b>{dimension.value}</b></div>)}
        </section>

        <div className="candidate-skill-columns">
          <section><span>已匹配能力</span><div>{selected.matchedSkills.map((skill) => <b key={skill}><CheckOutlined />{skill}</b>)}</div></section>
          <section><span>主要差距</span><div>{selected.gaps.map((skill) => <b key={skill}>{skill}</b>)}</div></section>
        </div>

        <section className="candidate-evidence-section">
          <span>匹配依据</span>
          {selected.evidence.map((item, index) => <div key={item}><b>{String(index + 1).padStart(2, '0')}</b><p>{item}</p></div>)}
        </section>
      </main>

      <aside className="candidate-decision-panel">
        <header><span>HUMAN REVIEW</span><b>{selected.status}</b></header>
        <section><span>人工筛选状态</span><Segmented vertical block value={selected.status} options={stages} onChange={changeStage} /></section>
        <section><span>处理原则</span><p>匹配分只提供排序和解释依据，最终招聘状态由企业人工确认。</p></section>
        <section><FilePdfOutlined /><span><strong>{selected.resume}</strong><small>简历解析与原文证据已关联</small></span></section>
      </aside>
    </section> : <div className="candidate-empty-state"><TeamOutlined /><strong>当前筛选条件下暂无候选人</strong><p>可以切换招聘 JD，或导入一份简历进行匹配。</p></div>}
  </div>;
};

export default CandidateMatchingPage;
