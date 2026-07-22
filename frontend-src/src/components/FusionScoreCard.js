import React, { useState } from 'react';
import {
  Card,
  Progress,
  Tag,
  Typography,
  Row,
  Col,
  Descriptions,
  Collapse,
  Tooltip,
} from 'antd';
import {
  TrophyOutlined,
  StarOutlined,
  InfoCircleOutlined,
  CaretUpOutlined,
  CaretDownOutlined,
  MinusOutlined,
} from '@ant-design/icons';
import './FusionScoreCard.css';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

// ── 因子配置 ────────────────────────────────────────────────────
const FACTOR_CONFIG = {
  bm25: {
    label: '关键词匹配',
    icon: '🔤',
    color: '#1890ff',
    description: '基于 BM25 算法的关键词匹配得分，衡量查询词在岗位描述中的出现频率和重要性',
  },
  semantic: {
    label: '语义相似度',
    icon: '🧠',
    color: '#722ed1',
    description: '基于向量嵌入的语义相似度，理解查询意图与岗位描述的深层语义匹配',
  },
  skill_coverage: {
    label: '技能覆盖',
    icon: '🎯',
    color: '#52c41a',
    description: '您的技能集覆盖岗位要求的比例，权重最高',
  },
  job_family: {
    label: '岗位大类',
    icon: '🏢',
    color: '#fa8c16',
    description: '岗位所属类别与目标岗位类别的匹配（1.0 = 完全匹配，0.0 = 不同类别）',
  },
  graph: {
    label: '知识图谱',
    icon: '🔗',
    color: '#eb2f96',
    description: '基于知识图谱的关联度，反映您与岗位在技能关系网络中的距离',
  },
};

// ── 分数颜色 ────────────────────────────────────────────────────
function getScoreColor(score) {
  if (score >= 0.75) return '#52c41a';
  if (score >= 0.55) return '#1890ff';
  if (score >= 0.35) return '#faad14';
  return '#ff4d4f';
}

function getScoreLabel(score) {
  if (score >= 0.75) return '优秀';
  if (score >= 0.55) return '良好';
  if (score >= 0.35) return '一般';
  return '较低';
}

function getRankBadge(rank) {
  if (rank === 1) return { color: '#faad14', icon: <TrophyOutlined />, text: 'TOP 1' };
  if (rank <= 3) return { color: '#1890ff', icon: <StarOutlined />, text: `TOP ${rank}` };
  if (rank <= 5) return { color: '#52c41a', icon: <StarOutlined />, text: `#${rank}` };
  return { color: '#8c8c8c', icon: null, text: `#${rank}` };
}

// ── 趋势指示器 ──────────────────────────────────────────────────
function TrendIndicator({ score }) {
  if (score >= 0.7) return <CaretUpOutlined style={{ color: '#52c41a', fontSize: 12 }} />;
  if (score < 0.4) return <CaretDownOutlined style={{ color: '#ff4d4f', fontSize: 12 }} />;
  return <MinusOutlined style={{ color: '#faad14', fontSize: 12 }} />;
}

