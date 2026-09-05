import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { App as AntdApp, Button, Empty, Progress, Skeleton } from 'antd';
import { CheckOutlined, ClockCircleOutlined, FileDoneOutlined, PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import PageHeading from '../components/workbench/PageHeading';
import TechnicalInspector from '../components/workbench/TechnicalInspector';
import { getLearningPlan } from '../services/talentApi';
import { saveLearningAssistantContext } from '../services/careerAssistantContext';
import { useNavigate } from 'react-router-dom';
import '../components/workbench/candidate-flow.css';

gsap.registerPlugin(useGSAP);

const LearningPlanPage = () => {
  const { message } = AntdApp.useApp();
  const navigate = useNavigate();
  const [plan, setPlan] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const pageRef = useRef(null);

  useGSAP(() => {
    if (!activeId) return undefined;
    const motion = gsap.matchMedia();
    motion.add({ reduceMotion: '(prefers-reduced-motion: reduce)' }, ({ conditions }) => {
      gsap.fromTo('.active-stage-detail', {
        autoAlpha: conditions.reduceMotion ? 1 : 0.76,
        y: conditions.reduceMotion ? 0 : 6,
      }, {
        autoAlpha: 1,
        y: 0,
        duration: conditions.reduceMotion ? 0 : 0.2,
        ease: 'power4.out',
        clearProps: 'transform,opacity,visibility',
      });
    });
    return () => motion.revert();
  }, { scope: pageRef, dependencies: [activeId], revertOnUpdate: true });

  useEffect(() => {
    getLearningPlan().then((result) => {
      let target = null;
      try { target = JSON.parse(localStorage.getItem('careerTarget')); } catch { target = null; }
      const resultStages = Array.isArray(result?.stages) ? result.stages.filter(Boolean) : [];
      const stages = target?.gaps?.length ? resultStages.map((stage, index) => {
        const skill = target.gaps[index] || stage.skill;
        if (skill === stage.skill) return stage;
        return {
          ...stage,
          title: `${skill}专项实践`,
          skill,
          goal: `围绕${skill}完成一个可运行、可评测、可复盘的专项实践。`,
          tasks: [`梳理${skill}的岗位要求`, `完成${skill}最小实践`, '记录评测结果与改进说明'],
          outcome: `${skill}实践项目与复盘说明`,
        };
      }) : resultStages;
      const nextPlan = target ? { ...result, targetRole: target.role, targetVersion: target.version, matchScore: target.score, stages } : result;
      setPlan(nextPlan);
      saveLearningAssistantContext(nextPlan);
      setActiveId(stages.find((stage) => stage.status === '进行中')?.id || stages[0]?.id);
    });
  }, []);
  if (!plan) return <div className="page-loading"><Skeleton active paragraph={{ rows: 12 }} /></div>;

  const activeStage = plan.stages.find((stage) => stage.id === activeId) || plan.stages[0];
  const statusIcon = { '已完成': <CheckOutlined />, '进行中': <PlayCircleOutlined />, '未开始': <ClockCircleOutlined /> };

  if (!activeStage) {
    return (
      <div className="workbench-page learning-plan-page" ref={pageRef}>
        <PageHeading eyebrow="GROWTH PLAN" title="学习与改进计划" description="当前诊断没有产生可用的能力缺口，请返回诊断页重新选择目标岗位。">
          <Button icon={<ReloadOutlined />} onClick={() => navigate('/diagnosis')}>重新诊断</Button>
        </PageHeading>
        <section className="learning-workspace"><Empty description="暂无可生成的学习阶段" /></section>
      </div>
    );
  }

  return (
    <div className="workbench-page learning-plan-page" ref={pageRef}>
      <PageHeading eyebrow="GROWTH PLAN" title="学习与改进计划" description="把诊断中的能力缺口转化为有前置关系、可交付、可复诊的阶段任务。">
        <Button icon={<ReloadOutlined />} onClick={() => navigate('/diagnosis')}>重新诊断</Button>
      </PageHeading>

      <section className="plan-summary-band">
        <div><span>{plan.profile} · 目标岗位</span><h2>{plan.targetRole} <small>{plan.targetVersion}</small></h2><p>{plan.matchScore && <><b className="plan-match-score">匹配度 {plan.matchScore}</b> · </>}计划由 3 个关键能力缺口生成，预计 3 周完成。</p></div>
        <div className="plan-progress"><Progress type="circle" size={76} percent={plan.progress} strokeColor="#4059c7" /><span><strong>{plan.currentStage}</strong><small>更新于 {plan.updatedAt}</small></span></div>
      </section>

      <section className="learning-workspace">
        <main className="learning-route">
          <header><span>LEARNING ROUTE</span><h2>从能力缺口到可验证作品</h2></header>
          <div className="stage-route">
            {plan.stages.map((stage, index) => <React.Fragment key={stage.id}>
              <button className={`${stage.id === activeId ? 'active' : ''} ${stage.status === '已完成' ? 'complete' : ''}`} onClick={() => setActiveId(stage.id)}>
                <span>{statusIcon[stage.status]}</span><small>{stage.phase} · {stage.duration}</small><strong>{stage.title}</strong><em>{stage.skill}</em>
              </button>
              {index < plan.stages.length - 1 && <i className="stage-connector"><b /></i>}
            </React.Fragment>)}
          </div>

          <article className="active-stage-detail">
            <header><div><span>{activeStage.phase} / {activeStage.status}</span><h2>{activeStage.title}</h2></div><b>{activeStage.duration}</b></header>
            <p>{activeStage.goal}</p>
            <section><span>阶段任务</span>{activeStage.tasks.map((task, index) => <label key={task}><input type="checkbox" defaultChecked={activeStage.status === '已完成' || (activeStage.status === '进行中' && index === 0)} /><span>{task}</span></label>)}</section>
            <footer><FileDoneOutlined /><div><span>预期交付物</span><strong>{activeStage.outcome}</strong></div><Button type="primary" onClick={() => message.success(`${activeStage.title}的进度已更新`)}>更新进度</Button></footer>
          </article>
        </main>

        <TechnicalInspector
          title="路径依据"
          status="诊断生成"
          version={plan.targetVersion}
          confidence={91}
          explanation={[
            `${activeStage.skill}是当前诊断中优先级最高的能力缺口之一。`,
            `该能力在${plan.targetRole} ${plan.targetVersion}中的要求强度持续上升。`,
            `学习任务按照前置知识、实践产出和可验证证据排序。`,
          ]}
          evidence={[
            { source: '诊断报告 DR-20260725', confidence: '差距 33', excerpt: `简历中尚未发现足够的${activeStage.skill}项目证据。`, collectedAt: plan.updatedAt },
            { source: `岗位定义 ${plan.targetVersion}`, confidence: '已发布', excerpt: `${activeStage.skill}已被标注为目标岗位的关键能力项。`, collectedAt: '2026-07-18' },
          ]}
          history={[
            { label: '生成初始学习计划', time: '2026-07-25 10:58' },
            { label: '完成阶段 1 交付物', time: '2026-07-25 11:12' },
            { label: '进入阶段 2', time: plan.updatedAt },
          ]}
        />
      </section>
    </div>
  );
};

export default LearningPlanPage;
