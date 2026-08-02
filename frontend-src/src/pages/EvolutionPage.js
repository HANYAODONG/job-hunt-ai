import React, { useEffect, useState } from 'react';
import { Button, Card, Col, Drawer, Row, Select, Space, Tag, Timeline, Typography } from 'antd';
import { ClockCircleOutlined, FileSearchOutlined, SwapOutlined } from '@ant-design/icons';
import PageHeading from '../components/workbench/PageHeading';
import { getRoleEvolution } from '../services/talentApi';

const ChangeGroup = ({ title, items, tone }) => <div className="change-group"><span>{title}</span>{items.length ? <Space wrap>{items.map((item) => <Tag key={item} className={`change-tag ${tone}`}>{item}</Tag>)}</Space> : <Typography.Text type="secondary">无</Typography.Text>}</div>;

const EvolutionPage = () => {
  const [data, setData] = useState(null);
  const [activeVersion, setActiveVersion] = useState(null);
  useEffect(() => { getRoleEvolution().then((result) => { setData(result); setActiveVersion(result.versions[0]); }); }, []);
  if (!data) return <div className="page-loading">正在加载版本记录...</div>;

  return (
    <div className="workbench-page">
      <PageHeading title="岗位演化分析" description="追溯岗位能力定义的每次变化，明确变更依据、影响范围和版本状态。">
        <Select defaultValue={data.role} options={[{ value: data.role }]} className="role-select" />
      </PageHeading>
      <Card className="evolution-summary-card" variant="borderless">
        <div><span className="summary-kicker">当前岗位</span><Typography.Title level={3}>{data.role}</Typography.Title><Typography.Text>已形成 {data.versions.length} 个可追溯版本，最近更新于 {data.versions[0].date}。</Typography.Text></div>
        <div className="evolution-summary-actions"><Tag color="green">当前版本 {data.versions[0].version}</Tag><Button icon={<SwapOutlined />}>比较两个版本</Button></div>
      </Card>
      <Row gutter={[16, 16]} className="evolution-body">
        <Col xs={24} lg={8}>
          <Card className="panel-card timeline-card" title="版本时间轴">
            <Timeline items={data.versions.map((version) => ({ color: version.status === '当前版本' ? '#00a6a6' : '#b9c7c1', children: <button className={`timeline-version ${activeVersion?.version === version.version ? 'active' : ''}`} onClick={() => setActiveVersion(version)}><strong>{version.version}</strong><span>{version.date}</span><Tag>{version.status}</Tag></button> }))} />
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          {activeVersion && <Card className="panel-card version-detail-card" title={<Space><ClockCircleOutlined />{activeVersion.version} · {activeVersion.date}</Space>} extra={<Tag color={activeVersion.status === '当前版本' ? 'green' : 'default'}>{activeVersion.status}</Tag>}>
            <Typography.Title level={4}>本次更新摘要</Typography.Title><Typography.Paragraph>{activeVersion.summary}</Typography.Paragraph>
            <div className="change-grid"><ChangeGroup title="新增能力" items={activeVersion.added} tone="added" /><ChangeGroup title="移除能力" items={activeVersion.removed} tone="removed" /><ChangeGroup title="调整说明" items={activeVersion.modified} tone="modified" /></div>
            <Card className="version-evidence-card" size="small"><FileSearchOutlined /><div><strong>{activeVersion.evidence} 条来源证据支撑本次变更</strong><span>来源已记录采集时间、原始文本片段和交叉验证状态。</span></div><Button type="link" onClick={() => setActiveVersion({ ...activeVersion, showEvidence: true })}>查看</Button></Card>
          </Card>}
        </Col>
      </Row>
      <Drawer title="变更证据" width={480} open={Boolean(activeVersion?.showEvidence)} onClose={() => setActiveVersion({ ...activeVersion, showEvidence: false })}>
        <Typography.Paragraph>证据展示区已为后端返回的岗位文本片段、数据来源、抓取时间与验证结果预留结构。</Typography.Paragraph>
        <Card size="small" className="evidence-card"><strong>企业招聘官网 · 已交叉验证</strong><span>“负责设计和优化多智能体工作流，并建立模型质量评测体系。”</span></Card>
        <Card size="small" className="evidence-card"><strong>招聘平台公开 JD · 可信度 0.91</strong><span>“熟悉 RAG、Agent 编排、LLM 应用链路可观测性。”</span></Card>
      </Drawer>
    </div>
  );
};

export default EvolutionPage;
