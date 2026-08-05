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
import { getMockRankedResults, rankFromQuery, getLayeredWeights, updateLayeredWeights, resetWeights, loadFusionResults } from '../services/fusionApi';
import './FusionDemoPage.css';

const { Title, Text, Paragraph } = Typography;

// ── 分层因子配置（第三阶段 v2）──────────────────────────────────────
const RELEVANCE_FACTORS = [
  { key: 'relevance_bm25', label: '关键词匹配 (BM25)', icon: '🔤' },
  { key: 'relevance_semantic', label: '语义相似度', icon: '🧠' },
];
const ABILITY_FACTORS = [
  { key: 'ability_skill', label: '技能覆盖', icon: '🎯' },
  { key: 'ability_graph', label: '知识图谱关联', icon: '🔗' },
];

const FACTOR_BREAKDOWN_MAP = {
  relevance_bm25: 'bm25_score',
  relevance_semantic: 'semantic_score',
  ability_skill: 'skill_coverage',
  ability_graph: 'graph_relatedness',
  job_family: 'job_family_match',
};

const DEFAULT_WEIGHTS = {
  relevance_bm25: 0.4, relevance_semantic: 0.6,
  ability_skill: 0.7, ability_graph: 0.3,
  relevance_base: 0.7, ability_multiplier: 0.3,
  use_family_gate: false,
};

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

  // ── 模式切换（Mock / 真实BM25 / 离线融合）───────────────────
  const [mode, setMode] = useState('bm25');  // 'mock' | 'bm25' | 'offline'
  const [queryText, setQueryText] = useState('');
  const [bm25Size, setBm25Size] = useState(20);
  const [searched, setSearched] = useState(false);  // 是否已搜索过
  const [offlineQueryIds, setOfflineQueryIds] = useState([]);
  const [offlineQueryId, setOfflineQueryId] = useState(null);

  const resultsRef = useRef(null);  // 结果区域 ref，用于自动滚动

  // ── 数据来源标注 ────────────────────────────────────────────
  const dataSources =
    mode === 'offline'
      ? { bm25_score: 'real', semantic_score: 'real', skill_coverage: 'real', job_family_match: 'real', graph_relatedness: 'real' }
      : mode === 'bm25'
        ? { bm25_score: 'real', semantic_score: 'pending', skill_coverage: 'pending', job_family_match: 'pending', graph_relatedness: 'pending' }
        : { bm25_score: 'mock', semantic_score: 'mock', skill_coverage: 'mock', job_family_match: 'mock', graph_relatedness: 'mock' };
  // job_family_match 数据来源（独立标注，用于门控）
  const familySource = mode === 'offline' ? 'real' : mode === 'bm25' ? 'pending' : 'mock';

  // ── BM25-Only 快捷权重 ─────────────────────────────────────
  const bm25OnlyWeights = {
    relevance_bm25: 1.0, relevance_semantic: 0.0,
    ability_skill: 0.5, ability_graph: 0.5,
    relevance_base: 1.0, ability_multiplier: 0.0,
    use_family_gate: false,
  };

  // ── 加载权重 ───────────────────────────────────────────────
  useEffect(() => {
    loadServerWeights();
  }, []);

  const loadServerWeights = async () => {
    try {
      const data = await getLayeredWeights();
      const w = data.weights;
      setServerWeights({
        relevance_bm25: w.relevance_bm25, relevance_semantic: w.relevance_semantic,
        ability_skill: w.ability_skill, ability_graph: w.ability_graph,
        relevance_base: w.relevance_base, ability_multiplier: w.ability_multiplier,
        use_family_gate: (w.family_discount || 1.0) < 0.95,
      });
    } catch {
      // 后端不可用，使用默认值
    }
  };

  // ── 执行 Mock 融合排序 ─────────────────────────────────────
  // ── 将前端权重转为 API 分层格式 ────────────────────────────
  const toLayeredApi = (w) => ({
    relevance_bm25: w.relevance_bm25,
    relevance_semantic: w.relevance_semantic,
    ability_skill: w.ability_skill,
    ability_graph: w.ability_graph,
    relevance_base: w.relevance_base,
    ability_multiplier: w.ability_multiplier,
    family_discount: w.use_family_gate ? 0.85 : 1.0,
  });

  const handleMockRank = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const activeWeights = useServerWeights ? serverWeights || DEFAULT_WEIGHTS : weights;
      const data = await getMockRankedResults(
        queryId, numJobs, seed, null, toLayeredApi(activeWeights)
      );
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

  // ── 加载离线融合结果 ─────────────────────────────────────
  const handleOfflineLoad = useCallback(async () => {
    if (!offlineQueryId) {
      message.warning('请先选择一个简历 ID');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await loadFusionResults(offlineQueryId, 'full');
      if (data.results && data.results.length > 0) {
        setResults({ query_id: data.query_id, results: data.results, weights_used: DEFAULT_WEIGHTS });
        setSearched(true);
        message.success(`加载了 ${data.count} 条离线融合结果`);
        setTimeout(() => {
          resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
      } else {
        setResults({ query_id: offlineQueryId, results: [], weights_used: DEFAULT_WEIGHTS });
        message.info('该简历暂无离线融合结果');
      }
    } catch (err) {
      setError(err.message);
      message.error('加载失败: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [offlineQueryId]);

  // ── 切换到离线模式时加载 query_id 列表 ────────────────────
  useEffect(() => {
    if (mode === 'offline') {
      loadFusionResults().then((data) => {
        if (data.query_ids && data.query_ids.length > 0) {
          setOfflineQueryIds(data.query_ids);
          if (!offlineQueryId && data.query_ids.length > 0) {
            setOfflineQueryId(data.query_ids[0]);
          }
        }
      }).catch(() => {});
    }
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

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
        layeredWeights: toLayeredApi(activeWeights),
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

  // ── 更新服务端分层权重 ────────────────────────────────────
  const handleUpdateServerWeights = async () => {
    try {
      const lw = {
        relevance_bm25: weights.relevance_bm25,
        relevance_semantic: weights.relevance_semantic,
        ability_skill: weights.ability_skill,
        ability_graph: weights.ability_graph,
        relevance_base: weights.relevance_base,
        ability_multiplier: weights.ability_multiplier,
        family_discount: weights.use_family_gate ? 0.85 : 1.0,
      };
      await updateLayeredWeights(lw);
      message.success('分层权重已推送到服务端');
      setServerWeights({ ...weights });
    } catch (err) {
      message.error('推送失败: ' + err.message);
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

  // 验证分层权重（两组各自求和为 1）
  const relSum = weights.relevance_bm25 + weights.relevance_semantic;
  const abSum = weights.ability_skill + weights.ability_graph;
  const relValid = Math.abs(relSum - 1.0) < 0.005;
  const abValid = Math.abs(abSum - 1.0) < 0.005;
  const weightsValid = relValid && abValid;

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
          第三阶段 v2：分层融合。相关性（BM25+Semantic）主导排序，能力（Skill+Graph）做候选集内调制，岗位族做门控。
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
            { label: <><BarChartOutlined /> 离线融合结果</>, value: 'offline' },
            { label: <><ApiOutlined /> Demo 演示</>, value: 'mock' },
          ]}
          block
          style={{ marginBottom: 16 }}
        />

        {/* 当前模式提示 Banner */}
        {mode === 'offline' ? (
          <Alert
            message="离线融合结果模式"
            description="从预计算的融合排序结果中加载，包含完整的 5 因子得分（BM25 + Semantic + Skill + JobFamily + Graph）。选择简历 ID 后点击加载即可查看。"
            type="success"
            showIcon
            icon={<BarChartOutlined />}
            style={{ marginBottom: 16 }}
          />
        ) : mode === 'bm25' ? (
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
            description="当前使用本地随机生成的模拟数据展示 UI 效果。所有分数均为随机值，不代表真实算法结果。"
            type="warning"
            showIcon
            icon={<ApiOutlined />}
            style={{ marginBottom: 16 }}
          />
        )}
      </div>

      {/* ── 分层权重配置面板（第三阶段 v2）── */}
      <Card
        className="weights-panel"
        title={
          <Space>
            <SettingOutlined />
            <span>分层融合权重</span>
            {!weightsValid && (
              <Tag color="error">
                {!relValid && `相关性: ${relSum.toFixed(2)} `}
                {!abValid && `能力: ${abSum.toFixed(2)}`}
                （需各为 1.00）
              </Tag>
            )}
            {weightsValid && <Tag color="success">✓</Tag>}
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
            <Button size="small" onClick={handleResetWeights}>恢复默认</Button>
            {!useServerWeights && (
              <Button size="small" type="primary" onClick={handleUpdateServerWeights} disabled={!weightsValid}>
                推送到服务端
              </Button>
            )}
          </Space>
        }
        style={{ marginBottom: 20 }}
      >
        {/* 相关性权重组 */}
        <Text strong style={{ fontSize: 13 }}>📊 相关性得分 = w₁ × BM25 + w₂ × Semantic</Text>
        <Row gutter={[16, 8]} style={{ marginTop: 4, marginBottom: 12 }}>
          {RELEVANCE_FACTORS.map((f) => (
            <Col key={f.key} span={12}>
              <Text style={{ fontSize: 12 }}>{f.icon} {f.label}</Text>
              <Row align="middle" gutter={8}>
                <Col flex="auto">
                  <Slider min={0} max={1} step={0.05} value={weights[f.key]}
                    onChange={(v) => handleWeightChange(f.key, v)} disabled={useServerWeights} />
                </Col>
                <Col flex="50px">
                  <InputNumber size="small" min={0} max={1} step={0.05}
                    value={weights[f.key]} onChange={(v) => handleWeightChange(f.key, v || 0)}
                    disabled={useServerWeights} style={{ width: 50 }} />
                </Col>
              </Row>
            </Col>
          ))}
        </Row>

        <Divider style={{ margin: '8px 0' }} />

        {/* 能力权重组 */}
        <Text strong style={{ fontSize: 13 }}>🎯 能力得分 = w₁ × Skill + w₂ × Graph（候选集内归一化）</Text>
        <Row gutter={[16, 8]} style={{ marginTop: 4, marginBottom: 12 }}>
          {ABILITY_FACTORS.map((f) => (
            <Col key={f.key} span={12}>
              <Text style={{ fontSize: 12 }}>{f.icon} {f.label}</Text>
              <Row align="middle" gutter={8}>
                <Col flex="auto">
                  <Slider min={0} max={1} step={0.05} value={weights[f.key]}
                    onChange={(v) => handleWeightChange(f.key, v)} disabled={useServerWeights} />
                </Col>
                <Col flex="50px">
                  <InputNumber size="small" min={0} max={1} step={0.05}
                    value={weights[f.key]} onChange={(v) => handleWeightChange(f.key, v || 0)}
                    disabled={useServerWeights} style={{ width: 50 }} />
                </Col>
              </Row>
            </Col>
          ))}
        </Row>

        <Divider style={{ margin: '8px 0' }} />

        {/* 公式参数 + 门控 */}
        <Text strong style={{ fontSize: 13 }}>公式：final = relevance × (base + multiplier × ability)</Text>
        <Row gutter={[16, 8]} style={{ marginTop: 4 }} align="middle">
          <Col span={8}>
            <Text style={{ fontSize: 12 }}>基础乘数 (base)</Text>
            <InputNumber size="small" min={0} max={1} step={0.05}
              value={weights.relevance_base}
              onChange={(v) => handleWeightChange('relevance_base', v || 0.7)}
              disabled={useServerWeights} style={{ width: '100%' }} />
          </Col>
          <Col span={8}>
            <Text style={{ fontSize: 12 }}>能力调制 (multiplier)</Text>
            <InputNumber size="small" min={0} max={1} step={0.05}
              value={weights.ability_multiplier}
              onChange={(v) => handleWeightChange('ability_multiplier', v || 0.3)}
              disabled={useServerWeights} style={{ width: '100%' }} />
          </Col>
          <Col span={8}>
            <Text style={{ fontSize: 12 }}>岗位族门控🏢</Text>
            <br />
            <Switch
              checkedChildren="降权" unCheckedChildren="忽略"
              checked={weights.use_family_gate}
              onChange={(v) => handleWeightChange('use_family_gate', v)}
              disabled={useServerWeights}
            />
            {familySource === 'real' && <Tag color="green" style={{ marginLeft: 4, fontSize: 10 }}>真实</Tag>}
            {familySource === 'pending' && <Tag color="blue" style={{ marginLeft: 4, fontSize: 10 }}>待接入</Tag>}
          </Col>
        </Row>
      </Card>

      {/* ── 控制栏 ── */}
      <Card style={{ marginBottom: 20 }}>
        {mode === 'offline' ? (
          /* ── 离线融合模式：选择 query_id ── */
          <Row align="middle" gutter={16} justify="space-between">
            <Col flex="auto">
              <Space>
                <Text strong>选择简历 ID：</Text>
                <select
                  value={offlineQueryId || ''}
                  onChange={(e) => setOfflineQueryId(e.target.value)}
                  style={{ padding: '4px 8px', fontSize: 14, borderRadius: 4, border: '1px solid #d9d9d9', minWidth: 280 }}
                >
                  <option value="">-- 选择 query_id --</option>
                  {offlineQueryIds.slice(0, 500).map((id) => (
                    <option key={id} value={id}>{id}</option>
                  ))}
                </select>
                <Text type="secondary">共 {offlineQueryIds.length} 个可用</Text>
              </Space>
            </Col>
            <Col>
              <Button
                type="primary"
                size="large"
                icon={<BarChartOutlined />}
                onClick={handleOfflineLoad}
                loading={loading}
                disabled={!offlineQueryId}
              >
                加载融合结果
              </Button>
            </Col>
          </Row>
        ) : mode === 'bm25' ? (
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
                  {results.weights_used.relevance_bm25 != null
                    ? `分层: rel(${results.weights_used.relevance_bm25}/${results.weights_used.relevance_semantic}) × (${results.weights_used.relevance_base}+${results.weights_used.ability_multiplier}×ability(${results.weights_used.ability_skill}/${results.weights_used.ability_graph}))`
                    : `权重: BM25=${results.weights_used.bm25} | Semantic=${results.weights_used.semantic} | Skill=${results.weights_used.skill_coverage} | Family=${results.weights_used.job_family} | Graph=${results.weights_used.graph}`}
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
            {mode === 'offline'
              ? '选择简历 ID，点击「加载融合结果」查看完整的 5 因子融合排序结果'
              : mode === 'bm25'
                ? '在搜索框中输入查询文本，点击「搜索并融合排序」查看真实 BM25 融合结果'
              : '调整权重配置，点击「生成 Mock 融合结果」查看排序和解释效果'}
          </Paragraph>
        </Card>
      )}
    </div>
  );
}
