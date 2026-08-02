/**
 * Mock 融合数据 — 前端独立开发用
 *
 * 模拟 /api/v1/fusion/rank 的返回结果，
 * 在后端不可用或开发时直接使用。
 */

const MOCK_TITLES = [
  'Senior Software Engineer',
  'Full Stack Developer',
  'Backend Engineer',
  'Frontend Developer',
  'DevOps Engineer',
  'Machine Learning Engineer',
  'Data Scientist',
  'Product Manager',
  'Software Architect',
  'Mobile Developer',
  'Cloud Engineer',
  'Security Engineer',
  'QA Engineer',
  'Technical Lead',
  'Engineering Manager',
  'Research Scientist',
  'Data Engineer',
  'Site Reliability Engineer',
  'Systems Engineer',
  'Embedded Software Engineer',
];

const MOCK_COMPANIES = [
  'Google', 'Microsoft', 'Amazon', 'Apple', 'Meta', 'Netflix',
  'Tesla', 'Uber', 'Airbnb', 'Stripe', 'Salesforce', 'Adobe',
  'Oracle', 'IBM', 'Intel', 'NVIDIA', 'Spotify', 'LinkedIn',
  'GitHub', 'Shopify',
];

function seededRandom(seed) {
  let s = seed || 42;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/**
 * 生成 Mock 融合结果，模拟后端 /mock-rank 的返回
 */
export function generateMockFusionResults(queryId = 'mock_resume_001', numJobs = 20, seed = 42, customWeights = null) {
  const rand = seededRandom(seed);
  const DEFAULT_WEIGHTS = {
    bm25: 0.15,
    semantic: 0.25,
    skill_coverage: 0.30,
    job_family: 0.15,
    graph: 0.15,
  };
  const activeWeights = customWeights || DEFAULT_WEIGHTS;

  const jobs = [];
  for (let i = 0; i < numJobs; i++) {
    const tierRoll = rand();
    const tier = tierRoll < 0.25 ? 'high' : tierRoll < 0.75 ? 'medium' : 'low';

    let bm25, semantic, skillCoverage, jobFamily, graph, missingCount;
    if (tier === 'high') {
      bm25 = 0.70 + rand() * 0.28;
      semantic = 0.72 + rand() * 0.24;
      skillCoverage = 0.65 + rand() * 0.30;
      jobFamily = rand() < 0.7 ? 1.0 : 0.60 + rand() * 0.35;
      graph = 0.65 + rand() * 0.27;
      missingCount = rand() < 0.5 ? 0 : 1;
    } else if (tier === 'medium') {
      bm25 = 0.40 + rand() * 0.35;
      semantic = 0.45 + rand() * 0.33;
      skillCoverage = 0.35 + rand() * 0.35;
      jobFamily = rand() < 0.4 ? 1.0 : 0.30 + rand() * 0.40;
      graph = 0.35 + rand() * 0.37;
      missingCount = 1 + Math.floor(rand() * 3);
    } else {
      bm25 = 0.10 + rand() * 0.40;
      semantic = 0.15 + rand() * 0.33;
      skillCoverage = 0.10 + rand() * 0.30;
      jobFamily = 0.10 + rand() * 0.45;
      graph = 0.10 + rand() * 0.35;
      missingCount = 2 + Math.floor(rand() * 4);
    }

    const skillPool = [
      'Python', 'JavaScript', 'React', 'Node.js', 'AWS', 'Docker',
      'Kubernetes', 'TypeScript', 'Java', 'Go', 'C++', 'SQL',
      'MongoDB', 'PostgreSQL', 'TensorFlow', 'PyTorch', 'Machine Learning',
      'CI/CD', 'Git', 'REST APIs', 'GraphQL', 'Microservices',
      'System Design', 'Agile', 'Scrum', 'Redis', 'Kafka', 'Spark',
    ];
    const missing = [];
    const usedIdx = new Set();
    while (missing.length < missingCount) {
      const idx = Math.floor(rand() * skillPool.length);
      if (!usedIdx.has(idx)) {
        usedIdx.add(idx);
        missing.push(skillPool[idx]);
      }
    }

    // 融合计算（使用传入的自定义权重）
    const finalScore = (
      bm25 * activeWeights.bm25 +
      semantic * activeWeights.semantic +
      skillCoverage * activeWeights.skill_coverage +
      jobFamily * activeWeights.job_family +
      graph * activeWeights.graph
    );

    jobs.push({
      query_id: queryId,
      job_id: `mock_job_${String(i + 1).padStart(3, '0')}`,
      final_score: Math.round(finalScore * 10000) / 10000,
      rank: 0, // 下面排序后设置
      score_breakdown: {
        bm25_score: Math.round(bm25 * 100) / 100,
        semantic_score: Math.round(semantic * 100) / 100,
        skill_coverage: Math.round(skillCoverage * 100) / 100,
        job_family_match: Math.round(jobFamily * 100) / 100,
        graph_relatedness: Math.round(graph * 100) / 100,
      },
      explanation: null, // 下面生成
      meta: {
        title: MOCK_TITLES[i % MOCK_TITLES.length],
        company: MOCK_COMPANIES[Math.floor(rand() * MOCK_COMPANIES.length)],
      },
    });
  }

  // 排序
  jobs.sort((a, b) => b.final_score - a.final_score);
  const matchedPool = ['Python', 'SQL', 'JavaScript', 'React', 'Docker', 'Git', 'REST APIs'];
  jobs.forEach((job, i) => {
    job.rank = i + 1;
    const matchedCount = Math.max(1, Math.floor((1 - job.final_score) * matchedPool.length));
    const matched = matchedPool.slice(0, matchedCount);
    // 缺失技能 = 排除已匹配的技能
    const allSkills = ['PyTorch', 'TensorFlow', 'Kubernetes', 'AWS', 'Machine Learning', 'System Design', 'CI/CD', 'Redis'];
    const missing = allSkills.slice(0, Math.max(1, Math.floor((1 - job.final_score) * allSkills.length)));
    job.explanation = generateExplanation(job, matched, missing);
  });

  return {
    query_id: queryId,
    results: jobs,
    weights_used: activeWeights,
  };
}

/**
 * 基于模板生成中文解释（分工3 Phase 3 格式）
 * @returns {{matched_skills: string[], missing_skills: string[], reason: string}}
 */
function generateExplanation(job, matchedSkills, missingSkills) {
  const { score_breakdown: sb } = job;
  const factorLabels = {
    bm25_score: '关键词匹配',
    semantic_score: '语义相似度',
    skill_coverage: '技能覆盖',
    job_family_match: '岗位大类匹配',
    graph_relatedness: '知识图谱关联',
  };

  const strengths = Object.entries(sb)
    .filter(([, s]) => s >= 0.7)
    .map(([k, s]) => `${factorLabels[k] || k}（${Math.round(s * 100)}%）`);
  const weaknesses = Object.entries(sb)
    .filter(([, s]) => s < 0.4)
    .map(([k, s]) => `${factorLabels[k] || k}（${Math.round(s * 100)}%）`);

  const parts = [];

  if (job.final_score >= 0.75) parts.push('该岗位与您的简历整体匹配度很高');
  else if (job.final_score >= 0.55) parts.push('该岗位与您的简历匹配度良好');
  else if (job.final_score >= 0.35) parts.push('该岗位与您的简历有一定匹配度');
  else parts.push('该岗位与您的简历匹配度较低');

  if (strengths.length) parts.push(`强项：${strengths.join('、')}`);
  else parts.push('各维度均无特别突出的优势项');

  if (weaknesses.length) parts.push(`弱项：${weaknesses.join('、')}`);

  if (missingSkills && missingSkills.length) {
    parts.push(`建议补充 ${missingSkills.join('、')} 等相关技能，可显著提升匹配度`);
  } else {
    parts.push('该岗位是您的良好选择，建议尽快投递');
  }

  return {
    matched_skills: matchedSkills || [],
    missing_skills: missingSkills || [],
    reason: parts.join('。') + '。',
  };
}
