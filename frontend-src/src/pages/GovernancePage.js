import React, { useEffect, useMemo, useState } from 'react';
import { App as AntdApp, Button, Progress, Skeleton } from 'antd';
import {
  CheckOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  FilterOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import PageHeading from '../components/workbench/PageHeading';
import { getDataGovernance } from '../services/talentApi';

const freshnessTone = (value) => value.includes('天') ? 'attention' : value.includes('5') ? 'watch' : 'healthy';

const GovernancePage = () => {
  const { message } = AntdApp.useApp();
  const [data, setData] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);
  const [showIssuesOnly, setShowIssuesOnly] = useState(false);

  useEffect(() => {
    getDataGovernance().then((result) => {
      setData(result);
      setSelectedKey(result.sources[0]?.key || null);
    });
  }, []);

  const sources = useMemo(() => showIssuesOnly
    ? data?.sources.filter((item) => item.valid < 93 || item.freshness.includes('天')) || []
    : data?.sources || [], [data, showIssuesOnly]);
  const selected = sources.find((item) => item.key === selectedKey) || sources[0] || data?.sources[0];

  if (!data) return <div className="page-loading"><Skeleton active paragraph={{ rows: 11 }} /></div>;

  return <div className="workbench-page governance-page">
    <PageHeading
      eyebrow="DATA OPERATIONS"
      title="数据治理"
      description="让每条岗位结论都能回到来源、清洗规则与质量状态。"
    >
      <Button icon={<ReloadOutlined />} onClick={() => message.loading({ content: '正在同步来源…', duration: 1.1 })}>同步来源</Button>
    </PageHeading>

    <section className="governance-overview" aria-label="数据质量概览">
      <div className="governance-score">
        <span>QUALITY SCORE</span>
        <strong>92.4</strong>
        <em>/ 100</em>
        <p><i />较上次同步 <b>+1.8</b>，来源可用性稳定</p>
      </div>
      <div className="governance-summary-line">
        <article><span>本周新入库</span><strong>1,286</strong><small>来自 3 个受控来源</small></article>
        <article><span>可追溯岗位结论</span><strong>98.7%</strong><small>已关联证据与版本记录</small></article>
        <article><span>去重命中</span><strong>314</strong><small>规则与语义双重归并</small></article>
      </div>
      <div className="governance-overview-note"><SafetyCertificateOutlined /><span>证据链完整度达到发布阈值</span><b>READY</b></div>
    </section>

    <section className="governance-workspace">
      <aside className="governance-source-list">
        <header><span>CONTROLLED SOURCES</span><Button type="text" icon={<FilterOutlined />} onClick={() => setShowIssuesOnly((value) => !value)}>{showIssuesOnly ? '全部' : '需关注'}</Button></header>
        <div className="governance-source-list-body">
          {sources.map((item) => <button type="button" key={item.key} className={item.key === selected?.key ? 'active' : ''} onClick={() => setSelectedKey(item.key)}>
            <span className={`source-state ${freshnessTone(item.freshness)}`}><i />{item.freshness}</span>
            <strong>{item.source}</strong>
            <small>{item.owner}</small>
            <b>{item.records}</b>
          </button>)}
        </div>
      </aside>

      {selected && <main className="governance-source-detail">
        <header className="governance-detail-header">
          <div><span>SOURCE PROFILE / {selected.key}</span><h2>{selected.source}</h2><p>{selected.owner}，最近一次采集完成于 {selected.freshness}</p></div>
          <Button icon={<CheckOutlined />} onClick={() => message.success('该来源的治理配置已通过校验')}>运行校验</Button>
        </header>
        <div className="source-health-grid">
          <article><span>有效记录</span><strong>{selected.records}</strong><small>本采集周期</small></article>
          <article><span>有效率</span><strong>{selected.valid}%</strong><Progress percent={selected.valid} showInfo={false} strokeColor="#0066ff" trailColor="#e8eaed" /></article>
          <article><span>重复率</span><strong>{selected.duplicate}%</strong><small>低于 6% 阈值</small></article>
          <article><span>追溯状态</span><strong>完整</strong><small>来源、时间和规则均已记录</small></article>
        </div>
        <section className="governance-rule-track">
          <header><span>PROCESSING RECORD</span><small>最近运行的标准化链路</small></header>
          <div className="rule-track-row"><b>01</b><span><strong>字段抽取与结构校验</strong><small>岗位名称、职责、技术栈、地区字段完整</small></span><em>已完成</em></div>
          <div className="rule-track-row"><b>02</b><span><strong>岗位与技能术语归一</strong><small>已按当前受控词表映射，保留原始文本</small></span><em>已完成</em></div>
          <div className="rule-track-row"><b>03</b><span><strong>跨来源重复与冲突检测</strong><small>发现 {selected.duplicate}% 的候选重复，已入审计记录</small></span><em>可追溯</em></div>
        </section>
      </main>}

      <aside className="governance-attention-panel">
        <header><span>ATTENTION QUEUE</span><b>{data.issues.length}</b></header>
        {data.issues.map((issue, index) => <article key={issue.title}>
          <span><ExclamationCircleOutlined /> ISSUE {String(index + 1).padStart(2, '0')}</span>
          <strong>{issue.title}</strong>
          <p>{issue.detail}</p>
          <button type="button" onClick={() => message.info('已打开关联审计记录')}>查看记录</button>
        </article>)}
        <footer><DatabaseOutlined /><span>近 30 天保留原始采集快照与规则版本</span></footer>
      </aside>
    </section>
  </div>;
};

export default GovernancePage;
