import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from 'react-query';
import {
  App as AntdApp,
  Button,
  Pagination,
  Segmented,
  Select,
  Skeleton,
  Slider,
  Switch,
  Upload,
} from 'antd';
import {
  BulbOutlined,
  CheckOutlined,
  FileAddOutlined,
  FilePdfOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import PageHeading from '../components/workbench/PageHeading';
import {
  getCandidateExplanation,
  getJobCandidates,
  getRecruitmentJobs,
  updateCandidateStage,
} from '../services/talentApi';
import '../components/workbench/recruitment.css';

const stages = ['待筛选', '待沟通', '入围', '不匹配'];
const defaultStats = {
  total_profiles: 0,
  initial_recall_count: 0,
  reranked_count: 0,
  eligible_count: 0,
  filtered_out_count: 0,
  threshold: 55,
  recommended_threshold: 55,
  recommended_pool_count: 0,
  page: 1,
  page_size: 50,
  total_pages: 1,
  took_ms: 0,
};
const emptyJobs = [];
const explanationModeLabel = (mode) => ({
  deepseek_grounded_rag_v1: 'DeepSeek 证据分析',
  grounded_fallback: '本地证据分析',
  legacy: '规则证据分析',
  'legacy-fallback': '本地规则分析',
}[mode] || '证据分析');

const CandidateMatchingPage = () => {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedJobId = searchParams.get('job');
  const compactMode = searchParams.get('compact') === '1';
  const [jobId, setJobId] = useState(requestedJobId);
  const [selectedId, setSelectedId] = useState(null);
  const [stageFilter, setStageFilter] = useState('全部');
  const [threshold, setThreshold] = useState(55);
  const [thresholdDraft, setThresholdDraft] = useState(55);
  const [suggestedThreshold, setSuggestedThreshold] = useState(55);
  const [thresholdTouched, setThresholdTouched] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [includeBelowThreshold, setIncludeBelowThreshold] = useState(false);
  const [ragResult, setRagResult] = useState(null);
  const [ragLoading, setRagLoading] = useState(false);
  const candidateListRef = useRef(null);

  const { data: jobsResult, isLoading: jobsLoading } = useQuery('recruitment-jobs', getRecruitmentJobs, {
    staleTime: 5 * 60 * 1000,
    cacheTime: 30 * 60 * 1000,
  });
  const jobs = useMemo(() => jobsResult?.items || emptyJobs, [jobsResult]);

  useEffect(() => {
    if (!jobs.length) return;
    const nextId = jobs.some((job) => job.id === requestedJobId)
      ? requestedJobId
      : jobs.find((job) => job.status === '招聘中')?.id || jobs[0]?.id;
    setJobId((current) => current && jobs.some((job) => job.id === current) ? current : nextId);
  }, [jobs, requestedJobId]);

  useEffect(() => {
    if (jobId && requestedJobId !== jobId) {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set('job', jobId);
      setSearchParams(nextParams, { replace: true });
    }
  }, [jobId, requestedJobId, searchParams, setSearchParams]);

  const candidatesQuery = useQuery(
    ['job-candidates', jobId, threshold, page, pageSize, includeBelowThreshold],
    () => getJobCandidates(jobId, { minScore: threshold, page, pageSize, includeBelowThreshold }),
    {
      enabled: Boolean(jobId),
      keepPreviousData: true,
      staleTime: 3 * 60 * 1000,
      cacheTime: 30 * 60 * 1000,
      onSuccess: (result) => {
        const stats = result.retrieval_stats || defaultStats;
        const recommendation = Number(stats.recommended_threshold ?? 55);
        setSuggestedThreshold(recommendation);
        if (!thresholdTouched && recommendation !== threshold) {
          setThreshold(recommendation);
          setThresholdDraft(recommendation);
          setPage(1);
          return;
        }
        const serverPage = stats.page;
        if (serverPage && serverPage !== page) setPage(serverPage);
        setSelectedId((current) => result.items.some((item) => item.id === current)
          ? current
          : result.items[0]?.id || null);
        candidateListRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
      },
      onError: (error) => message.error(error.message || '候选召回失败'),
    },
  );

  const candidates = candidatesQuery.data?.items || null;
  const dataSource = candidatesQuery.data?.source || jobsResult?.source || 'loading';
  const retrievalStats = candidatesQuery.data?.retrieval_stats || defaultStats;
  const stageCounts = candidatesQuery.data?.stage_counts || {};
  const matchMethod = candidatesQuery.data?.method || '';
  const matchingLoading = candidatesQuery.isLoading || candidatesQuery.isFetching;

  const job = jobs.find((item) => item.id === jobId);
  const visibleCandidates = useMemo(() => (candidates || []).filter(
    (candidate) => stageFilter === '全部' || candidate.status === stageFilter
  ), [candidates, stageFilter]);
  const selected = (candidates || []).find((candidate) => candidate.id === selectedId)
    || visibleCandidates[0];

  useEffect(() => {
    setRagResult(null);
  }, [selectedId]);

  const selectJob = (value) => {
    setJobId(value);
    setPage(1);
    setStageFilter('全部');
    setThreshold(55);
    setThresholdDraft(55);
    setSuggestedThreshold(55);
    setThresholdTouched(false);
  };

  const commitThreshold = (value) => {
    setThresholdTouched(true);
    setThreshold(value);
    setPage(1);
  };

  const changePage = (nextPage) => {
    if (nextPage === page || matchingLoading) return;
    setRagResult(null);
    setPage(nextPage);
  };

  const changeStage = async (nextStatus) => {
    if (!selected) return;
    if (!selected.isEligible && ['待沟通', '入围'].includes(nextStatus)) {
      message.warning(`该候选人未达到 ${threshold} 分准入线，不能进入沟通或入围阶段`);
      return;
    }
    const result = await updateCandidateStage(jobId, selected.id, nextStatus);
    queryClient.setQueriesData(['job-candidates', jobId], (current) => current ? {
      ...current,
      items: current.items.map((candidate) => candidate.id === selected.id
        ? { ...candidate, status: nextStatus }
        : candidate),
    } : current);
    message.success(result.warning
      ? `${selected.name} 已在当前页面更新，后端未持久化`
      : `${selected.name} 已更新为“${nextStatus}”`);
  };

  const generateRagExplanation = async () => {
    if (!selected) return;
    setRagLoading(true);
    try {
      const result = await getCandidateExplanation(jobId, selected.id, true, threshold);
      setRagResult(result);
      if (result.warning) message.warning(result.warning);
      else message.success('已生成可追溯的 RAG 匹配解释');
    } catch (error) {
      message.error(error.message || 'RAG 解释生成失败');
    } finally {
      setRagLoading(false);
    }
  };

  const importResume = (file) => {
    message.info(`${file.name} 已进入快速解析队列；正式入库接口仍待接入`);
    return false;
  };

  if (jobsLoading || !jobs.length || candidates === null) {
    return <div className="page-loading"><Skeleton active paragraph={{ rows: 12 }} /></div>;
  }

  const resultTotal = includeBelowThreshold
    ? retrievalStats.reranked_count
    : retrievalStats.eligible_count;
  const methodLabel = matchMethod.includes('rrf_bm25_text2vec_neo4j')
    ? 'BM25 + text2vec + Neo4j RRF'
    : (matchMethod || '候选召回');

  return <div className="workbench-page candidate-matching-page">
    <PageHeading
      eyebrow="CANDIDATE RETRIEVAL"
      title="候选召回与匹配"
      description="从标准候选池完成初召回、准入筛选、多维排序和证据解释，最终状态由企业人工确认。"
    >
      <span className={`market-runtime-badge ${dataSource === 'mock-fallback' ? 'offline' : 'live'}`}>
        {dataSource === 'mock-fallback' ? 'Mock 回退' : '真实候选池'}
      </span>
      <Select
        className="candidate-job-select"
        value={jobId}
        onChange={selectJob}
        options={jobs.map((item) => ({ value: item.id, label: `${item.title} · ${item.id}` }))}
      />
      <Upload accept=".pdf,.doc,.docx" showUploadList={false} beforeUpload={importResume}>
        <Button type="primary" icon={<FileAddOutlined />}>导入简历</Button>
      </Upload>
    </PageHeading>

    {!compactMode && job && <section className="candidate-job-context">
      <div><span>CURRENT JOB</span><strong>{job.title}</strong><small>{job.department} · {job.version} · {job.location}</small></div>
      <div><span>标准候选池</span><strong>{retrievalStats.total_profiles}</strong></div>
      <div><span>三路候选并集</span><strong>{retrievalStats.initial_recall_count}</strong></div>
      <div><span>达到准入线</span><strong>{retrievalStats.eligible_count}</strong></div>
    </section>}

    {!compactMode && <section className="candidate-retrieval-panel">
      <header>
        <div><span>RETRIEVAL FUNNEL</span><strong>{methodLabel}</strong></div>
        <small>耗时 {retrievalStats.took_ms} ms · 分数 {retrievalStats.score_min ?? 0}-{retrievalStats.score_max ?? 0}</small>
      </header>
      <div className="retrieval-funnel-metrics">
        <div><span>总画像</span><strong>{retrievalStats.total_profiles}</strong></div>
        <div><span>三路候选并集</span><strong>{retrievalStats.initial_recall_count}</strong></div>
        <div><span>融合 Top</span><strong>{retrievalStats.reranked_count}</strong></div>
        <div className="eligible"><span>进入候选池</span><strong>{retrievalStats.eligible_count}</strong></div>
      </div>
      <div className="retrieval-controls">
        <label>
          <span>准入阈值（岗位建议 {suggestedThreshold}）<b>{thresholdDraft}</b></span>
          <Slider
            min={10}
            max={100}
            value={thresholdDraft}
            onChange={setThresholdDraft}
            onAfterChange={commitThreshold}
          />
        </label>
        <label className="retrieval-switch">
          <span>查看未达标人员</span>
          <Switch
            checked={includeBelowThreshold}
            onChange={(checked) => { setIncludeBelowThreshold(checked); setPage(1); }}
          />
        </label>
        <Select
          value={pageSize}
          onChange={(value) => { setPageSize(value); setPage(1); }}
          options={[50, 100].map((value) => ({ value, label: `每页 ${value} 人` }))}
        />
      </div>
    </section>}

    <nav className="candidate-stage-filter" aria-label="候选人筛选状态">
      {['全部', ...stages].map((item) => <button
        type="button"
        key={item}
        className={stageFilter === item ? 'active' : ''}
        onClick={() => setStageFilter(item)}
      >
        {item}<b>{item === '全部' ? retrievalStats.eligible_count : stageCounts[item] || 0}</b>
      </button>)}
    </nav>

    {selected ? <section className={`candidate-review-workspace ${matchingLoading ? 'is-loading' : ''}`}>
      <aside className="candidate-review-list">
        <header><span>召回结果</span><b>{resultTotal}</b></header>
        <div ref={candidateListRef}>{visibleCandidates.map((candidate) => <button
          type="button"
          key={candidate.id}
          className={candidate.id === selected.id ? 'active' : ''}
          onClick={() => setSelectedId(candidate.id)}
        >
          <span><UserOutlined /><small>#{candidate.retrievalRank} · {candidate.decisionBand}</small></span>
          <strong>{candidate.name}<b>{candidate.score}</b></strong>
          <p>{candidate.degree} · {candidate.experience}</p>
          <footer><time>{candidate.isEligible ? '已达准入线' : '未达准入线'}</time><em>{candidate.confidence}% 可信</em></footer>
        </button>)}</div>
        <footer className="candidate-pagination">
          <Pagination
            current={page}
            pageSize={pageSize}
            total={resultTotal}
            onChange={changePage}
            showSizeChanger={false}
            showLessItems
            disabled={matchingLoading}
          />
        </footer>
      </aside>

      <main className="candidate-review-detail">
        <header className="candidate-profile-header">
          <div>
            <span>召回排名 #{selected.retrievalRank} · {selected.id}</span>
            <h2>{selected.name}</h2>
            <p>{selected.degree} · {selected.experience} · {selected.location}</p>
          </div>
          <div className={`candidate-match-score ${selected.isEligible ? 'eligible' : 'filtered'}`}>
            <strong>{selected.score}</strong>
            <span>{selected.decisionBand}</span>
            <small><SafetyCertificateOutlined /> 证据置信度 {selected.confidence}%</small>
          </div>
        </header>
        <p className="candidate-summary">{selected.summary}</p>

        <section className="candidate-dimension-section">
          <header><span>MATCH BREAKDOWN</span><strong>多维匹配</strong></header>
          {selected.dimensions.map((dimension) => <div key={dimension.label}>
            <span>{dimension.label}</span><i><u style={{ width: `${dimension.value}%` }} /></i><b>{dimension.value}</b>
          </div>)}
        </section>

        <div className="candidate-skill-columns">
          <section><span>已匹配能力</span><div>{selected.matchedSkills.map((skill) => <b key={skill}><CheckOutlined />{skill}</b>)}</div></section>
          <section><span>主要差距</span><div>{selected.gaps.map((skill) => <b key={skill}>{skill}</b>)}</div></section>
        </div>

        <section className="candidate-evidence-section">
          <span>确定性匹配依据</span>
          {selected.evidence.map((item, index) => <div key={item}><b>{String(index + 1).padStart(2, '0')}</b><p>{item}</p></div>)}
        </section>

        <section className="candidate-rag-section">
          <header>
            <div><span>证据解释</span><strong>岗位匹配解释</strong></div>
            <Button icon={<BulbOutlined />} loading={ragLoading} onClick={generateRagExplanation}>生成证据解释</Button>
          </header>
          {ragResult ? <div className="rag-result">
            <div className="rag-conclusion"><span>{explanationModeLabel(ragResult.mode)}</span><strong>{ragResult.conclusion}</strong><p>{ragResult.summary}</p></div>
            <div><span>匹配证据</span>{ragResult.matched_evidence.map((item) => <p key={item}>{item}</p>)}</div>
            <div><span>风险与差距</span>{[...(ragResult.skill_gaps || []), ...(ragResult.risks || [])].map((item) => <p key={item}>{item}</p>)}</div>
            <div><span>建议面试问题</span>{ragResult.interview_questions.map((item) => <p key={item}>{item}</p>)}</div>
          </div> : <p>按需检索 JD、技能和项目经历证据；配置 DeepSeek API 后生成模型解释，否则自动返回本地可追溯解释。</p>}
        </section>
      </main>

      <aside className="candidate-decision-panel">
        <header><span>HUMAN REVIEW</span><b>{selected.status}</b></header>
        <section>
          <span>人工筛选状态</span>
          <Segmented
            vertical
            block
            value={selected.status}
            options={stages.map((item) => ({
              label: item,
              value: item,
              disabled: !selected.isEligible && ['待沟通', '入围'].includes(item),
            }))}
            onChange={changeStage}
          />
        </section>
        <section><span>准入规则</span><p>当前准入线为 {threshold} 分。未达标人员可供人工复核，但不能直接进入沟通或入围阶段。</p></section>
        <section><FilePdfOutlined /><span><strong>{selected.resume}</strong><small>结构化简历证据已关联</small></span></section>
      </aside>
    </section> : <div className="candidate-empty-state">
      <TeamOutlined /><strong>当前阈值下暂无达标候选人</strong><p>可以降低准入阈值，或打开“查看未达标人员”进行人工复核。</p>
    </div>}
  </div>;
};

export default CandidateMatchingPage;
