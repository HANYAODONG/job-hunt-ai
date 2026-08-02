import React, { useState } from 'react';
import { CheckCircleOutlined, FileSearchOutlined, HistoryOutlined, InfoCircleOutlined } from '@ant-design/icons';

const tabs = [
  { key: 'explanation', label: '解释', icon: <InfoCircleOutlined /> },
  { key: 'evidence', label: '证据', icon: <FileSearchOutlined /> },
  { key: 'history', label: '记录', icon: <HistoryOutlined /> },
];

const TechnicalInspector = ({ title, status = 'AI 生成', version = '草稿', confidence = 0, explanation = [], evidence = [], history = [] }) => {
  const [active, setActive] = useState('explanation');

  return (
    <aside className="technical-inspector" aria-label={`${title}技术检查器`}>
      <header className="inspector-header">
        <div>
          <span className="inspector-kicker">TECHNICAL INSPECTOR</span>
          <h2>{title}</h2>
        </div>
        <span className="inspector-status"><i />{status}</span>
      </header>

      <div className="inspector-facts">
        <div><span>版本</span><strong>{version}</strong></div>
        <div><span>置信度</span><strong>{confidence}%</strong></div>
      </div>

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
            <p className="inspector-section-label">为什么得到这个结果</p>
            {explanation.map((item, index) => <div className="reason-row" key={item}><span>{String(index + 1).padStart(2, '0')}</span><p>{item}</p></div>)}
          </div>
        )}
        {active === 'evidence' && (
          <div className="inspector-evidence">
            <p className="inspector-section-label">原始数据证据</p>
            {evidence.map((item) => (
              <article className="evidence-entry" key={`${item.source}-${item.excerpt}`}>
                <div><strong>{item.source}</strong><span>{item.confidence || '已验证'}</span></div>
                <p>“{item.excerpt}”</p>
                <time>{item.collectedAt || '2026-07-25 09:42'}</time>
              </article>
            ))}
          </div>
        )}
        {active === 'history' && (
          <ol className="inspector-history">
            {history.map((item) => <li key={`${item.time}-${item.label}`}><CheckCircleOutlined /><div><strong>{item.label}</strong><span>{item.time}</span></div></li>)}
          </ol>
        )}
      </div>
    </aside>
  );
};

export default TechnicalInspector;
