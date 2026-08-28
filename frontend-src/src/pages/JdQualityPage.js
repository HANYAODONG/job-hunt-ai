import React, { useEffect, useMemo, useState } from 'react';
import { App as AntdApp, Button, Progress, Select, Skeleton, Tag } from 'antd';
import {
  ApiOutlined,
  CheckCircleOutlined,
  ExperimentOutlined,
  RadarChartOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import PageHeading from '../components/workbench/PageHeading';
import { getJdQualitySample } from '../services/talentApi';
import './JdQualityPage.css';

const riskLabels = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
};

const riskTone = {
  high: 'error',
  medium: 'warning',
  low: 'success',
};

const policyLabels = {
  hold_for_review: '暂缓入图，进入人工复核',
  downweight_and_trace: '降权入图，保留证据追踪',
  allow_with_trace: '允许入图，保留来源证据',
};

const metricPercent = (value) => Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100);

const StructuredSummary = ({ total, highCount, mediumCount, avgInflation, fallback }) => {
  if (!total) return <h2>正在等待 JD 审核结果</h2>;
  return (
    <div className="jd-quality-structured-summary" aria-label={fallback || 'JD 审核统计摘要'}>
      <p>
        <span>本批次共审核</span>
        <b className="summary-total">{total}</b>
        <span>条 JD</span>
      </p>
      <p>
        <span>高风险</span>
        <b className="summary-high">{highCount}</b>
        <span>条</span>
      </p>
      <p>
        <span>中风险</span>
        <b className="summary-medium">{mediumCount}</b>
        <span>条</span>
      </p>
      <p>
        <span>平均通胀风险</span>
        <b className="summary-inflation">{avgInflation}%</b>
      </p>
      <p className="summary-advice">
        <span>建议高风险 JD 暂缓直接写入能力图谱，先进入人工复核队列</span>
      </p>
    </div>
  );
};

