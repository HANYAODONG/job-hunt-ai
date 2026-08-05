import React, { useState } from 'react';
import {
  Card,
  Progress,
  Tag,
  Typography,
  Row,
  Col,
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

// ── 因子配置（key 对应 ScoreBreakdown 字段名）─────────────────────
const FACTOR_CONFIG = {
  bm25_score: {
    label: '关键词匹配',
    icon: '🔤',
    color: '#1890ff',
    description: '基于 BM25 算法的关键词匹配得分，衡量查询词在岗位描述中的出现频率和重要性',
  },
  semantic_score: {
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
  job_family_match: {
    label: '岗位大类',
    icon: '🏢',
    color: '#fa8c16',
    description: '岗位所属类别与目标岗位类别的匹配（1.0 = 完全匹配，0.0 = 不同类别）',
  },
  graph_relatedness: {
    label: '知识图谱',
    icon: '🔗',
    color: '#eb2f96',
    description: '基于知识图谱的关联度，反映您与岗位在技能关系网络中的距离',
  },
};

// 兼容旧字段名映射
const FIELD_ALIASES = {
  bm25: 'bm25_score',
  semantic: 'semantic_score',
  job_family: 'job_family_match',
  graph: 'graph_relatedness',
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
export default function FusionScoreCard({ result, rank, showRank = true, dataSources = {} }) {
  const [expanded, setExpanded] = useState(false);

  if (!result) return null;

  const {
    final_score: finalScore,
    score_breakdown: breakdown,
    explanation,
    meta = {},
  } = result;

  // 兼容新旧 explanation 格式：新格式是对象 {reason, matched_skills, missing_skills}，旧格式是字符串
  const explanationText = typeof explanation === 'string' ? explanation : (explanation?.reason || '');
  const matchedSkills = explanation?.matched_skills || [];
  const missingSkills = explanation?.missing_skills || [];

  const scoreColor = getScoreColor(finalScore);
  const scoreLabel = getScoreLabel(finalScore);
  const rankBadge = getRankBadge(rank || result.rank);
  const scorePercent = Math.round(finalScore * 100);

  // breakdown 中的 key -> Factor config（兼容新旧字段名）
  const factorEntries = breakdown
    ? Object.entries(breakdown).map(([key, score]) => {
        const resolvedKey = FIELD_ALIASES[key] || key;
        return {
          key: resolvedKey,
          score,
          config: FACTOR_CONFIG[resolvedKey] || { label: key, icon: '📊', color: '#8c8c8c', description: '' },
          source: dataSources[resolvedKey] || dataSources[key] || 'mock',
        };
      })
    : [];

  // 按分数排序
  factorEntries.sort((a, b) => b.score - a.score);

  // 判断整体数据模式
  const hasRealData = Object.values(dataSources).some(s => s === 'real');
  const hasPendingData = Object.values(dataSources).some(s => s === 'pending');
  const allMock = !hasRealData && !hasPendingData;

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
            {!allMock && (
              <Tag
                color={hasRealData ? 'green' : 'blue'}
                style={{ marginLeft: 8, fontSize: 11 }}
              >
                {hasRealData ? '真实数据' : '部分真实'}
              </Tag>
            )}
            {allMock && (
              <Tag color="default" style={{ marginLeft: 8, fontSize: 11 }}>模拟数据</Tag>
            )}
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            {meta.company || meta.company_name || ''}
            {meta.standard_job && ` · ${meta.standard_job}`}
            {meta.location && ` · ${meta.location}`}
            {meta.salary && ` · ${meta.salary}`}
          </Text>
          {!meta.company && !meta.company_name && !meta.standard_job && !meta.location && !meta.salary && (
            <Text type="secondary" style={{ fontSize: 13, fontStyle: 'italic' }}>
              暂无详细岗位信息
            </Text>
          )}
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
      {explanationText && (
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
          {explanationText}
        </Paragraph>
      )}

      {/* ── 匹配技能 ── */}
      {matchedSkills.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <Text strong style={{ fontSize: 13 }}>✅ 匹配技能：</Text>
          {matchedSkills.map((skill) => (
            <Tag key={skill} color="green" style={{ marginLeft: 4, marginTop: 4 }}>
              {skill}
            </Tag>
          ))}
        </div>
      )}

      {/* ── 缺失技能 ── */}
      {missingSkills.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <Text strong style={{ fontSize: 13 }}>🔍 缺失技能：</Text>
          {missingSkills.map((skill) => (
            <Tag key={skill} color="error" style={{ marginLeft: 4, marginTop: 4 }}>
              {skill}
            </Tag>
          ))}
        </div>
      )}

      {/* ── 展开：分项得分详情 ── */}
      {expanded && (
        <div className="fusion-score-detail" style={{ marginTop: 16 }}>
          <Text strong style={{ fontSize: 14, marginBottom: 12, display: 'block' }}>
            📊 得分明细
          </Text>
          {factorEntries.map(({ key, score, config, source }) => (
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
                  strokeColor={source === 'real' ? config.color : '#d9d9d9'}
                  showInfo={false}
                />
              </Col>
              <Col flex="50px" style={{ textAlign: 'right' }}>
                <Text strong style={{ color: source === 'real' ? getScoreColor(score) : '#bbb', fontSize: 14 }}>
                  {Math.round(score * 100)}%
                </Text>
              </Col>
              <Col flex="20px">
                <TrendIndicator score={score} />
              </Col>
              <Col flex="56px" style={{ textAlign: 'right' }}>
                <Tag
                  color={source === 'real' ? 'green' : source === 'pending' ? 'blue' : 'default'}
                  style={{ fontSize: 10, margin: 0 }}
                >
                  {source === 'real' ? '✅ 真实' : source === 'pending' ? '🔸 待接入' : '🔸 模拟'}
                </Tag>
              </Col>
            </Row>
          ))}

          {/* ── 缺失技能（详情区，仅当列表较长时重复展示） ── */}
          {missingSkills.length > 5 && (
            <div style={{ marginTop: 12 }}>
              <Text strong style={{ fontSize: 13 }}>🔍 全部缺失技能：</Text>
              {missingSkills.map((skill) => (
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
