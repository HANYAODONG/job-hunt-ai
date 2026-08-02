import React, { useEffect, useState } from 'react';
import { App as AntdApp, Button, Progress, Skeleton } from 'antd';
import { CheckCircleOutlined, ExperimentOutlined, FileSearchOutlined, ReloadOutlined } from '@ant-design/icons';
import PageHeading from '../components/workbench/PageHeading';
import { getEvaluationReport } from '../services/talentApi';

const EvaluationPage = () => {
  const { message } = AntdApp.useApp();
  const [data, setData] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState(0);

  useEffect(() => { getEvaluationReport().then(setData); }, []);
  if (!data) return <div className="page-loading"><Skeleton active paragraph={{ rows: 11 }} /></div>;

  const active = data.metrics[selectedMetric];
  const percent = active.value > 100 ? 100 : active.value;

  return <div className="workbench-page evaluation-page">
    <PageHeading
      eyebrow="MODEL QUALITY"
      title="评测中心"
      description="持续验证 JD 解析、简历技能提取和人岗匹配，确保每次能力演化都可复现。"
    >
      <Button icon={<ReloadOutlined />} onClick={() => message.loading({ content: '评测任务已加入队列', duration: 1.1 })}>运行评测</Button>
    </PageHeading>

    <section className="evaluation-banner">
      <div><span><CheckCircleOutlined /> EVALUATION SNAPSHOT</span><h2>核心指标处于可发布范围</h2><p>覆盖 126 条标注 JD、48 份匿名简历样本，并保留误差归因记录。</p></div>
      <div className="evaluation-banner-meta"><strong>2026.07.26</strong><small>最近一次完整运行</small><b>v1.8.2</b></div>
    </section>

    <section className="evaluation-workspace">
      <aside className="evaluation-metric-rail">
        <header><span>BENCHMARKS</span><small>选择指标查看明细</small></header>
        {data.metrics.map((metric, index) => <button type="button" className={index === selectedMetric ? `active tone-${metric.tone}` : `tone-${metric.tone}`} key={metric.label} onClick={() => setSelectedMetric(index)}>
          <span>{metric.label}</span><strong>{metric.value}{metric.value <= 100 ? '%' : ''}</strong><small>目标 {metric.target}{metric.target <= 100 ? '%' : ''}</small>
          <i><u style={{ width: `${Math.min(100, (metric.value / metric.target) * 100)}%` }} /></i>
        </button>)}
      </aside>

      <main className="evaluation-analysis-panel">
        <header><span>QUALITY DETAIL / {String(selectedMetric + 1).padStart(2, '0')}</span><h2>{active.label}</h2><p>当前值与阈值的差异及对应的测试集覆盖情况。</p></header>
        <div className="evaluation-score-row">
          <div className="evaluation-score-ring"><Progress type="circle" percent={percent} format={() => `${active.value}${active.value <= 100 ? '%' : ''}`} strokeColor="#0066ff" trailColor="#edf0f3" size={132} /></div>
          <div className="evaluation-score-copy"><span>RELEASE THRESHOLD</span><strong>{active.target}{active.target <= 100 ? '%' : ''}</strong><p>{active.value >= active.target ? '当前指标达到发布要求，已可进入下一次岗位能力演化。' : '当前指标尚未达到发布要求，建议先完成误差归因和样本补充。'}</p><b className={active.value >= active.target ? 'pass' : 'watch'}>{active.value >= active.target ? 'MEETS TARGET' : 'NEEDS REVIEW'}</b></div>
          <div className="evaluation-sample-box"><ExperimentOutlined /><span>测试样本</span><strong>{active.label.includes('JD') ? '126 JD' : active.label.includes('简历') ? '48 简历' : '174 配对样本'}</strong><small>标注版本 2026.07</small></div>
        </div>
        <section className="evaluation-method-track"><header><span>REPRODUCIBLE RUN</span><small>评测链路记录</small></header><div><b>01</b><span><strong>固定测试集</strong><small>加载匿名标注数据与版本化真值</small></span><em>LOCKED</em></div><div><b>02</b><span><strong>执行解析与匹配</strong><small>使用当前受控词表和模型配置</small></span><em>DONE</em></div><div><b>03</b><span><strong>聚合指标与误差</strong><small>生成可追溯的样本级归因记录</small></span><em>DONE</em></div></section>
      </main>

      <aside className="evaluation-error-panel">
        <header><span>ERROR EXPLORER</span><b>{data.errors.reduce((sum, item) => sum + item.count, 0)}</b></header>
        {data.errors.map((item, index) => <article key={item.category}><span><b>{String(index + 1).padStart(2, '0')}</b> {item.count} samples</span><strong>{item.category}</strong><p>{item.example}</p><button type="button" onClick={() => message.info(`已定位到「${item.category}」的样本集`)}><FileSearchOutlined />查看样本</button></article>)}
      </aside>
    </section>
  </div>;
};

export default EvaluationPage;
