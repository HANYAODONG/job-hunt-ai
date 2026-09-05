import React, { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from 'react-query';
import { App as AntdApp, Button, Card, Input, Popconfirm, Progress, Select, Space, Tag, Upload } from 'antd';
import {
  ArrowRightOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
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
  getDiscoveryBatch,
  deleteImportedMonth,
  getRoleEvolutionWorkspace,
  getRoleAnalytics,
  importMonthlyJds,
  reviewDiscoveryCandidate,
  reviewPendingJob,
  runSyntheticNewRoleFixture,
  saveRoleOptimization,
  submitRoleJd,
} from '../services/talentApi';
import './RoleEvolutionCenterPage.css';

const views = [
  { key: 'batch-discovery', label: '批量新岗位发现', hint: '按月份聚类未归类 JD，形成可审计候选' },
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

const formatUpdateTime = (value) => {
  if (!value) return '暂无记录';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(parsed).reduce((result, part) => ({ ...result, [part.type]: part.value }), {});
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
};

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
  const [discoveryMonth, setDiscoveryMonth] = useState('');
  const [fromMonth, setFromMonth] = useState('');
  const [toMonth, setToMonth] = useState('');
  const [fixtureRunning, setFixtureRunning] = useState(false);
  const [fixtureResult, setFixtureResult] = useState(null);
  const [monthlyImporting, setMonthlyImporting] = useState(false);
  const [monthlyDeleting, setMonthlyDeleting] = useState(false);
  const [reviewingCandidate, setReviewingCandidate] = useState('');
  const [selectedReview, setSelectedReview] = useState(null);
  const [reviewDraft, setReviewDraft] = useState({ standard_category: '', standard_job_title: '', match_keywords: '', skills_text: '', skill_group: '通用技术能力', responsibilities_text: '', bonus_skills_text: '', scenarios_text: '', evidence_note: '' });

  const { data, isLoading, refetch: refreshWorkspace } = useQuery(
    'role-evolution-workspace',
    getRoleEvolutionWorkspace,
    { staleTime: 5 * 60 * 1000, cacheTime: 30 * 60 * 1000 },
  );

  const { data: batchData, isLoading: batchLoading, refetch: refreshBatch } = useQuery(
    ['role-discovery-batch', discoveryMonth, selectedRole],
    () => getDiscoveryBatch(discoveryMonth, 10, selectedRole),
    { enabled: activeView === 'batch-discovery', staleTime: 60 * 1000, retry: false },
  );

  const analyticsMonths = useMemo(() => {
    const values = safeList(data?.analytics?.months).concat(safeList(data?.analytics?.trend).map((item) => item.month));
    return [...new Set(values.filter(Boolean))].sort();
  }, [data]);
  useEffect(() => {
    if (!analyticsMonths.length) return;
    setFromMonth((current) => current && analyticsMonths.includes(current) ? current : analyticsMonths[0]);
    setToMonth((current) => current && analyticsMonths.includes(current) ? current : analyticsMonths[analyticsMonths.length - 1]);
  }, [analyticsMonths]);
  useEffect(() => {
    const months = safeList(batchData?.available_months);
    if (!months.length) return;
    setDiscoveryMonth((current) => current && months.includes(current) ? current : months[months.length - 1]);
  }, [batchData?.available_months]);
  const { data: compareData, isFetching: compareLoading } = useQuery(
    ['role-evolution-compare', selectedRole, fromMonth, toMonth],
    () => getRoleAnalytics({ standard_job: selectedRole, from_month: fromMonth, to_month: toMonth }),
    { enabled: activeView === 'analytics' && Boolean(selectedRole && fromMonth && toMonth), staleTime: 60 * 1000, retry: false },
  );
  const { data: liveRoleData, isFetching: liveRoleLoading } = useQuery(
    ['role-live-evolution', selectedRole],
    () => getRoleAnalytics({ standard_job: selectedRole }),
    { enabled: activeView === 'live-evolution' && Boolean(selectedRole), staleTime: 60 * 1000, retry: false },
  );

  useEffect(() => {
    if (!data) return;
    setSelectedRole((current) => data.jobs.some((job) => job.name === current) ? current : data.optimization?.name || data.analytics.role);
    setEditedSkills(safeList(data.optimization?.requiredSkills).map((skill) => typeof skill === 'string' ? skill : skill.name));
  }, [data]);

  const selectedJob = useMemo(() => data?.jobs?.find((job) => job.name === selectedRole) || data?.optimization, [data, selectedRole]);
  const selectedMonthReviewItems = useMemo(() => {
    const reviews = safeList(data?.pending);
    const selectedMonth = batchData?.month || discoveryMonth;
    if (!selectedMonth) return reviews;
    return reviews.filter((item) => (item.input || {}).month === selectedMonth);
  }, [batchData?.month, data?.pending, discoveryMonth]);
  const baseLatest = submitted || data?.latest || {};
  const liveLatest = submitted || (baseLatest.role === selectedRole ? baseLatest : liveRoleData?.roleEvolution) || {
    role: selectedRole,
    status: '暂无画像数据',
    version: '待数据输入',
    summary: '该岗位尚未形成可比较的时序画像，不展示其他岗位的替代数据。',
    added: [], removed: [], modified: [], evidence: 0, updatedAt: '', input: {}, raw: {},
  };
  const latest = activeView === 'live-evolution' ? liveLatest : baseLatest;
  const visibleAnalytics = compareData?.analytics || (data?.analytics?.role === selectedRole ? data.analytics : {
    role: selectedRole, versions: [], trend: [], lifecycle: [], migration: [],
  });
  const latestIsConfirmed = latest?.status === '已生效' || latest?.status === '已发布';
  const latestEvidence = latestIsConfirmed ? [
    {
      source: '已确认岗位画像更新',
      confidence: '已生效',
      excerpt: `${latest.role} 在 ${latest.version} 的岗位能力画像已写入演化记录。`,
      collectedAt: latest.updatedAt,
    },
    {
      source: '本次 JD 技能输入',
      confidence: `${latest.evidence || 0} 项技能`,
      excerpt: safeList(latest.raw?.signal_skills).join('、') || '本次提交的技能已用于岗位画像更新。',
      collectedAt: latest.input?.month || latest.updatedAt,
    },
    {
      source: '岗位画像差异',
      confidence: '已记录',
      excerpt: `新增 ${safeList(latest.added).length} 项；调整 ${safeList(latest.modified).length} 项；移除 ${safeList(latest.removed).length} 项。`,
      collectedAt: latest.updatedAt,
    },
  ] : [
    { source: '市场 JD 输入', confidence: '本次提交', excerpt: latest?.input?.job_title || latest.role, collectedAt: latest?.input?.month || latest.updatedAt },
    { source: '岗位技能抽取', confidence: `${latest.evidence || 0} 条证据`, excerpt: safeList(latest.added).join('、') || '未发现新增能力', collectedAt: latest.updatedAt },
    { source: '岗位画像版本', confidence: latest.version, excerpt: '变化结果保留新增、删除和修改三类差异。', collectedAt: latest.updatedAt },
  ];
  const latestHistory = latestIsConfirmed ? [
    { label: '完成 JD 解析与岗位归类', time: latest.updatedAt },
    { label: '确认岗位并写入岗位画像', time: latest.updatedAt },
    { label: '岗位画像变化已记录', time: latest.updatedAt },
  ] : [
    { label: '完成 JD 解析与岗位归类', time: latest.updatedAt },
    { label: latest.candidateSkillCount ? `${latest.candidateSkillCount} 项新增能力进入交叉验证候选池` : '技能均已通过岗位能力验证', time: latest.updatedAt },
    { label: '等待人工确认发布', time: '当前' },
  ];
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

  const handleSyntheticFixture = async () => {
    setFixtureRunning(true);
    try {
      const result = await runSyntheticNewRoleFixture();
      setFixtureResult(result);
      message.success('新岗位发现验证完成：候选仅写入隔离审核环境');
    } catch (error) {
      message.error(error.message || '新岗位发现验证失败');
    } finally {
      setFixtureRunning(false);
    }
  };

  const handleMonthlyImport = async (file) => {
    if (!/\.csv$/i.test(file?.name || '')) {
      message.error('请选择 CSV 格式的月度 JD 文件');
      return Upload.LIST_IGNORE;
    }
    setMonthlyImporting(true);
    try {
      const result = await importMonthlyJds(file);
      message.success(`已导入 ${result.count ?? 0} 条 JD，进入待审核队列`);
      await Promise.all([refreshBatch(), refreshWorkspace()]);
    } catch (error) {
      message.error(error.message || '月度 JD 导入失败');
    } finally {
      setMonthlyImporting(false);
    }
    return false;
  };

  const handleDeleteImportedMonth = async () => {
    if (!discoveryMonth) return;
    setMonthlyDeleting(true);
    try {
      const result = await deleteImportedMonth(discoveryMonth);
      setSelectedReview(null);
      setFixtureResult(null);
      await Promise.all([refreshBatch(), refreshWorkspace()]);
      message.success(`已清理 ${result.deleted_review_items ?? 0} 条 ${discoveryMonth} 导入审核记录`);
    } catch (error) {
      message.error(error.message || '月度导入数据清理失败');
    } finally {
      setMonthlyDeleting(false);
    }
  };

  const openReview = (item, sourceReviewIds = []) => {
    const input = item.input || {};
    const route = item.result?.route || {};
    setSelectedReview({ ...item, sourceReviewIds });
    setReviewDraft({
      standard_category: route.best_category?.name || '',
      standard_job_title: route.best_job?.name || input.job_title || '',
      match_keywords: input.job_title || '',
      skills_text: safeList(item.result?.skills).map((skill) => typeof skill === 'string' ? skill : skill.normalized_skill || skill.raw_skill || '').filter(Boolean).join('、'),
      skill_group: '通用技术能力',
      responsibilities_text: '',
      bonus_skills_text: '',
      scenarios_text: '',
      evidence_note: sourceReviewIds.length > 1 ? `基于 ${sourceReviewIds.length} 条独立 JD 证据，经人工核验后提出新岗位定义。` : '',
    });
  };

  const openClusterReview = (cluster) => {
    const evidence = safeList(cluster.evidence);
    const sourceReviewIds = safeList(cluster.review_item_ids).length
      ? safeList(cluster.review_item_ids)
      : evidence.map((item) => item.candidate_id || item.raw?.item_id || item.item_id).filter(Boolean);
    openReview(cluster.candidate || {}, sourceReviewIds);
  };

  const handlePendingReview = async (action) => {
    if (!selectedReview) return;
    const skills = reviewDraft.skills_text.split(/[、,，;；\n]+/).map((item) => item.trim()).filter(Boolean);
    const splitList = (value) => value.split(/[、,，;；\n]+/).map((item) => item.trim()).filter(Boolean);
    if (!reviewDraft.standard_category.trim() || !reviewDraft.standard_job_title.trim() || !skills.length) {
      message.error('请填写二级方向、三级岗位名称和至少一项核心技能');
      return;
    }
    setReviewingCandidate(selectedReview.item_id);
    try {
      await reviewPendingJob(selectedReview.item_id, action, {
        ...reviewDraft,
        required_skills: skills,
        core_responsibilities: splitList(reviewDraft.responsibilities_text),
        bonus_skills: splitList(reviewDraft.bonus_skills_text),
        application_scenarios: splitList(reviewDraft.scenarios_text),
        source_review_ids: selectedReview.sourceReviewIds || [],
        skills: skills.map((normalized_skill) => ({
          normalized_skill,
          kg_display_skill: reviewDraft.skill_group.trim() || '通用技术能力',
          skill_type: 'required',
          decision: 'confirmed',
        })),
      });
      message.success(action === 'confirm' ? '已确认归入现有三级岗位' : `新岗位定义已提交，关联 ${Math.max(1, selectedReview.sourceReviewIds?.length || 0)} 条 JD 证据，等待发布审核`);
      setSelectedReview(null);
      await Promise.all([refreshWorkspace(), refreshBatch()]);
    } catch (error) {
      message.error(error.message || '审核操作失败');
    } finally {
      setReviewingCandidate('');
    }
  };

  const handleCandidateReview = async (cluster, action) => {
    const candidate = cluster.candidate || {};
    const title = cluster.title || candidate.title || candidate.source?.job_title || '';
    const candidateId = candidate.candidate_id || candidate.id;
    if (!candidateId) return;
    setReviewingCandidate(candidateId);
    try {
      const definition = {
        name: title,
        category: candidate.best_category || '待人工确认二级方向',
        keywords: title,
        coreResponsibilities: ['定义岗位核心职责与交付边界', '实现并验证该岗位的核心技术链路', '建立质量、监控和持续改进机制'],
        requiredSkills: (candidate.skills || []).map((skill) => typeof skill === 'string' ? skill : skill.normalized_skill || skill.skill).filter(Boolean),
        bonusSkills: [],
        scenarios: [],
        evidenceNote: `基于 ${cluster.supporting_jd_count} 条独立 JD 证据，提交前需人工核验。`,
        maintenanceId: candidate.maintenance_id || candidate.maintenanceId || '',
      };
      const response = await reviewDiscoveryCandidate(candidateId, action, definition);
      const published = response?.status === 'published_new_job' || response?.result?.published_result;
      message.success(action === 'publish'
        ? (published ? '候选岗位已发布到当前岗位目录' : '岗位定义已提交正式发布审核')
        : '候选岗位已驳回');
      if (action === 'publish' || response) await refreshBatch();
    } catch (error) {
      message.error(error.message || '岗位候选审核失败');
    } finally {
      setReviewingCandidate('');
    }
  };

  const openView = (view) => {
    if (view === 'live-evolution' && !submitted && baseLatest.role) {
      setSelectedRole(baseLatest.role);
    }
    setActiveView(view);
  };
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
        <Metric label="最新数据月份" value={data.analytics.latest_month || '暂无'} detail="来自版本化岗位数据" />
        <Metric label="覆盖标准岗位" value={data.analytics.job_count ?? data.jobs.length} detail="当前分析数据集" />
        <Metric label="覆盖技能" value={data.analytics.skill_count ?? 0} detail="岗位技能关系数据" />
      </section>

      <nav className="role-evolution-tabs" aria-label="岗位演化功能">
        {views.map((view) => <button key={view.key} className={activeView === view.key ? 'active' : ''} onClick={() => openView(view.key)}><strong>{view.label}</strong><span>{view.hint}</span></button>)}
      </nav>

      {activeView === 'batch-discovery' && <section className="role-evolution-batch">
          <div className="role-evolution-batch-toolbar">
          <div><span>BATCH DISCOVERY</span><h2>月度新岗位发现闭环</h2><p>把新月份 JD 路由到现有三级岗位；无法稳定归类的记录进入聚类候选，超过阈值后才进入人工审核。</p></div>
          <Space>
            <Select showSearch placeholder="聚焦三级岗位" value={selectedRole || undefined} onChange={setSelectedRole} options={safeList(data?.jobs).map((job) => ({ value: job.name, label: job.name }))} />
            <Select allowClear placeholder="选择数据月份" value={discoveryMonth || undefined} onChange={(value) => setDiscoveryMonth(value || '')} options={safeList(batchData?.available_months).map((month) => ({ value: month, label: month }))} />
            <Upload accept=".csv,text/csv" maxCount={1} showUploadList={false} beforeUpload={handleMonthlyImport} disabled={monthlyImporting}>
              <Button icon={<PlusOutlined />} loading={monthlyImporting}>导入月度 JD</Button>
            </Upload>
            <Popconfirm
              title={`删除 ${discoveryMonth || '当前'} 月的导入测试数据？`}
              description="只删除该月未发布的导入审核记录，不会修改正式岗位池、图谱或历史画像。"
              okText="删除数据"
              cancelText="保留"
              okButtonProps={{ danger: true }}
              onConfirm={handleDeleteImportedMonth}
              disabled={!discoveryMonth || monthlyDeleting}
            >
              <Button danger icon={<DeleteOutlined />} loading={monthlyDeleting} disabled={!discoveryMonth}>删除当前月数据</Button>
            </Popconfirm>
            <Button icon={<FileSearchOutlined />} loading={fixtureRunning} onClick={handleSyntheticFixture}>验证新岗位发现</Button>
            <Button icon={<ReloadOutlined />} loading={batchLoading} onClick={() => refreshBatch()}>刷新批次</Button>
          </Space>
        </div>
        {fixtureResult && <section className="role-evolution-fixture-result" aria-label="新岗位发现验证结果">
          <header><div><span>WORKFLOW VALIDATION</span><h3>新岗位发现验证结果</h3></div><Tag color="blue">隔离数据</Tag></header>
          <p>输入 {fixtureResult.fixture_jd_count ?? 0} 条同类 JD，均未归入现有三级岗位；系统按岗位标题聚类后进入人工审核队列。</p>
          <div>
            <Metric label="候选岗位" value={fixtureResult.result_summary?.title || '未生成'} detail="待定义三级岗位" />
            <Metric label="支撑 JD" value={fixtureResult.result_summary?.supporting_jd_count ?? 0} detail={`触发阈值 > ${fixtureResult.result_summary?.threshold ?? 10}`} />
            <Metric label="路由结果" value={safeList(fixtureResult.route_statuses).join('、') || '未知'} detail="未自动并入现有岗位" />
            <Metric label="正式池变更" value={fixtureResult.production_state_changed ? '有' : '无'} detail="需人工发布后才生效" />
          </div>
        </section>}
        {batchLoading && <div className="role-evolution-batch-empty">正在读取版本化岗位事件流...</div>}
        {!batchLoading && batchData && <>
          <div className="role-evolution-batch-metrics">
            <Metric label="数据月份" value={batchData.month || '暂无'} detail="来自岗位事件流" />
            <Metric label="输入 JD" value={batchData.input_jd_count ?? 0} detail="原始事件记录" />
            <Metric label="去重后 JD" value={batchData.deduplicated_jd_count ?? 0} detail="按原始岗位 ID" />
            <Metric label="已归类 JD" value={batchData.classified_jd_count ?? 0} detail="已有标准三级岗位" />
            <Metric label="未稳定归类" value={batchData.unmapped_jd_count ?? 0} detail="进入候选信号" />
          </div>
          <div className="role-evolution-batch-rule"><strong>批次状态</strong><span>{batchData.batch_status || '已读取月度事件流'} · 当前覆盖 {batchData.role_count ?? 0} 个标准岗位</span><Tag color={batchData.batch_status === '已完成归类' ? 'green' : 'gold'}>{batchData.batch_status || '只读批次'}</Tag></div>
          <section className="role-evolution-review-queue" aria-label="待审核队列">
            <header><div><h3>待审核队列</h3><span>{batchData.month || '当前'} 月的月度导入和单条 JD 审核记录</span></div><Tag color={selectedMonthReviewItems.length ? 'orange' : 'green'}>{selectedMonthReviewItems.length} 条待处理</Tag></header>
            {selectedMonthReviewItems.length ? <div className="role-evolution-review-queue-list">{selectedMonthReviewItems.slice(0, 20).map((item, index) => {
              const input = item.input || {};
              const route = item.result?.route || {};
              return <div className="role-evolution-review-queue-row" key={item.item_id || item.job_id || `review-${index}`}>
                <div><strong>{input.job_title || item.job_id || '未命名 JD'}</strong><span>{input.month || '月份未提供'} · {item.review_type === 'skill' ? '技能审核' : '岗位审核'}</span></div>
                <Space size={6}><Tag>{route.status === 'potential_new_job' ? '待确认新岗位' : '待确认归类'}</Tag>{item.review_type === 'job' && <Button size="small" onClick={() => openReview(item)}>审核</Button>}</Space>
              </div>;
            })}</div> : <div className="role-evolution-review-queue-empty">当前月份没有待审核记录。</div>}
            {selectedMonthReviewItems.length > 20 && <small className="role-evolution-review-queue-more">仅展示最近 20 条，完整数量见右上角。</small>}
          </section>
          {selectedReview && <section className="role-evolution-review-editor" aria-label="岗位审核编辑器">
            <header><div><h3>审核岗位归类</h3><span>{selectedReview.input?.job_title || selectedReview.job_id}</span></div><Button type="text" onClick={() => setSelectedReview(null)}>关闭</Button></header>
            <div className="role-evolution-review-editor-grid">
              <label>二级方向<Input value={reviewDraft.standard_category} onChange={(event) => setReviewDraft((current) => ({ ...current, standard_category: event.target.value }))} /></label>
              <label>三级岗位名称<Input value={reviewDraft.standard_job_title} onChange={(event) => setReviewDraft((current) => ({ ...current, standard_job_title: event.target.value }))} /></label>
              <label>匹配关键词<Input value={reviewDraft.match_keywords} onChange={(event) => setReviewDraft((current) => ({ ...current, match_keywords: event.target.value }))} /></label>
              <label>核心技能（用逗号分隔）<Input value={reviewDraft.skills_text} onChange={(event) => setReviewDraft((current) => ({ ...current, skills_text: event.target.value }))} placeholder="例如：Python、RAG、向量数据库" /></label>
              <label>技能类别<Input value={reviewDraft.skill_group} onChange={(event) => setReviewDraft((current) => ({ ...current, skill_group: event.target.value }))} placeholder="例如：人工智能技术" /></label>
              <label>核心职责（用逗号分隔）<Input value={reviewDraft.responsibilities_text} onChange={(event) => setReviewDraft((current) => ({ ...current, responsibilities_text: event.target.value }))} placeholder="例如：设计智能体任务编排与边云协同执行链路" /></label>
              <label>加分技能（用逗号分隔）<Input value={reviewDraft.bonus_skills_text} onChange={(event) => setReviewDraft((current) => ({ ...current, bonus_skills_text: event.target.value }))} placeholder="例如：ROS 2、边缘计算平台" /></label>
              <label>应用场景（用逗号分隔）<Input value={reviewDraft.scenarios_text} onChange={(event) => setReviewDraft((current) => ({ ...current, scenarios_text: event.target.value }))} placeholder="例如：具身智能、工业设备协同" /></label>
              <label>证据说明<Input value={reviewDraft.evidence_note} onChange={(event) => setReviewDraft((current) => ({ ...current, evidence_note: event.target.value }))} placeholder="说明这组 JD 与现有岗位的职责边界差异" /></label>
            </div>
            <footer><span>{selectedReview.sourceReviewIds?.length > 1 ? `本次将以 ${selectedReview.sourceReviewIds.length} 条独立 JD 作为同一新岗位的发布证据。` : '确认已有岗位会合并到现有目录；提交新岗位会生成维护审核记录，不会立即污染 canonical 闭集。'}</span><Space><Button loading={reviewingCandidate === selectedReview.item_id} onClick={() => handlePendingReview('confirm')}>归入现有岗位</Button><Button type="primary" loading={reviewingCandidate === selectedReview.item_id} onClick={() => handlePendingReview('new')}>提交为新岗位</Button></Space></footer>
          </section>}
          <section className="role-evolution-profile-replay">
            <header><div><h3>三级岗位内 JD / 技能画像变化</h3><span>{batchData.role_profile_evolution?.standard_job || selectedRole} · 不改变三级岗位名，观察岗位内涵变化</span></div><Tag color="purple">岗位画像</Tag></header>
            <div className="role-evolution-profile-history">{safeList(batchData.role_profile_evolution?.history).map((item) => {
              const maxJd = Math.max(...safeList(batchData.role_profile_evolution?.history).map((row) => row.jd_count || 0), 1);
              return <div className={['role-evolution-profile-month', item.month === batchData.month ? 'active' : ''].filter(Boolean).join(' ')} key={item.month}>
                <strong>{item.month}</strong>
                <div className="role-evolution-profile-volume"><i style={{ height: Math.max(8, Math.min(100, ((item.jd_count || 0) / maxJd) * 100)) + '%' }} /></div>
                <span>{item.jd_count || 0} 条 JD</span>
                <small>{safeList(item.new_skills).length ? '新技能：' + safeList(item.new_skills).slice(0, 2).join('、') : '无新增技能信号'}</small>
              </div>;
            })}</div>
            <div className="role-evolution-profile-detail">
              {(() => {
                const currentProfile = safeList(batchData.role_profile_evolution?.history).find((item) => item.month === batchData.month) || safeList(batchData.role_profile_evolution?.history).slice(-1)[0] || {};
                return <>
                  <section><b>当月高频技能</b><div>{safeList(currentProfile.top_skills).slice(0, 8).map((item) => <Tag className="role-evolution-token required" key={item.skill}>{item.skill}{item.delta > 0 ? ' +' + item.delta : ''}</Tag>)}</div></section>
                  <section><b>当月标题样例</b>{safeList(currentProfile.sample_titles).slice(0, 4).map((title) => <span key={title}>{title}</span>)}</section>
                </>;
              })()}
            </div>
            {batchData.role_profile_evolution?.interpretation && <p className="role-evolution-pool-note">{batchData.role_profile_evolution.interpretation}</p>}
          </section>
          {safeList(batchData.role_distribution).length > 0 && <section className="role-evolution-monthly-panel">
            <header><h3>当月标准岗位分布</h3><span>按真实 JD 归类结果统计</span></header>
            <div className="role-evolution-role-distribution">{safeList(batchData.role_distribution).map((row) => <div className="role-evolution-role-row" key={row.standard_job}><span>{row.standard_job}</span><strong>{row.jd_count}</strong><div><i style={{ width: `${Math.min(100, (row.jd_count / Math.max(1, batchData.role_distribution[0]?.jd_count || row.jd_count)) * 100)}%` }} /></div></div>)}</div>
          </section>}
          {safeList(batchData.candidates).length === 0 && <div className="role-evolution-batch-empty">当前月份已完成 {batchData.classified_jd_count ?? 0} 条 JD 的标准岗位归类；没有达到新岗位候选阈值的记录。新岗位候选仍需去重后同类 JD 数量超过 {batchData.trigger_threshold ?? 10} 条，并进入人工审核。</div>}
          <div className="role-evolution-batch-list">{safeList(batchData.candidates).map((cluster) => {
            const candidate = cluster.candidate || {};
            const definition = candidate.definition || {};
            return <Card key={cluster.cluster_id} className="role-evolution-batch-card">
              <header><div><span>{cluster.cluster_id}</span><h3>{cluster.title}</h3></div><Tag color={cluster.threshold_met ? 'orange' : 'default'}>{cluster.status}</Tag></header>
              <div className="role-evolution-cluster-metrics"><span><small>支撑 JD</small><strong>{cluster.supporting_jd_count}</strong></span><span><small>来源数</small><strong>{cluster.source_count}</strong></span><span><small>候选二级方向</small><strong>{candidate.domain || '待归类'}</strong></span></div>
              <p>{candidate.signals?.[0] || candidate.route_reason || '候选由未稳定归类的岗位信号形成，等待人工定义边界。'}</p>
              <div className="role-evolution-definition-grid"><section><b>核心职责</b><ul>{safeList(definition.coreResponsibilities || definition.core_responsibilities).slice(0, 3).map((item) => <li key={item}>{item}</li>)}</ul></section><section><b>必备技能</b><div>{safeList(definition.requiredSkills || definition.required_skills).slice(0, 8).map((item) => <Tag className="role-evolution-token required" key={typeof item === 'string' ? item : item.name}>{typeof item === 'string' ? item : item.name}</Tag>)}</div></section></div>
              <details><summary>查看来源 JD 证据（{safeList(cluster.evidence).length} 条）</summary><div className="role-evolution-evidence-list">{safeList(cluster.evidence).map((evidence, index) => <div key={evidence.id || evidence.candidate_id || index}><strong>{evidence.name || evidence.title || evidence.raw?.source?.job_title || evidence.source?.job_title || '未命名 JD'}</strong><span>{evidence.updatedAt || evidence.updated_at || evidence.raw?.source?.month || evidence.source?.month || '来源月份未提供'} · {evidence.raw?.source?.job_id || evidence.source?.job_id || evidence.id || evidence.candidate_id || '无原始 ID'}</span></div>)}</div></details>
              <footer><span>{cluster.threshold_met ? '满足数量门槛，但仍需人工确认岗位边界与 canonical_role_id。' : `当前证据不足以触发正式新岗位（需要 > ${cluster.threshold} 条去重 JD）。`}</span><Tag>{candidate.status || candidate.workflow_stage || '观察中'}</Tag></footer>
              {cluster.threshold_met && <div className="role-evolution-candidate-actions">
                <Button size="small" loading={reviewingCandidate === (candidate.candidate_id || candidate.id)} onClick={() => (candidate.maintenance_id || candidate.maintenanceId ? handleCandidateReview(cluster, 'publish') : openClusterReview(cluster))} disabled={candidate.stage === 'published' || candidate.status === 'published_new_job'} icon={<SendOutlined />}>{candidate.maintenance_id || candidate.maintenanceId ? '发布到岗位池' : '审核并定义岗位'}</Button>
                <Button size="small" danger onClick={() => handleCandidateReview(cluster, 'reject')}>驳回候选</Button>
              </div>}
            </Card>;
          })}</div>
          <div className="role-evolution-guardrails"><strong>发布边界</strong>{safeList(batchData.guardrails).map((item) => <span key={item}>· {item}</span>)}</div>
        </>}
      </section>}

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
          <header><div><span>LIVE EFFECT</span><h2>{latest.role} · 本次岗位演化</h2></div><Space><Select showSearch optionFilterProp="label" aria-label="选择查看岗位演化" value={selectedRole} loading={liveRoleLoading} onChange={setSelectedRole} options={data.jobs.map((job) => ({ value: job.name, label: job.name }))} /><Tag color={latestIsConfirmed ? 'green' : 'blue'}>{latest.status}</Tag></Space></header>
          <div className="role-evolution-effect-header"><div><small>画像变化</small><strong>{safeList(latest.added).length + safeList(latest.removed).length + safeList(latest.modified).length} 项</strong></div><div><small>更新时间</small><strong>{formatUpdateTime(latest.updatedAt)}</strong></div><div><small>输入技能</small><strong>{latest.evidence || 0} 项</strong></div></div>
          <p className="role-evolution-summary">{latest.summary}</p>
          <div className="role-evolution-change-columns">{changeGroups.map((group) => <ChangeGroup key={group.key} title={group.label} items={latest[group.key]} tone={group.tone} />)}</div>
          <div className="role-evolution-action-row"><Button onClick={() => openView('analytics')} icon={<BarChartOutlined />}>查看历史趋势</Button><Button onClick={() => openContextualRoute('/graph')} icon={<NodeIndexOutlined />}>打开全景图谱</Button><Button type="primary" onClick={() => openView('optimization')} icon={<FileSearchOutlined />}>进入人工优化</Button></div>
        </main>
        <TechnicalInspector title="岗位演化证据" status={latest.status} version={latest.version} hideFacts explanation={[latest.summary, ...safeList(latest.modified)]} evidence={latestEvidence} history={latestHistory} />
      </section>}

      {activeView === 'analytics' && <section className="role-evolution-analytics">
        <div className="role-evolution-analytics-toolbar"><div><span>TIME SERIES</span><h2>岗位技能时序分析</h2><p>切换三级岗位后，趋势、生命周期、迁移路径和画像对比会同步刷新。</p></div><Space wrap><Select showSearch optionFilterProp="label" aria-label="选择查看岗位时序" value={selectedRole} onChange={setSelectedRole} options={data.jobs.map((job) => ({ value: job.name, label: job.name }))} /><Select value={fromMonth || undefined} placeholder="起始月份" onChange={setFromMonth} options={analyticsMonths.map((month) => ({ value: month, label: `从 ${month}` }))} /><ArrowRightOutlined /><Select value={toMonth || undefined} placeholder="结束月份" onChange={setToMonth} options={analyticsMonths.map((month) => ({ value: month, label: `到 ${month}` }))} /></Space></div>
        <div className="role-evolution-compare-strip"><div><span>时间窗口</span><strong>{fromMonth || '未选择'} → {toMonth || '未选择'}</strong></div><div><span>新增技能</span><strong>{compareData?.profileCompare?.summary?.added ?? '—'}</strong></div><div><span>下降技能</span><strong>{compareData?.profileCompare?.summary?.decreased ?? '—'}</strong></div><div><span>画像变化</span><strong>{compareLoading ? '计算中' : compareData?.profileCompare?.summary?.modified ?? '—'}</strong></div></div>
        <div className="role-evolution-analytics-grid">
          <Card title="技能需求趋势" className="role-evolution-card"><div className="role-evolution-trend-chart">{safeList(visibleAnalytics.trend).map((point) => <div className="role-evolution-trend-point" key={point.month} title={`${point.month}: ${Math.round(point.frequency * 100)}%`} aria-label={`${point.month} 技能需求占比 ${Math.round(point.frequency * 100)}%`}><b>{Math.round(point.frequency * 100)}%</b><i style={{ height: `${Math.round(point.frequency * 100)}%` }} /><span>{point.month.slice(5)}</span></div>)}</div></Card>
          <Card title="前后岗位画像对比" className="role-evolution-card role-evolution-profile-card"><div className="role-evolution-profile-compare"><div><span>{fromMonth || '起始月份'}</span>{safeList(compareData?.profileCompare?.from_profile).slice(0, 6).map((item) => <Tag key={item.skill}>{item.skill}</Tag>)}</div><ArrowRightOutlined /><div><span>{toMonth || '结束月份'}</span>{safeList(compareData?.profileCompare?.to_profile).slice(0, 6).map((item) => <Tag className="role-evolution-token added" key={item.skill}>{item.skill}</Tag>)}</div></div><p className="role-evolution-muted">新增、下降和稳定技能来自版本化岗位画像；没有数据时不会用演示值替代。</p></Card>
          <Card title="技能生命周期" className="role-evolution-card"><div className="role-evolution-lifecycle">{safeList(visibleAnalytics.lifecycle).map((item) => <div key={item.skill}><span><strong>{item.skill}</strong><small>{item.status}</small></span><Progress percent={Math.round(item.frequency * 100)} showInfo={false} /><b>{item.change}</b></div>)}</div></Card>
          <Card title="跨岗位技能迁移路径" className="role-evolution-card"><div className="role-evolution-migrations">{safeList(visibleAnalytics.migration).map((item) => <div key={`${item.from}-${item.to}`}><span>{item.from}</span><ArrowRightOutlined /><strong>{item.to}</strong><Tag>{Math.round(item.weight * 100)}%</Tag></div>)}</div><p className="role-evolution-muted">展示市场 JD 中技能在不同岗位之间的关联迁移，不作为当前岗位的岗位内趋势。</p></Card>
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
