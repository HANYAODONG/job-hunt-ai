import React, { useRef, useState } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { Alert, App as AntdApp, Button, Skeleton, Tag, Upload } from 'antd';
import { ArrowRightOutlined, CheckCircleFilled, FilePdfOutlined, InboxOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import PageHeading from '../components/workbench/PageHeading';
import TechnicalInspector from '../components/workbench/TechnicalInspector';
import { diagnoseCandidate } from '../services/talentApi';
import { useNavigate } from 'react-router-dom';
import '../components/workbench/candidate-flow.css';

const gapActions = {
  'Agent 工作流': { title: '先完成一个可解释的 Agent 工作流', detail: '实现工具调用、记忆与失败回退，并保留一次完整运行记录作为项目证据。' },
  '模型评测': { title: '建立可复现的 RAG 质量评测', detail: '从 30 条真实问答开始，分别记录检索召回、答案忠实度和业务结果。' },
  '可观测性': { title: '为项目补齐运行证据与反馈闭环', detail: '记录链路耗时、调用成本和失败类型，让项目从演示原型走向可诊断系统。' },
};

const scoreLabels = {
  bm25: 'BM25 召回',
  semantic: '语义相关度',
  skill_coverage: '技能覆盖率',
  job_family: '岗位族匹配',
  graph: '图谱关联度',
};

gsap.registerPlugin(useGSAP);

const DiagnosisPage = () => {
  const { message } = AntdApp.useApp();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRoleId, setSelectedRoleId] = useState(null);
  const [selectedGap, setSelectedGap] = useState('Agent 工作流');
  const [roleContext] = useState(() => {
    try { return JSON.parse(localStorage.getItem('roleEvolutionContext') || 'null'); } catch { return null; }
  });
  const pageRef = useRef(null);

  useGSAP(() => {
    if (!analysis) return undefined;
    const motion = gsap.matchMedia();
    motion.add({ reduceMotion: '(prefers-reduced-motion: reduce)' }, ({ conditions }) => {
      gsap.fromTo('.diagnosis-report-workspace', {
        autoAlpha: conditions.reduceMotion ? 1 : 0,
        y: conditions.reduceMotion ? 0 : 8,
      }, {
        autoAlpha: 1,
        y: 0,
        duration: conditions.reduceMotion ? 0 : 0.24,
        ease: 'power4.out',
        clearProps: 'transform,opacity,visibility',
      });
    });
    return () => motion.revert();
  }, { scope: pageRef, dependencies: [Boolean(analysis)], revertOnUpdate: true });

  const startDiagnosis = async (file = { name: '陈同学-前端与AI项目简历.pdf' }) => {
    if (!/\.(pdf|doc|docx)$/i.test(file.name || '')) {
      message.error('仅支持 PDF、DOC、DOCX 格式的简历');
      return false;
    }
    if (file.size && file.size > 10 * 1024 * 1024) {
      message.error('简历文件不能超过 10 MB');
      return false;
    }

    setLoading(true);
    setError(null);
    try {
      const resumeFile = typeof File !== 'undefined' && file instanceof File ? file : null;
      const result = await diagnoseCandidate({ resumeFile });
      setAnalysis(result);
      setSelectedRoleId(result.matches?.[0]?.id || null);
      setSelectedGap(result.matches?.[0]?.gaps?.[0]?.skill || result.gaps?.[0]?.skill || '岗位适配');
      message.success(result.source === 'live'
        ? (result.pipeline?.mode === 'full' ? '完整人岗智能匹配流水线已完成' : '简历解析完成，已从现有推荐服务生成结果')
        : '已加载脱敏示例诊断');
      requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: 'auto' });
        document.querySelector('.workbench-content')?.scrollTo({ top: 0, behavior: 'auto' });
      });
    } catch (diagnosisError) {
      const errorMessage = diagnosisError.message || '诊断失败，请检查后端服务后重试';
      setError(errorMessage);
      message.error(errorMessage);
    } finally { setLoading(false); }
    return false;
  };

  const matches = analysis?.matches || [];
  const selectedMatch = matches.find((match) => match.id === selectedRoleId) || matches[0];
  const selectedGaps = selectedMatch?.gaps || analysis?.gaps || [];
  const selectedAction = gapActions[selectedGap] || {
    title: `围绕“${selectedGap}”形成可验证的项目证据`,
    detail: '先完成一个可运行的最小实践，再记录任务目标、实现过程、评测结果与复盘说明。',
  };

  const selectRole = (match) => {
    setSelectedRoleId(match.id);
    setSelectedGap(match.gaps[0]?.skill || 'Agent 工作流');
  };

  const createLearningPlan = () => {
    localStorage.setItem('careerTarget', JSON.stringify({
      role: selectedMatch.role,
      version: selectedMatch.version,
      score: selectedMatch.score,
      gaps: selectedGaps.map((gap) => gap.skill),
    }));
    navigate('/learning');
  };

  return (
    <div className="workbench-page diagnosis-page-v2" ref={pageRef}>
      <PageHeading eyebrow="PERSON-ROLE DIAGNOSIS" title="人岗诊断" description="上传简历后自动匹配岗位图谱，确认目标岗位并查看可解释的能力差距。">
        {roleContext && <Tag color="blue">当前岗位版本：{roleContext.role} · {roleContext.version}</Tag>}
      </PageHeading>

      <nav className="diagnosis-flow" aria-label="诊断流程">
        {['上传简历', '确认画像', '自动匹配', '差距诊断'].map((label, index) => <React.Fragment key={label}><span className={analysis || index === 0 ? 'active' : ''}><b>{index + 1}</b>{label}</span>{index < 3 && <i />}</React.Fragment>)}
      </nav>

      {analysis?.pipeline?.warning && <Alert
        className="diagnosis-error"
        type="warning"
        showIcon
        message="完整智能匹配流水线已降级"
        description={`${analysis.pipeline.warning}。当前结果来自现有岗位推荐接口。`}
      />}

      {loading && !analysis ? <Skeleton active paragraph={{ rows: 12 }} /> : !analysis ? <section className="diagnosis-setup">
        <div className="diagnosis-upload-zone">
          {error && <Alert className="diagnosis-error" type="error" showIcon message="无法完成人岗诊断" description={error} closable onClose={() => setError(null)} />}
          <Upload.Dragger accept=".pdf,.doc,.docx" maxCount={1} beforeUpload={startDiagnosis} showUploadList={false} disabled={loading}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <h2>上传一份简历，建立能力画像</h2>
            <p>支持 PDF、DOC、DOCX，单文件不超过 10 MB</p>
            <Button type="primary" loading={loading}>选择文件</Button>
          </Upload.Dragger>
          <button className="sample-resume-button" onClick={() => startDiagnosis()} disabled={loading}><FilePdfOutlined /><span><strong>陈同学-前端与AI项目简历.pdf</strong><small>使用脱敏示例快速查看完整诊断</small></span><ArrowRightOutlined /></button>
        </div>
        <aside className="diagnosis-target-panel diagnosis-auto-panel">
          <span>AUTOMATIC MATCHING</span><h2>系统将自动完成</h2>
          <ol><li><b>01</b><span><strong>解析简历能力</strong><small>提取技能、项目和经历证据</small></span></li><li><b>02</b><span><strong>匹配岗位图谱</strong><small>从已发布岗位版本中计算匹配度</small></span></li><li><b>03</b><span><strong>输出能力差距</strong><small>解释优势、缺口和学习优先级</small></span></li></ol>
          <div className="target-version-facts"><p><span>岗位池</span><strong>38 个</strong></p><p><span>能力节点</span><strong>3,468</strong></p><p><span>图谱版本</span><strong>2026.7</strong></p></div>
          <footer><SafetyCertificateOutlined />所有结论均引用已发布岗位版本和简历证据</footer>
        </aside>
      </section> : <div className="diagnosis-results">
        <section className="diagnosis-match-selector" aria-label="自动匹配岗位">
          <header><div><span>AUTOMATIC ROLE MATCHES</span><h2>选择一个目标岗位继续诊断</h2></div><p>匹配基于当前简历画像与已发布岗位版本</p></header>
          <div>{matches.map((match, index) => <button type="button" key={match.id} className={match.id === selectedMatch?.id ? 'active' : ''} onClick={() => selectRole(match)}>
            <span>{String(index + 1).padStart(2, '0')} · {match.family}</span><strong>{match.role}</strong><p>{match.reason}</p><footer><small>{match.version}</small><b>{match.score}</b></footer>
          </button>)}</div>
        </section>

        <section className="diagnosis-report-workspace">
        <main className="diagnosis-report">
          <header className="diagnosis-report-header">
            <div><span>{analysis.profile.name} / 已确认目标岗位</span><h2>{selectedMatch?.role} <small>{selectedMatch?.version}</small></h2><p>{analysis.profile.experience}</p></div>
            <div className="overall-match"><strong>{selectedMatch?.score}</strong><span>综合匹配度</span><small><SafetyCertificateOutlined /> {analysis.profile.confidence == null ? '后端未提供画像置信度' : `画像置信度 ${analysis.profile.confidence}%`}</small></div>
          </header>

          <section className="profile-skill-confirmation">
            <header><span>已确认能力画像</span><button>编辑画像</button></header>
            <div>{analysis.profile.skills.map((skill) => <span key={skill}><CheckCircleFilled />{skill}</span>)}</div>
          </section>

          <section className="dimension-comparison">
            <header><div><span>MATCH BREAKDOWN</span><h2>关键能力差距</h2></div><p><i className="current-level" />当前能力 <i className="target-level" />岗位要求</p></header>
            {selectedGaps.map((gap) => {
              const current = gap.current || 55;
              const target = gap.target || 75;
              return <button className={`gap-comparison-row ${selectedGap === gap.skill ? 'active' : ''}`} key={gap.skill} onClick={() => setSelectedGap(gap.skill)} aria-pressed={selectedGap === gap.skill}>
                <span><strong>{gap.skill}</strong><small>{gap.priority}优先级</small></span>
                <div className="dual-bar"><i className="target-bar" style={{ width: `${target}%` }} /><i className="current-bar" style={{ width: `${current}%` }} /></div>
                <b>差距 {target - current}</b>
                <ArrowRightOutlined />
              </button>;
            })}
          </section>

          <section className="diagnosis-recommendation">
            <div><span>NEXT ACTION / {selectedGap}</span><h2>{selectedAction.title}</h2><p>{selectedAction.detail}</p></div>
            <Button type="primary" onClick={createLearningPlan}>生成学习路径 <ArrowRightOutlined /></Button>
          </section>
        </main>

        <TechnicalInspector
          title="诊断报告"
          status="已生成"
          version={selectedMatch?.version || '当前 JD'}
          confidence={analysis.profile.confidence}
          explanation={[...selectedGaps.filter((gap) => gap.skill === selectedGap), ...selectedGaps.filter((gap) => gap.skill !== selectedGap)].map((gap) => gap.reason)}
          evidence={analysis.source === 'live' ? [
            { source: '简历解析结果', confidence: '后端实际提取', excerpt: analysis.profile.skills.join('、') || '未提取到明确技能', collectedAt: analysis.generatedAt },
            { source: `${selectedMatch?.role}岗位要求`, confidence: selectedMatch?.version, excerpt: selectedGaps.length ? `待补充技能：${selectedGaps.map((gap) => gap.skill).join('、')}` : '未发现明确技能缺口', collectedAt: analysis.generatedAt },
            { source: '人岗匹配服务', confidence: `综合匹配度 ${selectedMatch?.score}%`, excerpt: selectedMatch?.reason, collectedAt: analysis.generatedAt },
            ...Object.entries(selectedMatch?.scoreBreakdown || {}).map(([factor, score]) => ({
              source: scoreLabels[factor] || factor,
              confidence: `因子得分 ${Math.round((Number(score) || 0) * 100)}%`,
              excerpt: `该因子已参与 Fusion 融合排序，最终综合匹配度为 ${selectedMatch?.score}%。`,
              collectedAt: analysis.generatedAt,
            })),
            ...(selectedMatch?.evidencePaths || []).slice(0, 4).map((path) => ({
              source: '知识图谱证据路径',
              confidence: 'Neo4j 实际查询',
              excerpt: path,
              collectedAt: analysis.generatedAt,
            })),
            ...(analysis.pipeline?.warning ? [{
              source: '流水线运行状态',
              confidence: '已降级',
              excerpt: analysis.pipeline.warning,
              collectedAt: analysis.generatedAt,
            }] : []),
          ] : [
            { source: '脱敏示例简历', confidence: '演示数据', excerpt: '使用 LangChain 与 FastAPI 完成企业知识库问答服务。', collectedAt: '示例快照' },
            { source: `${selectedMatch?.role}岗位能力项`, confidence: selectedMatch?.version, excerpt: `${selectedGaps[0]?.skill}被标记为当前目标岗位的优先能力要求。`, collectedAt: selectedMatch?.version },
            { source: '岗位市场交叉验证', confidence: '演示数据', excerpt: selectedMatch?.reason, collectedAt: '示例快照' },
          ]}
          history={analysis.source === 'live' ? [
            { label: '完成简历文本解析', time: analysis.generatedAt },
            { label: `提取 ${analysis.profile.skills.length} 项技能证据`, time: analysis.generatedAt },
            ...(analysis.pipeline?.capabilities || []).map((capability) => ({ label: `完成${capability}`, time: analysis.generatedAt })),
            { label: `输出 ${matches.length} 个候选岗位匹配`, time: analysis.generatedAt },
          ] : [
            { label: '加载脱敏示例简历', time: '示例' },
            { label: '生成示例能力画像', time: '示例' },
            { label: `对照${selectedMatch?.role}完成示例诊断`, time: '示例' },
          ]}
        />
        </section>
      </div>}
    </div>
  );
};

export default DiagnosisPage;