const JdQualityPage = () => {
  const { message } = AntdApp.useApp();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [useLlm, setUseLlm] = useState(false);
  const [limit, setLimit] = useState(30);
  const [selectedRisk, setSelectedRisk] = useState('all');

  const loadData = async (llm = useLlm, nextLimit = limit) => {
    setLoading(true);
    try {
      const result = await getJdQualitySample({ limit: nextLimit, useLlm: llm, llmLimit: 5 });
      setData(result);
      setUseLlm(llm);
      if (llm && result.summary?.llm_warning) message.warning(result.summary.llm_warning);
    } catch (error) {
      message.error(error.message || 'JD 质量审核接口不可用');
    } finally {
      setLoading(false);
    }
  };

  const handleLimitChange = (value) => {
    setLimit(value);
    loadData(useLlm, value);
  };

  useEffect(() => {
    loadData(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const items = useMemo(() => data?.items || [], [data]);
  const summary = data?.summary || {};
  const filteredItems = useMemo(() => (
    selectedRisk === 'all' ? items : items.filter((item) => item.risk_level === selectedRisk)
  ), [items, selectedRisk]);

  const riskCounts = summary.risk_counts || {};
  const highCount = riskCounts.high || 0;
  const mediumCount = riskCounts.medium || 0;
  const lowCount = riskCounts.low || 0;
  const avgInflation = metricPercent(summary.average_inflation_score);
  const topIssues = summary.top_issues || [];
  const topSkills = summary.top_suspected_skills || [];
  const scanNodes = items.slice(0, 22).map((item, index) => ({
    ...item,
    left: 10 + ((index * 31) % 78),
    top: 12 + ((index * 47) % 66),
  }));

  if (loading && !data) {
    return <div className="workbench-page jd-quality-page"><Skeleton active paragraph={{ rows: 12 }} /></div>;
  }

  return (
    <div className="workbench-page jd-quality-page">
      <PageHeading
        eyebrow="JD QUALITY AUDIT"
        title="JD 通胀与噪声检测"
        description="在岗位技能入图前，对 JD 的技能堆叠、模板噪声和证据不足问题做预审，减少脏数据进入能力图谱。"
      >
        <Select
          value={limit}
          onChange={handleLimitChange}
          options={[30, 50, 100].map((value) => ({ value, label: `${value} 条样例` }))}
          style={{ width: 130 }}
        />
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => loadData(false)}>规则审核</Button>
        <Button type="primary" icon={<ThunderboltOutlined />} loading={loading} onClick={() => loadData(true)}>
          DeepSeek 增强总结
        </Button>
      </PageHeading>

      <section className="jd-quality-hero">
        <div className="jd-quality-radar-panel">
          <div className="jd-quality-radar-header">
            <span><RadarChartOutlined /> LIVE JD SCREENING</span>
            <b>{items.length || 0} 条 JD</b>
          </div>
          <div className="jd-quality-radar-stage">
            <div className="jd-quality-scan-line" />
            <div className="jd-quality-radar-ring ring-one" />
            <div className="jd-quality-radar-ring ring-two" />
            <div className="jd-quality-radar-ring ring-three" />
            {scanNodes.map((item) => (
              <button
                type="button"
                key={item.job_id}
                className={`jd-quality-radar-node ${item.risk_level}`}
                style={{ left: `${item.left}%`, top: `${item.top}%` }}
                title={`${item.title} · ${riskLabels[item.risk_level] || item.risk_level}`}
                onClick={() => setSelectedRisk(item.risk_level)}
              >
                <span />
              </button>
            ))}
            <div className="jd-quality-radar-core">
              <strong>{avgInflation}%</strong>
              <span>AVG INFLATION</span>
            </div>
          </div>
          <div className="jd-quality-radar-footer">
            <article><span>高风险拦截</span><strong>{highCount}</strong></article>
            <article><span>中风险降权</span><strong>{mediumCount}</strong></article>
            <article><span>可信入图</span><strong>{lowCount}</strong></article>
          </div>
        </div>
        <div className="jd-quality-summary-card">
          <div className="jd-quality-summary-label"><SafetyCertificateOutlined /> LLM SCREENING SUMMARY</div>
          <StructuredSummary
            total={summary.total || items.length}
            highCount={highCount}
            mediumCount={mediumCount}
            avgInflation={avgInflation}
            fallback={summary.overall_summary}
          />
          <div className="jd-quality-summary-tags">
            <Tag color={useLlm && summary.llm_used ? 'blue' : 'default'}>{useLlm && summary.llm_used ? 'DeepSeek 已介入' : '规则模式'}</Tag>
            <Tag color="cyan">证据约束</Tag>
            <Tag color="purple">入图前过滤</Tag>
          </div>
          {summary.llm_warning && <p className="jd-quality-warning"><WarningOutlined /> {summary.llm_warning}</p>}
          {!!summary.risk_insights?.length && (
            <div className="jd-quality-insights">
              {summary.risk_insights.map((item) => <span key={item}>{item}</span>)}
            </div>
          )}
          {!summary.risk_insights?.length && (
            <div className="jd-quality-insights">
              {topIssues.slice(0, 4).map((item) => <span key={item.issue}>{item.issue} × {item.count}</span>)}
            </div>
          )}
          <div className="jd-quality-mini-flow">
            <span>JD 输入</span>
            <i />
            <span>规则筛查</span>
            <i />
            <span>LLM 复核</span>
            <i />
            <span>入图策略</span>
          </div>
        </div>
      </section>

      <section className="jd-quality-metrics">
        <article><span>审核 JD</span><strong>{summary.total || items.length}</strong><small>来自标准数据样例</small></article>
        <article><span>高风险</span><strong>{highCount}</strong><small>建议人工复核</small></article>
        <article><span>中风险</span><strong>{mediumCount}</strong><small>降权并追踪</small></article>
        <article><span>平均通胀风险</span><strong>{avgInflation}%</strong><Progress percent={avgInflation} showInfo={false} strokeColor="#0b7a68" /></article>
      </section>

      <section className="jd-quality-workspace">
        <aside className="jd-quality-sidebar">
          <header><ExperimentOutlined /> 审核维度</header>
          <button type="button" className={selectedRisk === 'all' ? 'active' : ''} onClick={() => setSelectedRisk('all')}>全部 JD <b>{items.length}</b></button>
          <button type="button" className={selectedRisk === 'high' ? 'active danger' : ''} onClick={() => setSelectedRisk('high')}>高风险 <b>{highCount}</b></button>
          <button type="button" className={selectedRisk === 'medium' ? 'active warn' : ''} onClick={() => setSelectedRisk('medium')}>中风险 <b>{mediumCount}</b></button>
          <button type="button" className={selectedRisk === 'low' ? 'active ok' : ''} onClick={() => setSelectedRisk('low')}>低风险 <b>{lowCount}</b></button>
          <div className="jd-quality-sidebar-note">
            <ApiOutlined />
            <span>接口：/api/v1/jd-quality/sample。可接入真实 JD 导入链路后批量调用 /batch。</span>
          </div>
          {!!topSkills.length && (
            <div className="jd-quality-sidebar-skills">
              <header>疑似通胀技能</header>
              {topSkills.slice(0, 6).map((item) => <span key={item.skill}>{item.skill} <b>{item.count}</b></span>)}
            </div>
          )}
        </aside>

        <main className="jd-quality-list">
          {filteredItems.map((item) => (
            <article className={`jd-quality-item ${item.risk_level}`} key={item.job_id}>
              <header>
                <div>
                  <span>{item.job_id}</span>
                  <h3>{item.title}</h3>
                </div>
                <Tag color={riskTone[item.risk_level]}>{riskLabels[item.risk_level] || item.risk_level}</Tag>
              </header>
              <div className="jd-quality-score-row">
                <div><span>通胀风险</span><Progress percent={metricPercent(item.inflation_score)} size="small" strokeColor="#0b7a68" /></div>
                <div><span>模板噪声</span><Progress percent={metricPercent(item.noise_score)} size="small" strokeColor="#d39431" /></div>
                <div><span>证据不足</span><Progress percent={metricPercent(item.evidence_risk)} size="small" strokeColor="#6558b8" /></div>
              </div>
              <p>{item.llm_summary || item.local_summary}</p>
              <div className="jd-quality-evidence">
                {(item.evidence || []).slice(0, 3).map((evidence) => <span key={evidence}>{evidence}</span>)}
              </div>
              <footer>
                <span><CheckCircleOutlined /> {policyLabels[item.graph_policy] || item.graph_policy}</span>
                {!!item.suspected_inflated_skills?.length && <small>疑似通胀技能：{item.suspected_inflated_skills.slice(0, 6).join('、')}</small>}
              </footer>
            </article>
          ))}
        </main>
      </section>
    </div>
  );
};

export default JdQualityPage;
