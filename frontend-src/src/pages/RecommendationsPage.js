import React from 'react';
import {
  Card,
  Typography,
  Button,
  Space,
  Row,
  Col,
  Alert,
  Spin,
  Empty,
  Upload,
  message,
  Tag,
} from 'antd';
import {
  UploadOutlined,
  CheckCircleOutlined,
  ExperimentOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation } from 'react-query';
import { searchJobsWithResume, uploadResume } from '../services/api';
import { recommendJobs } from '../services/fusionApi';
import { useCandidate } from '../contexts/CandidateContext';
import FusionScoreCard from '../components/FusionScoreCard';

const { Title, Paragraph, Text } = Typography;

/**
 * 统一推荐入口：POST /api/v1/fusion/recommend
 * sample 模式下后端内部完成 BM25 → Semantic → KG → Fusion 全链路。
 */
const SAMPLE_CANDIDATE_ID = 'resume_000001_exp00_0';
const SAMPLE_CANDIDATE_SKILLS = ['LLM', 'Megatron', 'PPO', 'LoRA', 'C/C++', 'PyTorch'];

// 五个因子均来自后端真实计算（sample 链路），用于 FusionScoreCard 数据来源标注
const REAL_FACTORS = {
  bm25_score: 'real',
  semantic_score: 'real',
  skill_coverage: 'real',
  job_family_match: 'real',
  graph_relatedness: 'real',
};

/** 从简历画像构建查询文本（与 talentApi.buildCandidateQuery 保持一致） */
const buildCandidateQuery = (candidateProfile) => {
  const candidate = candidateProfile?.candidate || {};
  const skills = candidateProfile?.extracted_skills?.length
    ? candidateProfile.extracted_skills
    : (candidate.skills || []).map((skill) => skill.name).filter(Boolean);
  const experience = (candidate.experience || [])
    .flatMap((item) => [item.position, item.description])
    .filter(Boolean);
  return [candidate.target_job_family, candidate.summary, ...skills, ...experience, candidateProfile?.experience_summary]
    .filter(Boolean)
    .join(' ')
    .trim();
};

/** Convert the legacy JobSearchResult job contract to the card contract. */
const normalizeUploadedJob = (job) => {
  const metadata = job.search_metadata || {};
  const explanation = metadata.match_explanation || {};
  const components = explanation.components || {};
  const skillDetails = components['Skill Match']?.details || {};
  const componentScore = (name) => Number(components[name]?.score || 0);

  return {
    job_id: job.id,
    final_score: Number(job.rerank_score || 0),
    score_breakdown: {
      skill_coverage: componentScore('Skill Match'),
      semantic_score: componentScore('Job Description Match'),
    },
    explanation: {
      reason: skillDetails.matched_skills?.length
        ? `匹配技能：${skillDetails.matched_skills.join('、')}`
        : '已根据简历画像完成岗位匹配。',
      matched_skills: skillDetails.matched_skills || [],
      missing_skills: skillDetails.missing_skills || [],
    },
    meta: {
      title: job.title,
      company: job.company_name,
      standard_job: job.job_family,
      location: job.location?.city,
      salary: job.salary
        ? `${job.salary.min_salary || ''}-${job.salary.max_salary || ''}`
        : '',
    },
  };
};

