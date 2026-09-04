import React, { useMemo, useState } from 'react';
import { Alert, App as AntdApp, Button, Card, Descriptions, Segmented, Space, Tag, Typography } from 'antd';
import { ApiOutlined, CheckCircleOutlined, CloudServerOutlined, ReloadOutlined, SaveOutlined, SettingOutlined, ThunderboltOutlined, WarningOutlined } from '@ant-design/icons';
import PageHeading from '../components/workbench/PageHeading';
import './RuntimeSettingsPage.css';

const PIPELINE_KEY = 'matchingPipelineMode';
const PARSER_KEY = 'resumeParserMode';
const DEFAULTS = { pipeline: 'lightweight', parser: 'auto' };

const readSetting = (key, fallback) => {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
};

const writeSettings = (pipeline, parser) => {
  try {
    localStorage.setItem(PIPELINE_KEY, pipeline);
    localStorage.setItem(PARSER_KEY, parser);
    window.dispatchEvent(new CustomEvent('runtime-settings-changed', { detail: { matchingPipelineMode: pipeline, resumeParserMode: parser } }));
  } catch { /* storage may be unavailable in a restricted browser */ }
};

const parserLabels = { auto: '自动（LLM 优先）', local: '仅本地快速解析', llm: '强制大模型解析' };

const RuntimeSettingsPage = () => {
  const { message } = AntdApp.useApp();
  const [pipeline, setPipeline] = useState(() => readSetting(PIPELINE_KEY, DEFAULTS.pipeline));
  const [parser, setParser] = useState(() => readSetting(PARSER_KEY, DEFAULTS.parser));
  const [saved, setSaved] = useState(false);
  const persistedPipeline = readSetting(PIPELINE_KEY, DEFAULTS.pipeline);
  const persistedParser = readSetting(PARSER_KEY, DEFAULTS.parser);
  const hasChanges = pipeline !== persistedPipeline || parser !== persistedParser;
  const pipelineLabel = pipeline === 'full' ? '完整链路' : '轻量链路';
  const parserDescription = useMemo(() => ({
    auto: '检测到可用的大模型配置时优先调用 LLM；不可用或超时则自动回退本地解析。',
    local: '使用本地轻量解析器，不发起外部大模型请求，适合快速联调和离线环境。',
    llm: '强制调用大模型解析。若服务不可用，本次上传会直接返回错误，不自动回退。',
  }[parser]), [parser]);

  const save = () => { writeSettings(pipeline, parser); setSaved(true); message.success('运行设置已保存'); };
  const reset = () => { setPipeline(DEFAULTS.pipeline); setParser(DEFAULTS.parser); writeSettings(DEFAULTS.pipeline, DEFAULTS.parser); setSaved(true); message.success('已恢复轻量链路默认设置'); };

  return (
    <div className="workbench-page runtime-settings-page">
      <PageHeading eyebrow="RUNTIME CONTROL" title="运行设置" description="控制简历解析与人岗匹配的运行路径。设置只影响当前浏览器，不会改动岗位池或核心算法。">
        <Tag icon={<CheckCircleOutlined />} color="success">当前：{pipelineLabel}</Tag>
      </PageHeading>

      <div className="runtime-settings-grid">
        <Card className="runtime-setting-panel" title={<><ThunderboltOutlined /> 匹配链路</>}>
          <div className="runtime-setting-copy"><Typography.Text strong>默认推荐轻量链路</Typography.Text><Typography.Paragraph type="secondary">轻量链路直接使用 canonical v2 岗位池完成岗位归属和岗位内 JD 排序，不依赖外部检索、图谱或融合服务。</Typography.Paragraph></div>
          <Segmented block value={pipeline} onChange={(value) => { setPipeline(value); setSaved(false); }} options={[{ label: '轻量链路（默认）', value: 'lightweight' }, { label: '完整链路', value: 'full' }]} />
          <div className={`runtime-mode-note ${pipeline === 'full' ? 'is-warning' : 'is-active'}`}>{pipeline === 'full' ? <WarningOutlined /> : <CheckCircleOutlined />}<span>{pipeline === 'full' ? '完整链路会调用 Elasticsearch、Neo4j、BGE-M3 向量和 Fusion 服务。请确认这些服务已由部署环境启动。' : '无需 Docker 或外部服务，上传简历即可走两阶段岗位匹配。'}</span></div>
        </Card>

        <Card className="runtime-setting-panel" title={<><ApiOutlined /> 简历解析</>}>
          <div className="runtime-setting-copy"><Typography.Text strong>大模型解析是显式可控的</Typography.Text><Typography.Paragraph type="secondary">{parserDescription}</Typography.Paragraph></div>
          <Segmented block value={parser} onChange={(value) => { setParser(value); setSaved(false); }} options={Object.entries(parserLabels).map(([value, label]) => ({ label, value }))} />
          <div className="runtime-parser-status"><Tag color={parser === 'llm' ? 'blue' : parser === 'local' ? 'default' : 'green'}>{parserLabels[parser]}</Tag><span>当前上传任务生效</span></div>
        </Card>
      </div>

      {pipeline === 'full' && <Alert className="runtime-settings-alert" type="warning" showIcon icon={<CloudServerOutlined />} message="完整链路运行前检查" description="前端只负责传递 pipeline_mode=full。若任一外部服务不可用，后端应返回明确错误，不会悄悄把完整链路伪装成轻量结果。" />}

      <Card className="runtime-settings-summary" title={<><SettingOutlined /> 当前配置</>}>
        <Descriptions column={{ xs: 1, sm: 2 }} size="small"><Descriptions.Item label="匹配链路"><Tag color={pipeline === 'full' ? 'orange' : 'green'}>{pipelineLabel}</Tag></Descriptions.Item><Descriptions.Item label="解析方式">{parserLabels[parser]}</Descriptions.Item><Descriptions.Item label="岗位池版本">canonical v2</Descriptions.Item><Descriptions.Item label="配置作用范围">本浏览器当前会话</Descriptions.Item></Descriptions>
        <Space className="runtime-settings-actions"><Button icon={<ReloadOutlined />} onClick={reset}>恢复默认</Button><Button type="primary" icon={<SaveOutlined />} onClick={save} disabled={!hasChanges && saved}>保存设置</Button></Space>
      </Card>
    </div>
  );
};

export default RuntimeSettingsPage;
