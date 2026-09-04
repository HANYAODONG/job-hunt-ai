import React, { useState } from 'react';
import { CheckCircleOutlined, FileSearchOutlined, HistoryOutlined, InfoCircleOutlined } from '@ant-design/icons';
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

const tabs = [
  { key: 'explanation', label: '解释', icon: <InfoCircleOutlined /> },
  { key: 'evidence', label: '证据', icon: <FileSearchOutlined /> },
  { key: 'history', label: '记录', icon: <HistoryOutlined /> },
];

const toDisplayText = (value) => {
  if (value == null) return '暂无数据';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(toDisplayText).join('、');
  if (typeof value === 'object') {
    const matched = Array.isArray(value.matched_skills) ? value.matched_skills.join('、') : '';
    const missing = Array.isArray(value.missing_skills) ? value.missing_skills.join('、') : '';
    const reason = value.reason ? toDisplayText(value.reason) : '';
    return [
      matched && `匹配技能：${matched}`,
      missing && `待补充技能：${missing}`,
      reason,
    ].filter(Boolean).join('；') || JSON.stringify(value);
  }
  return String(value);
};

const CapabilityRadar = ({ data }) => (
  <section className="inspector-radar" aria-label="求职者能力雷达图">
    <header>
      <div><span>CAPABILITY PROFILE</span><strong>能力雷达</strong></div>
      <small>基于当前简历证据</small>
    </header>
    <div className="inspector-radar-chart">
      <ResponsiveContainer width="100%" height={292}>
        <RadarChart data={data} outerRadius="78%">
          <PolarGrid stroke="var(--wf-line-strong)" />
          <PolarAngleAxis dataKey="subject" tick={{ fill: '#6b7280', fontSize: 10 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar dataKey="score" stroke="#1677ff" fill="#1677ff" fillOpacity={0.22} strokeWidth={2} />
          <Tooltip formatter={(value) => [`${value}%`, '得分']} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  </section>
);

const TechnicalInspector = ({
  title,
  status = 'AI 生成',
  version = '草稿',
  confidence = 0,
  explanation = [],
  evidence = [],
  history = [],
  hideFacts = false,
  hideHeader = false,
  capabilityRadar = [],
}) => {
  const [active, setActive] = useState('explanation');

  return (
    <aside className="technical-inspector" aria-label={`${toDisplayText(title)}技术检查器`}>
      {!hideHeader && <header className="inspector-header">
        <div>
          <span className="inspector-kicker">TECHNICAL INSPECTOR</span>
          <h2>{toDisplayText(title)}</h2>
        </div>
        <span className="inspector-status"><i />{toDisplayText(status)}</span>
      </header>}

      {!hideFacts && <div className="inspector-facts">
        <div><span>版本</span><strong>{toDisplayText(version)}</strong></div>
        <div><span>置信度</span><strong>{confidence == null ? '未提供' : `${confidence}%`}</strong></div>
      </div>}

      {capabilityRadar.length > 0 && <CapabilityRadar data={capabilityRadar} />}

      <div className="inspector-tabs" role="tablist" aria-label="技术详情">
        {tabs.map((tab) => (
          <button key={tab.key} className={active === tab.key ? 'active' : ''} onClick={() => setActive(tab.key)} role="tab" aria-selected={active === tab.key}>
            {tab.icon}<span>{tab.label}</span>
          </button>
        ))}
      </div>

      <div className="inspector-body">
        {active === 'explanation' && (
          <div className="inspector-explanation">
            <p className="inspector-section-label">为什么得到这个结果？</p>
            {explanation.map((item, index) => (
              <div className="reason-row" key={`${index}-${toDisplayText(item)}`}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <p>{toDisplayText(item)}</p>
              </div>
            ))}
          </div>
        )}
        {active === 'evidence' && (
          <div className="inspector-evidence">
            <p className="inspector-section-label">原始数据证据</p>
            {evidence.map((item, index) => (
              <article className="evidence-entry" key={`${index}-${toDisplayText(item.source)}-${toDisplayText(item.excerpt)}`}>
                <div><strong>{toDisplayText(item.source)}</strong><span>{toDisplayText(item.confidence || '已验证')}</span></div>
                <p>{toDisplayText(item.excerpt)}</p>
                <time>{toDisplayText(item.collectedAt || '2026-07-25 09:42')}</time>
              </article>
            ))}
          </div>
        )}
        {active === 'history' && (
          <ol className="inspector-history">
            {history.map((item, index) => (
              <li key={`${index}-${toDisplayText(item.time)}-${toDisplayText(item.label)}`}>
                <CheckCircleOutlined />
                <div><strong>{toDisplayText(item.label)}</strong><span>{toDisplayText(item.time)}</span></div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </aside>
  );
};

export default TechnicalInspector;