const RecommendationsPage = () => {
  const { candidateProfile, resumeFile, updateCandidateProfile, updateResumeFile } = useCandidate();

  const uploadMutation = useMutation(uploadResume, {
    onSuccess: (data) => {
      updateCandidateProfile(data);
      message.success('简历解析完成，正在生成推荐…');
    },
    onError: (error) => {
      message.error(`简历解析失败：${error.message}`);
    },
  });

  const { data: recommendations = [], isLoading, error, refetch } = useQuery(
    ['recommendations', candidateProfile?.candidate?.id, candidateProfile?.candidate?.name],
    async () => {
      if (!candidateProfile) return [];
      const queryText = buildCandidateQuery(candidateProfile);
      // An uploaded resume must use the real resume-aware endpoint. The
      // sample Fusion endpoint remains available only for the built-in demo
      // candidate, so an upload can never silently render sample results.
      if (resumeFile) {
        const result = await searchJobsWithResume(
          {
            query: queryText || candidateProfile.candidate?.target_job_family || 'software engineer',
            page: 1,
            page_size: 10,
            limit: 10,
          },
          resumeFile,
          'auto'
        );
        return (result.jobs || []).map(normalizeUploadedJob);
      }

      const result = await recommendJobs({
        candidateId: candidateProfile.candidate?.id,
        queryText,
        topK: 10,
        mode: 'sample',
      });
      return result.results || [];
    },
    {
      enabled: !!candidateProfile,
      retry: 1,
    }
  );

  const handleResumeUpload = (file) => {
    const isPdf = file.type === 'application/pdf';
    const isDoc =
      file.type === 'application/msword' ||
      file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    if (!isPdf && !isDoc) {
      message.error('仅支持 PDF 或 DOC/DOCX 格式');
      return false;
    }
    if (file.size / 1024 / 1024 >= 10) {
      message.error('文件不能超过 10MB');
      return false;
    }
    updateResumeFile(file);
    uploadMutation.mutate(file);
    return false;
  };

  /** 加载示例候选人：匹配 sample_pack 标准候选人，展示完整技能匹配效果 */
  const useSampleCandidate = () => {
    updateCandidateProfile({
      candidate: {
        id: SAMPLE_CANDIDATE_ID,
        name: '示例候选人（大模型算法工程师）',
        skills: [],
        experience: [],
        target_job_family: '大模型算法工程师',
      },
      extracted_skills: SAMPLE_CANDIDATE_SKILLS,
      experience_summary: '示例候选人：大模型算法方向，熟悉 LLM 训练与推理优化。',
    });
    message.info('已加载示例候选人，正在生成推荐…');
  };

  const candidateName = candidateProfile?.candidate?.name;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      <Title level={2} style={{ textAlign: 'center', marginBottom: '8px' }}>
        💡 岗位推荐
      </Title>
      <Paragraph style={{ textAlign: 'center', marginBottom: '24px' }}>
        上传简历，基于统一融合推荐链路（BM25 → 语义重排 → 知识图谱 → 分层融合排序）生成个性化岗位推荐。
      </Paragraph>

      {!candidateProfile ? (
        <Card style={{ marginBottom: '24px' }}>
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <UploadOutlined style={{ fontSize: '48px', color: '#1890ff', marginBottom: '16px' }} />
            <Title level={3}>上传简历开始推荐</Title>
            <Paragraph style={{ marginBottom: '24px' }}>
              上传简历后，系统将解析技能与经历，并与岗位库进行融合匹配。
            </Paragraph>
            <Space direction="vertical" size="middle">
              <Upload beforeUpload={handleResumeUpload} showUploadList={false} accept=".pdf,.doc,.docx">
                <Button type="primary" size="large" icon={<UploadOutlined />} loading={uploadMutation.isLoading}>
                  上传简历
                </Button>
              </Upload>
              <Button icon={<ExperimentOutlined />} onClick={useSampleCandidate}>
                使用示例候选人（大模型算法工程师）
              </Button>
            </Space>
          </div>
        </Card>
      ) : (
        <Card style={{ marginBottom: '24px' }}>
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <CheckCircleOutlined style={{ fontSize: '24px', color: '#52c41a', marginBottom: '8px' }} />
            <Title level={4} style={{ color: '#52c41a', marginBottom: '8px' }}>
              简历画像已建立
            </Title>
            <Paragraph style={{ marginBottom: '12px' }}>
              当前候选人：<strong>{candidateName}</strong>，已识别{' '}
              <Tag color="blue">
                {(candidateProfile.extracted_skills || candidateProfile.candidate?.skills || []).length} 项技能
              </Tag>
            </Paragraph>
            <Space>
              <Upload beforeUpload={handleResumeUpload} showUploadList={false} accept=".pdf,.doc,.docx">
                <Button size="small" icon={<UploadOutlined />} loading={uploadMutation.isLoading}>
                  更换简历
                </Button>
              </Upload>
              <Button size="small" icon={<ReloadOutlined />} loading={isLoading} onClick={() => refetch()}>
                重新推荐
              </Button>
              <Button size="small" icon={<ExperimentOutlined />} onClick={useSampleCandidate}>
                加载示例候选人
              </Button>
            </Space>
          </div>
        </Card>
      )}

      {uploadMutation.isLoading && (
        <Card>
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <Title level={4} style={{ marginTop: '16px' }}>正在解析简历…</Title>
            <Paragraph>提取技能、经历与教育背景。</Paragraph>
          </div>
        </Card>
      )}

      {isLoading && candidateProfile && (
        <Card>
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <Title level={4} style={{ marginTop: '16px' }}>正在生成岗位推荐…</Title>
            <Paragraph>执行 BM25 召回、语义重排、知识图谱差距分析与融合排序。</Paragraph>
          </div>
        </Card>
      )}

      {error && (
        <Alert
          message="推荐加载失败"
          description={error.message || '推荐服务暂不可用，请检查后端后重试。'}
          type="error"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {!isLoading && !error && candidateProfile && recommendations.length > 0 && (
        <div>
          <div style={{ marginBottom: '16px', textAlign: 'center' }}>
            <Title level={3}>找到 {recommendations.length} 个推荐岗位</Title>
            <Paragraph>按融合最终得分排序，点击卡片可展开五因子得分明细。</Paragraph>
          </div>
          {recommendations.map((result, index) => (
            <FusionScoreCard
              key={result.job_id}
              result={result}
              rank={index + 1}
              dataSources={REAL_FACTORS}
            />
          ))}
        </div>
      )}

      {!isLoading && !error && candidateProfile && recommendations.length === 0 && (
        <Card>
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Empty description="暂无匹配岗位" />
            <Paragraph style={{ marginTop: '12px' }}>
              当前简历未匹配到岗位，可尝试更换简历或加载示例候选人。
            </Paragraph>
            <Button icon={<ExperimentOutlined />} onClick={useSampleCandidate}>
              加载示例候选人
            </Button>
          </div>
        </Card>
      )}

      <Row justify="center" style={{ marginTop: '16px' }}>
        <Col>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {resumeFile
              ? '数据来源：POST /api/v1/jobs/search-with-resume（自动简历解析）'
              : '数据来源：POST /api/v1/fusion/recommend（示例候选人 sample 链路）'}
          </Text>
        </Col>
      </Row>
    </div>
  );
};

export default RecommendationsPage;