// ── 组件主体 ────────────────────────────────────────────────────
export default function FusionScoreCard({ result, rank, showRank = true }) {
  const [expanded, setExpanded] = useState(false);

  if (!result) return null;

  const {
    final_score: finalScore,
    score_breakdown: breakdown,
    explanation,
    meta = {},
  } = result;

  const scoreColor = getScoreColor(finalScore);
  const scoreLabel = getScoreLabel(finalScore);
  const rankBadge = getRankBadge(rank || result.rank);
  const scorePercent = Math.round(finalScore * 100);

  // breakdown 中的 key -> Factor config
  const factorEntries = breakdown
    ? Object.entries(breakdown).map(([key, score]) => ({
        key,
        score,
        config: FACTOR_CONFIG[key] || { label: key, icon: '📊', color: '#8c8c8c', description: '' },
      }))
    : [];

  // 按分数排序
  factorEntries.sort((a, b) => b.score - a.score);

  return (
    <Card
      className={`fusion-score-card ${expanded ? 'expanded' : ''}`}
      hoverable
      onClick={() => setExpanded(!expanded)}
      style={{
        borderLeft: `4px solid ${scoreColor}`,
        marginBottom: 16,
        transition: 'all 0.3s',
      }}
    >
      {/* ── 头部：排名 + 标题 + 得分 ── */}
      <Row align="middle" gutter={16}>
        {/* 排名 */}
        {showRank && (
          <Col flex="60px" style={{ textAlign: 'center' }}>
            <Tag
              color={rankBadge.color}
              style={{ fontSize: 14, padding: '2px 8px', borderRadius: 12 }}
            >
              {rankBadge.icon} {rankBadge.text}
            </Tag>
          </Col>
        )}

        {/* 岗位信息 */}
        <Col flex="auto">
          <Title level={5} style={{ margin: 0 }}>
            {meta.title || `Job ${result.job_id}`}
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            {meta.company || ''}
          </Text>
        </Col>

        {/* 最终得分 */}
        <Col flex="120px" style={{ textAlign: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Progress
              type="circle"
              percent={scorePercent}
              size={72}
              strokeColor={scoreColor}
              format={() => (
                <span style={{ fontSize: 18, fontWeight: 700, color: scoreColor }}>
                  {scorePercent}%
                </span>
              )}
            />
          </div>
          <Tag color={scoreColor} style={{ marginTop: 4 }}>
            {scoreLabel}
          </Tag>
        </Col>
      </Row>

      {/* ── 解释文本 ── */}
      {explanation && (
        <Paragraph
          style={{
            marginTop: 12,
            padding: '10px 14px',
            background: '#fafafa',
            borderRadius: 8,
            fontSize: 13,
            lineHeight: 1.8,
          }}
        >
          {explanation}
        </Paragraph>
      )}

      {/* ── 展开：分项得分详情 ── */}
      {expanded && (
        <div className="fusion-score-detail" style={{ marginTop: 16 }}>
          <Text strong style={{ fontSize: 14, marginBottom: 12, display: 'block' }}>
            📊 得分明细
          </Text>
          {factorEntries.map(({ key, score, config }) => (
            <Row
              key={key}
              align="middle"
              gutter={12}
              style={{ marginBottom: 10, padding: '6px 8px', borderRadius: 6, background: '#f9f9f9' }}
            >
              <Col flex="24px" style={{ textAlign: 'center', fontSize: 18 }}>
                {config.icon}
              </Col>
              <Col flex="100px">
                <Tooltip title={config.description}>
                  <Text style={{ fontSize: 13 }}>
                    {config.label} <InfoCircleOutlined style={{ fontSize: 10, color: '#bbb' }} />
                  </Text>
                </Tooltip>
              </Col>
              <Col flex="auto">
                <Progress
                  percent={Math.round(score * 100)}
                  size="small"
                  strokeColor={config.color}
                  showInfo={false}
                />
              </Col>
              <Col flex="50px" style={{ textAlign: 'right' }}>
                <Text strong style={{ color: getScoreColor(score), fontSize: 14 }}>
                  {Math.round(score * 100)}%
                </Text>
              </Col>
              <Col flex="20px">
                <TrendIndicator score={score} />
              </Col>
            </Row>
          ))}

          {/* ── 缺失技能 ── */}
          {result.missing_skills && result.missing_skills.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Text strong style={{ fontSize: 13 }}>🔍 缺失技能：</Text>
              {result.missing_skills.map((skill) => (
                <Tag key={skill} color="error" style={{ marginLeft: 4, marginTop: 4 }}>
                  {skill}
                </Tag>
              ))}
            </div>
          )}

          {/* ── 证据路径 ── */}
          {result.evidence_paths && result.evidence_paths.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text strong style={{ fontSize: 13 }}>🔗 知识图谱证据路径：</Text>
              {result.evidence_paths.map((path, i) => (
                <Text key={i} code style={{ display: 'block', marginTop: 4, fontSize: 12 }}>
                  {path}
                </Text>
              ))}
            </div>
          )}
        </div>
      )}

      <Text
        type="secondary"
        style={{ fontSize: 11, display: 'block', textAlign: 'center', marginTop: 8 }}
      >
        {expanded ? '点击收起' : '点击展开查看详情'}
      </Text>
    </Card>
  );
}
