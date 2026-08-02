import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card,
  Button,
  Slider,
  Row,
  Col,
  Typography,
  Space,
  Skeleton,
  Alert,
  Tag,
  Divider,
  message,
  InputNumber,
  Statistic,
  Switch,
  Input,
  Segmented,
  Empty,
} from 'antd';
import {
  ReloadOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  SettingOutlined,
  BarChartOutlined,
  SearchOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import FusionScoreCard from '../components/FusionScoreCard';
import { getMockRankedResults, rankFromQuery, getWeights, updateWeights, resetWeights } from '../services/fusionApi';
import './FusionDemoPage.css';

const { Title, Text, Paragraph } = Typography;

// ── 因子配置（key 用于权重API，breakdownKey 用于展示）─────────────────
const FACTORS = [
  { key: 'bm25', breakdownKey: 'bm25_score', label: '关键词匹配 (BM25)', icon: '🔤', tip: '来自工作流5：Elasticsearch BM25 得分' },
  { key: 'semantic', breakdownKey: 'semantic_score', label: '语义相似度', icon: '🧠', tip: '来自工作流2：向量嵌入语义相似度' },
  { key: 'skill_coverage', breakdownKey: 'skill_coverage', label: '技能覆盖', icon: '🎯', tip: '来自工作流3：技能覆盖率' },
  { key: 'job_family', breakdownKey: 'job_family_match', label: '岗位大类匹配', icon: '🏢', tip: '来自工作流3：岗位类别匹配' },
  { key: 'graph', breakdownKey: 'graph_relatedness', label: '知识图谱关联', icon: '🔗', tip: '来自工作流3：KG关系网络关联度' },
];

const DEFAULT_WEIGHTS = { bm25: 0.15, semantic: 0.25, skill_coverage: 0.30, job_family: 0.15, graph: 0.15 };

const EXAMPLE_QUERIES = [
  { label: 'Python 数据分析', text: '熟悉 Python、SQL、数据分析，有3年经验，期望数据工程师岗位' },
  { label: 'Java 后端开发', text: 'Java、Spring Boot、微服务架构，5年后端开发经验，期望后端开发工程师' },
  { label: '前端 React', text: 'React、TypeScript、Node.js，2年前端开发经验，期望前端开发工程师' },
  { label: 'AI 算法', text: 'Python、TensorFlow、PyTorch，深度学习模型训练经验，期望算法工程师' },
];

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
  const [queryId] = useState(`fusion_demo_${Date.now()}`);

  // ── 模式切换（Mock / 真实BM25）─────────────────────────────
  const [mode, setMode] = useState('bm25');  // 'mock' | 'bm25'
  const [queryText, setQueryText] = useState('');
  const [bm25Size, setBm25Size] = useState(20);
  const [searched, setSearched] = useState(false);  // 是否已搜索过

  const resultsRef = useRef(null);  // 结果区域 ref，用于自动滚动

  // ── 数据来源标注（key 对应 ScoreBreakdown 字段名）─────────────
  const dataSources = mode === 'bm25'
    ? { bm25_score: 'real', semantic_score: 'pending', skill_coverage: 'pending', job_family_match: 'pending', graph_relatedness: 'pending' }
    : { bm25_score: 'mock', semantic_score: 'mock', skill_coverage: 'mock', job_family_match: 'mock', graph_relatedness: 'mock' };

  // ── BM25-only 快捷权重 ─────────────────────────────────────
  const bm25OnlyWeights = { bm25: 1.0, semantic: 0.0, skill_coverage: 0.0, job_family: 0.0, graph: 0.0 };

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
      setSearched(true);

      if (data.results.length > 0) {
        message.success(`成功生成 ${data.results.length} 条 Mock 融合结果`);
        setTimeout(() => {
          resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
      }
    } catch (err) {
      setError(err.message);
      message.error('融合排序失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [queryId, numJobs, seed, weights, useServerWeights, serverWeights]);

  // ── 执行真实 BM25 融合排序 ─────────────────────────────────
  const handleBm25Search = useCallback(async () => {
    if (!queryText.trim()) {
      message.warning('请输入查询文本');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const activeWeights = useServerWeights ? serverWeights || DEFAULT_WEIGHTS : weights;

      const data = await rankFromQuery(queryText.trim(), {
        size: bm25Size,
        weights: activeWeights,
      });
      setResults(data);
      setSearched(true);

      if (data.results.length > 0) {
        message.success(`BM25 召回 ${data.results.length} 条结果，已融合排序`);
        // 自动滚动到结果区域
        setTimeout(() => {
          resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
        // 如果有真实BM25原始分数，展示在控制台
        const rawScores = data.results
          .filter(r => r.meta?.bm25_score_raw)
          .map(r => `${r.job_id}: raw=${r.meta.bm25_score_raw.toFixed(2)}`);
        if (rawScores.length > 0) {
          console.log('BM25原始分数:', rawScores.slice(0, 5), '...');
        }
      } else {
        message.info('BM25 未召回结果，请尝试其他查询词');
      }
    } catch (err) {
      setError(err.message);
      message.error('BM25 融合排序失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [queryText, bm25Size, weights, useServerWeights, serverWeights]);

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
  const weightsValid = Math.abs(weightSum - 1.0) < 0.005;

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
          支持 Mock 模拟数据和真实 BM25 检索两种模式。其余因子（semantic / skill / graph）待其他工作流接入。
        </Paragraph>

        {/* 模式切换 + 当前模式标注 */}
        <Segmented
          value={mode}
          onChange={(val) => {
            setMode(val);
            setResults(null);
            setError(null);
            setSearched(false);
            if (val === 'bm25') {
              setWeights({ ...bm25OnlyWeights });
            } else {
              setWeights({ ...DEFAULT_WEIGHTS });
            }
          }}
          options={[
            { label: <><SearchOutlined /> BM25 真实检索</>, value: 'bm25' },
            { label: <><ApiOutlined /> Demo 演示</>, value: 'mock' },
          ]}
          block
          style={{ marginBottom: 16 }}
        />

        {/* 当前模式提示 Banner */}
        {mode === 'bm25' ? (
          <Alert
            message="真实数据模式"
            description="当前使用 Elasticsearch BM25 真实检索。其他因子（语义相似度、技能覆盖、岗位大类、知识图谱）待工作流2/3接入后自动生效。"
            type="info"
            showIcon
            icon={<SearchOutlined />}
            style={{ marginBottom: 16 }}
          />
        ) : (
          <Alert
            message="Demo 演示模式"
            description="当前使用本地随机生成的模拟数据展示 UI 效果。所有分数均为随机值，不代表真实算法结果。点击「BM25 真实检索」切换到真实数据模式。"
            type="warning"
            showIcon
            icon={<ApiOutlined />}
            style={{ marginBottom: 16 }}
          />
        )}
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
          {FACTORS.map((factor) => {
            const src = dataSources[factor.breakdownKey] || 'mock';
            return (
            <Col key={factor.key} span={12} md={24 / FACTORS.length}>
              <div className="factor-slider">
                <Text className="factor-label">
                  {factor.icon} {factor.label}
                  {src === 'real' && <Tag color="green" style={{ marginLeft: 4, fontSize: 10 }}>真实</Tag>}
                  {src === 'pending' && <Tag color="blue" style={{ marginLeft: 4, fontSize: 10 }}>待接入</Tag>}
                  {src === 'mock' && <Tag color="default" style={{ marginLeft: 4, fontSize: 10 }}>模拟</Tag>}
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
          )})}
        </Row>
      </Card>

      {/* ── 控制栏 ── */}
      <Card style={{ marginBottom: 20 }}>
        {mode === 'bm25' ? (
          /* ── BM25 真实模式：查询输入 ── */
          <>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12, marginRight: 8 }}>💡 试试：</Text>
              {EXAMPLE_QUERIES.map((eq) => (
                <Tag
                  key={eq.label}
                  color="blue"
                  style={{ cursor: 'pointer', marginBottom: 4 }}
                  onClick={() => setQueryText(eq.text)}
                >
                  {eq.label}
                </Tag>
              ))}
            </div>
            <Row gutter={16} align="middle">
              <Col flex="auto">
                <Input.TextArea
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder="输入查询文本 — 例如：熟悉 Python、SQL、TensorFlow，有3年数据分析经验，期望算法工程师岗位"
                  rows={3}
                  style={{ fontSize: 14 }}
                  onPressEnter={(e) => {
                    if (!e.shiftKey) {
                      e.preventDefault();
                      handleBm25Search();
                    }
                  }}
                />
              </Col>
              <Col>
                <Space direction="vertical" align="center">
                  <Text type="secondary" style={{ fontSize: 12 }}>召回数</Text>
                  <InputNumber min={5} max={200} value={bm25Size} onChange={setBm25Size} />
                </Space>
              </Col>
            </Row>
            <Row justify="space-between" align="middle" style={{ marginTop: 12 }}>
              <Col>
                <Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    💡 当前只有 BM25 分数来自真实 ES 检索，其余因子待工作流2/3接入后自动填充
                  </Text>
                </Space>
              </Col>
              <Col>
                <Space>
                  <Button
                    onClick={() => setWeights({ ...bm25OnlyWeights })}
                    size="small"
                    disabled={useServerWeights}
                  >
                    BM25-Only 权重
                  </Button>
                  <Button
                    type="primary"
                    size="large"
                    icon={<SearchOutlined />}
                    onClick={handleBm25Search}
                    loading={loading}
                    disabled={!weightsValid || !queryText.trim()}
                  >
                    搜索并融合排序
                  </Button>
                </Space>
              </Col>
            </Row>
          </>
        ) : (
          /* ── Mock 模式：数量 + Seed ── */
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
        )}
      </Card>

      {/* ── 错误提示 ── */}
      {error && (
        <Alert message="融合排序失败" description={error} type="error" showIcon style={{ marginBottom: 20 }} />
      )}

      {/* ── Loading 骨架屏 ── */}
      {loading && (
        <div style={{ padding: '0 4px' }}>
          <Row gutter={16} style={{ marginBottom: 20 }}>
            {[1, 2, 3, 4].map((i) => (
              <Col span={6} key={i}>
                <Card><Skeleton active paragraph={{ rows: 1 }} title={{ width: '60%' }} /></Card>
              </Col>
            ))}
          </Row>
          {[1, 2, 3].map((i) => (
            <Card key={i} style={{ marginBottom: 16 }}>
              <Skeleton active avatar paragraph={{ rows: 2 }} />
            </Card>
          ))}
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
      <div ref={resultsRef}>
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
              dataSources={dataSources}
            />
          ))}
        </>
      )}

      {/* ── 搜索后无结果 ── */}
      {!loading && results && results.results.length === 0 && !error && (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <Empty
            description={
              <span>
                未找到匹配的岗位<br />
                <Text type="secondary" style={{ fontSize: 12 }}>请尝试更换查询词或调整搜索条件</Text>
              </span>
            }
          />
        </Card>
      )}
      </div>

      {/* ── 空状态（未搜索过） ── */}
      {!loading && !results && !error && !searched && (
        <Card style={{ textAlign: 'center', padding: 60 }}>
          <ExperimentOutlined style={{ fontSize: 48, color: '#bbb' }} />
          <Title level={4} type="secondary" style={{ marginTop: 16 }}>
            尚未生成融合结果
          </Title>
          <Paragraph type="secondary">
            {mode === 'bm25'
              ? '在搜索框中输入查询文本，点击「搜索并融合排序」查看真实 BM25 融合结果'
              : '调整权重配置，点击「生成 Mock 融合结果」查看排序和解释效果'}
          </Paragraph>
        </Card>
      )}
    </div>
  );
}
