import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Button,
  Slider,
  Row,
  Col,
  Typography,
  Space,
  Spin,
  Alert,
  Tag,
  Divider,
  message,
  InputNumber,
  Descriptions,
  Statistic,
  Switch,
} from 'antd';
import {
  ReloadOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  SettingOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import FusionScoreCard from '../components/FusionScoreCard';
import { getMockRankedResults, getWeights, updateWeights, resetWeights } from '../services/fusionApi';
import './FusionDemoPage.css';

const { Title, Text, Paragraph } = Typography;

// ── 因子配置 ────────────────────────────────────────────────────
const FACTORS = [
  { key: 'bm25', label: '关键词匹配 (BM25)', icon: '🔤', tip: '来自工作流2：Elasticsearch BM25 得分' },
  { key: 'semantic', label: '语义相似度', icon: '🧠', tip: '来自工作流2：向量嵌入语义相似度' },
  { key: 'skill_coverage', label: '技能覆盖', icon: '🎯', tip: '来自工作流3：技能覆盖率', weight: 0.30 },
  { key: 'job_family', label: '岗位大类匹配', icon: '🏢', tip: '来自工作流3：岗位类别匹配' },
  { key: 'graph', label: '知识图谱关联', icon: '🔗', tip: '来自工作流3：KG关系网络关联度' },
];

const DEFAULT_WEIGHTS = { bm25: 0.15, semantic: 0.25, skill_coverage: 0.30, job_family: 0.15, graph: 0.15 };

export default function FusionDemoPage() {
  // ── State ──────────────────────────────────────────────────
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [weights, setWeights] = useState({ ...DEFAULT_WEIGHTS });
  const [serverWeights, setServerWeights] = useState(null);
  const [numJobs, setNumJobs] = useState(20);
  const [seed, setSeed] = useState(null);
  const [useServerWeights, setUseServerWeights] = useState(false);
  const [showWeightsPanel, setShowWeightsPanel] = useState(true);
  const [queryId] = useState(`fusion_demo_${Date.now()}`);

  // ── 加载权重 ───────────────────────────────────────────────
  useEffect(() => {
    loadServerWeights();
  }, []);

  const loadServerWeights = async () => {
    try {
      const data = await getWeights();
      setServerWeights(data.weights);
    } catch {
      // 后端不可用，使用默认值
    }
  };

  // ── 执行 Mock 融合排序 ─────────────────────────────────────
  const handleMockRank = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const activeWeights = useServerWeights ? serverWeights || DEFAULT_WEIGHTS : weights;

      const data = await getMockRankedResults(queryId, numJobs, seed, activeWeights);
      setResults(data);

      if (data.results.length > 0) {
        message.success(`成功生成 ${data.results.length} 条融合结果`);
      }
    } catch (err) {
      setError(err.message);
      message.error('融合排序失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [queryId, numJobs, seed, weights, useServerWeights, serverWeights]);

  // ── 更新服务端权重 ─────────────────────────────────────────
  const handleUpdateServerWeights = async () => {
    try {
      await updateWeights(weights);
      message.success('服务端权重已更新');
      setServerWeights({ ...weights });
    } catch (err) {
      message.error('更新服务端权重失败: ' + err.message);
    }
  };

  const handleResetWeights = async () => {
    setWeights({ ...DEFAULT_WEIGHTS });
    try {
      await resetWeights();
      setServerWeights({ ...DEFAULT_WEIGHTS });
      message.success('权重已恢复默认');
    } catch {
      // 后端不可用
    }
  };

  // ── 权重滑块变化 ───────────────────────────────────────────
  const handleWeightChange = (key, value) => {
    setWeights((prev) => ({ ...prev, [key]: value }));
  };

  // 验证权重之和
  const weightSum = Object.values(weights).reduce((a, b) => a + b, 0);
  const weightsValid = Math.abs(weightSum - 1.0) < 0.01;

  // ── 统计数据 ───────────────────────────────────────────────
  const stats = results
    ? {
        total: results.results.length,
        avgScore: Math.round(
          (results.results.reduce((s, r) => s + r.final_score, 0) / results.results.length) * 100
        ),
        topScore: results.results.length
          ? Math.round(results.results[0].final_score * 100)
          : 0,
        highQuality: results.results.filter((r) => r.final_score >= 0.75).length,
        mediumQuality: results.results.filter(
          (r) => r.final_score >= 0.55 && r.final_score < 0.75
        ).length,
        lowQuality: results.results.filter((r) => r.final_score < 0.55).length,
      }
    : null;

  // ── Render ─────────────────────────────────────────────────
  return (
    <div className="fusion-demo-page">
      {/* ── 页头 ── */}
      <div className="fusion-page-header">
        <Title level={2}>
          <ExperimentOutlined /> 工作流4：融合排序演示
        </Title>
        <Paragraph type="secondary">
          独立 Mock 模式 — 不依赖其他工作流。后期接入真实 BM25 / Semantic / KG 分数后替换数据源。
        </Paragraph>
      </div>

      {/* ── 权重配置面板 ── */}
      <Card
        className="weights-panel"
        title={
          <Space>
            <SettingOutlined />
            <span>融合权重配置</span>
            {!weightsValid && (
              <Tag color="error">权重之和: {weightSum.toFixed(2)}（需为 1.00）</Tag>
            )}
            {weightsValid && (
              <Tag color="success">权重之和: 1.00 ✓</Tag>
            )}
          </Space>
        }
        extra={
          <Space>
            <Switch
              checkedChildren="服务端权重"
              unCheckedChildren="本地权重"
              checked={useServerWeights}
              onChange={setUseServerWeights}
            />
            <Button size="small" onClick={handleResetWeights}>
              恢复默认
            </Button>
            {!useServerWeights && (
              <Button
                size="small"
                type="primary"
                onClick={handleUpdateServerWeights}
                disabled={!weightsValid}
              >
                推送到服务端
              </Button>
            )}
          </Space>
        }
        style={{ marginBottom: 20 }}
      >
        <Row gutter={[24, 16]}>
          {FACTORS.map((factor) => (
            <Col key={factor.key} span={12} md={24 / FACTORS.length}>
              <div className="factor-slider">
                <Text className="factor-label">
                  {factor.icon} {factor.label}
                </Text>
                <Row align="middle" gutter={8}>
                  <Col flex="auto">
                    <Slider
                      min={0}
                      max={0.5}
                      step={0.01}
                      value={weights[factor.key]}
                      onChange={(v) => handleWeightChange(factor.key, v)}
                      disabled={useServerWeights}
                    />
                  </Col>
                  <Col flex="60px">
                    <InputNumber
                      size="small"
                      min={0}
                      max={1}
                      step={0.05}
                      value={weights[factor.key]}
                      onChange={(v) => handleWeightChange(factor.key, v || 0)}
                      disabled={useServerWeights}
                      style={{ width: 60 }}
                    />
                  </Col>
                </Row>
              </div>
            </Col>
          ))}
        </Row>
      </Card>

      {/* ── 控制栏 ── */}
      <Card style={{ marginBottom: 20 }}>
        <Row align="middle" gutter={16} justify="space-between">
          <Col>
            <Space>
              <Text strong>生成数量：</Text>
              <InputNumber min={5} max={100} value={numJobs} onChange={setNumJobs} />
              <Text type="secondary">Seed：</Text>
              <InputNumber
                min={0}
                max={99999}
                value={seed}
                onChange={setSeed}
                placeholder="随机"
                style={{ width: 80 }}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              <Button
                type="primary"
                size="large"
                icon={<ThunderboltOutlined />}
                onClick={handleMockRank}
                loading={loading}
                disabled={!weightsValid}
              >
                生成 Mock 融合结果
              </Button>
              <Button icon={<ReloadOutlined />} onClick={handleMockRank} loading={loading}>
                刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* ── 错误提示 ── */}
      {error && (
        <Alert message="融合排序失败" description={error} type="error" showIcon style={{ marginBottom: 20 }} />
      )}

      {/* ── Loading ── */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="正在融合排序..." />
        </div>
      )}

      {/* ── 统计卡片 ── */}
      {stats && (
        <Row gutter={16} style={{ marginBottom: 20 }}>
          <Col span={6}>
            <Card>
              <Statistic title="总岗位数" value={stats.total} prefix={<BarChartOutlined />} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="最高得分"
                value={stats.topScore}
                suffix="%"
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="平均得分"
                value={stats.avgScore}
                suffix="%"
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Row gutter={8}>
                <Col span={8}>
                  <Statistic title="优秀" value={stats.highQuality} valueStyle={{ color: '#52c41a', fontSize: 20 }} />
                </Col>
                <Col span={8}>
                  <Statistic title="良好" value={stats.mediumQuality} valueStyle={{ color: '#1890ff', fontSize: 20 }} />
                </Col>
                <Col span={8}>
                  <Statistic title="一般" value={stats.lowQuality} valueStyle={{ color: '#faad14', fontSize: 20 }} />
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>
      )}

      {/* ── 融合结果列表 ── */}
      {results && results.results.length > 0 && (
        <>
          <Divider orientation="left">
            <Space>
              <BarChartOutlined />
              <span>排序结果</span>
              <Tag color="blue">共 {results.results.length} 条</Tag>
              {results.weights_used && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  权重: BM25={results.weights_used.bm25} | Semantic={results.weights_used.semantic} |
                  Skill={results.weights_used.skill_coverage} | Family={results.weights_used.job_family} |
                  Graph={results.weights_used.graph}
                </Text>
              )}
            </Space>
          </Divider>

          {results.results.map((result) => (
            <FusionScoreCard
              key={result.job_id}
              result={result}
              rank={result.rank}
              showRank
            />
          ))}
        </>
      )}

      {/* ── 空状态 ── */}
      {!loading && !results && !error && (
        <Card style={{ textAlign: 'center', padding: 60 }}>
          <ExperimentOutlined style={{ fontSize: 48, color: '#bbb' }} />
          <Title level={4} type="secondary" style={{ marginTop: 16 }}>
            尚未生成融合结果
          </Title>
          <Paragraph type="secondary">
            调整权重配置，点击「生成 Mock 融合结果」查看排序和解释效果
          </Paragraph>
        </Card>
      )}
    </div>
  );
}
