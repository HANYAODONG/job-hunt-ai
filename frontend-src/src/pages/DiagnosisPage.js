import React, { useRef, useState } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { App as AntdApp, Button, Skeleton, Upload } from 'antd';
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

gsap.registerPlugin(useGSAP);

const DiagnosisPage = () => {
  const { message } = AntdApp.useApp();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState(null);
  const [selectedGap, setSelectedGap] = useState('Agent 工作流');
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
    setLoading(true);
    try {
      const result = await diagnoseCandidate({ fileName: file.name, targetRole: '大模型应用工程师', targetVersion: 'v1.2' });
      setAnalysis(result);
      setSelectedRoleId(result.matches?.[0]?.id || null);
      setSelectedGap(result.matches?.[0]?.gaps?.[0]?.skill || result.gaps[0]?.skill || 'Agent 工作流');
      message.success('简历解析完成，已从岗位图谱中生成匹配结果');
      requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: 'auto' });
        document.querySelector('.workbench-content')?.scrollTo({ top: 0, behavior: 'auto' });
      });
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
      <PageHeading eyebrow="PERSON-ROLE DIAGNOSIS" title="人岗诊断" description="上传简历后自动匹配岗位图谱，确认目标岗位并查看可解释的能力差距。" />

      <nav className="diagnosis-flow" aria-label="诊断流程">
        {['上传简历', '确认画像', '自动匹配', '差距诊断'].map((label, index) => <React.Fragment key={label}><span className={analysis || index === 0 ? 'active' : ''}><b>{index + 1}</b>{label}</span>{index < 3 && <i />}</React.Fragment>)}
      </nav>

      {!analysis ? <section className="diagnosis-setup">
        <div className="diagnosis-upload-zone">
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
      </section> : loading ? <Skeleton active paragraph={{ rows: 12 }} /> : <div className="diagnosis-results">
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
            <div className="overall-match"><strong>{selectedMatch?.score}</strong><span>综合匹配度</span><small><SafetyCertificateOutlined /> 画像置信度 {analysis.profile.confidence}%</small></div>
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
          version="岗位 v1.2"
          confidence={analysis.profile.confidence}
          explanation={[...selectedGaps.filter((gap) => gap.skill === selectedGap), ...selectedGaps.filter((gap) => gap.skill !== selectedGap)].map((gap) => gap.reason)}
          evidence={[
            { source: '简历项目经历', confidence: '提取置信度 0.93', excerpt: '使用 LangChain 与 FastAPI 完成企业知识库问答服务。', collectedAt: '2026-07-25 11:02' },
            { source: `${selectedMatch?.role}岗位能力项`, confidence: `当前版本 ${selectedMatch?.version}`, excerpt: `${selectedGaps[0]?.skill}被标记为当前目标岗位的优先能力要求。`, collectedAt: `岗位版本 ${selectedMatch?.version}` },
            { source: '岗位市场交叉验证', confidence: '已通过', excerpt: selectedMatch?.reason, collectedAt: '2026-08-01' },
          ]}
          history={[
            { label: '完成简历文本解析', time: '11:02:14' },
            { label: '用户确认 6 项技能证据', time: '11:03:08' },
            { label: `对照${selectedMatch?.role} ${selectedMatch?.version}完成诊断`, time: '11:03:12' },
          ]}
        />
        </section>
      </div>}
    </div>
  );
};

export default DiagnosisPage;
