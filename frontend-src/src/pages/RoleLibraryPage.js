import React, { useEffect, useMemo, useState } from 'react';
import { Button, Input, Select, Skeleton } from 'antd';
import { ApartmentOutlined, ArrowRightOutlined, BranchesOutlined, EditOutlined, SearchOutlined } from '@ant-design/icons';
import { Link, useOutletContext } from 'react-router-dom';
import PageHeading from '../components/workbench/PageHeading';
import TechnicalInspector from '../components/workbench/TechnicalInspector';
import { getRoleCatalog } from '../services/talentApi';

const RoleLibraryPage = () => {
  const { workspaceRole = 'candidate' } = useOutletContext() || {};
  const enterpriseMode = workspaceRole === 'enterprise';
  const [roles, setRoles] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState('');

  useEffect(() => { getRoleCatalog().then((items) => { setRoles(items); setSelectedId(items[0]?.id); }); }, []);

  const visibleRoles = useMemo(() => roles.filter((role) => role.name.toLowerCase().includes(query.toLowerCase()) || role.requiredSkills.some((skill) => skill.name.toLowerCase().includes(query.toLowerCase()))), [roles, query]);
  const selected = roles.find((role) => role.id === selectedId) || visibleRoles[0];

  if (!roles.length) return <div className="page-loading"><Skeleton active paragraph={{ rows: 12 }} /></div>;

  const evidence = [
    { source: '企业招聘官网', confidence: '68 条', excerpt: `${selected.name}相关职责已完成岗位名称与技能点标准化。`, collectedAt: '2026-07-25 09:30' },
    { source: '招聘平台公开 JD', confidence: `${selected.evidenceCount} 条`, excerpt: `${selected.requiredSkills.slice(0, 3).map((skill) => skill.name).join('、')}构成当前版本的核心能力组合。`, collectedAt: selected.updatedAt },
    { source: '专家审核记录', confidence: '已通过', excerpt: '岗位边界、职责颗粒度和技能等级已完成领域专家复核。', collectedAt: selected.updatedAt },
  ];

  return (
    <div className="workbench-page role-library-page">
      <PageHeading eyebrow="ROLE CATALOG" title={enterpriseMode ? '岗位库' : '探索目标岗位'} description={enterpriseMode ? '维护标准岗位定义、当前版本、能力要求和演化证据。' : '查看岗位职责、最新能力要求和版本证据，并选择确定版本发起诊断。'}>
        {enterpriseMode && <Button icon={<ApartmentOutlined />}>新建岗位草稿</Button>}
      </PageHeading>

      <div className="catalog-toolbar">
        <Input prefix={<SearchOutlined />} placeholder="搜索岗位或技能" value={query} onChange={(event) => setQuery(event.target.value)} allowClear />
        <Select defaultValue="全部领域" options={[{ value: '全部领域' }, { value: '人工智能' }, { value: '软件工程' }]} />
        <Select defaultValue="全部级别" options={[{ value: '全部级别' }, { value: '初级' }, { value: '中级' }, { value: '高级' }]} />
        <span>{visibleRoles.length} 个标准岗位</span>
      </div>

      <section className="role-catalog-workspace">
        <aside className="role-index">
          {visibleRoles.map((role) => <button key={role.id} className={role.id === selected.id ? 'active' : ''} onClick={() => setSelectedId(role.id)}><span>{role.family} · {role.level}</span><strong>{role.name}</strong><small>当前 {role.version} · {role.evidenceCount} 条证据</small><b>{role.growth}</b></button>)}
        </aside>

        <main className="role-profile">
          <header className="role-profile-header">
            <div><span>{selected.domain} / {selected.family}</span><h2>{selected.name}</h2><p>{selected.summary}</p></div>
            <div><span className="published-version">{selected.status} · {selected.version}</span><small>更新于 {selected.updatedAt}</small></div>
          </header>

          <div className="role-actions-row">
            <Link to="/graph"><Button icon={<BranchesOutlined />}>在图谱中查看</Button></Link>
            {enterpriseMode && <Button icon={<EditOutlined />}>编辑岗位定义</Button>}
            <Link to="/diagnosis"><Button type="primary">发起人岗诊断 <ArrowRightOutlined /></Button></Link>
          </div>

          <section className="role-content-section"><span>核心职责</span><ol>{selected.responsibilities.map((item) => <li key={item}>{item}</li>)}</ol></section>
          <section className="role-content-section"><span>必备技能与要求</span><div className="skill-requirements">{selected.requiredSkills.map((skill) => <div key={skill.name}><header><strong>{skill.name}</strong><span>需求变化 {skill.trend}</span></header><div><i style={{ width: `${skill.level}%` }} /></div><small>要求强度 {skill.level}</small></div>)}</div></section>
          <div className="role-profile-columns">
            <section className="role-content-section"><span>加分技能</span><div className="plain-token-list">{selected.bonusSkills.map((skill) => <b key={skill}>{skill}</b>)}</div></section>
            <section className="role-content-section"><span>行业应用场景</span><div className="plain-token-list scenarios">{selected.scenarios.map((scenario) => <b key={scenario}>{scenario}</b>)}</div></section>
          </div>
          <section className="role-content-section version-history"><span>版本历史</span>{selected.versions.map((version, index) => <div key={version.version}><i className={index === 0 ? 'current' : ''} /><strong>{version.version}</strong><time>{version.date}</time><p>{version.note}</p></div>)}</section>
        </main>

        <TechnicalInspector
          title="岗位画像"
          status="已审核"
          version={selected.version}
          confidence={94}
          explanation={[
            `${selected.evidenceCount} 条有效岗位数据支撑当前定义。`,
            `${selected.requiredSkills[0].name}与${selected.requiredSkills[1].name}在目标岗位中保持高频共现。`,
            `当前版本较上一版重点强化${selected.bonusSkills[0]}相关能力。`,
          ]}
          evidence={evidence}
          history={selected.versions.map((version) => ({ label: `${version.version} ${version.note}`, time: version.date }))}
        />
      </section>
    </div>
  );
};

export default RoleLibraryPage;
