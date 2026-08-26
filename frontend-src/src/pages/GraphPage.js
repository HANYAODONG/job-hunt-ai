import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Segmented, Select, Tooltip } from 'antd';
import { useQuery, useQueryClient } from 'react-query';
import {
  ArrowLeftOutlined,
  ExpandOutlined,
  FullscreenExitOutlined,
  RadarChartOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import GalaxyScene from '../components/workbench/GalaxyScene';
import { getCapabilityGraph, getCapabilityRoleJobs } from '../services/talentApi';
import { subscribeGraphDataChanged } from '../services/graphSync';

const typeLabels = {
  root: '岗位宇宙',
  domain: '一级分类',
  family: '岗位方向',
  role: '标准岗位',
};

const GRAPH_STATE_KEY = 'job-hunt.graph-state.v1';

const readGraphState = () => {
  try {
    const saved = JSON.parse(sessionStorage.getItem(GRAPH_STATE_KEY) || 'null');
    return saved && typeof saved === 'object' ? saved : {};
  } catch {
    return {};
  }
};

const flattenTree = (root) => {
  const nodes = [];
  const visit = (node, parent = null, depth = 0) => {
    nodes.push({ ...node, parentId: parent?.id || null, depth });
    (node.children || []).forEach((child) => visit(child, node, depth + 1));
  };
  visit(root);
  return nodes;
};

const findPath = (node, id, path = []) => {
  const nextPath = [...path, node];
  if (node.id === id) return nextPath;
  for (const child of node.children || []) {
    const result = findPath(child, id, nextPath);
    if (result) return result;
  }
  return null;
};

const GraphPage = () => {
  const savedState = useMemo(readGraphState, []);
  const [mode, setMode] = useState(savedState.mode || 'overview');
  const [selectedId, setSelectedId] = useState(savedState.selectedId || 'root');
  const [stack, setStack] = useState(savedState.stack || '全部技术栈');
  const [level, setLevel] = useState(['全部层级', '一级分类', '岗位方向', '标准岗位'].includes(savedState.level) ? savedState.level : '全部层级');
  const [year, setYear] = useState(savedState.year || '2026');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [roleContext] = useState(() => {
    try { return JSON.parse(localStorage.getItem('roleEvolutionContext') || 'null'); } catch { return null; }
  });
  const workspaceRef = useRef(null);
  const queryClient = useQueryClient();

  const { data, error: loadError } = useQuery(
    ['capability-graph', year],
    () => getCapabilityGraph(year),
    {
      staleTime: 5 * 60 * 1000,
      cacheTime: 30 * 60 * 1000,
      keepPreviousData: true,
      refetchOnMount: true,
    },
  );

  useEffect(() => {
    sessionStorage.setItem(GRAPH_STATE_KEY, JSON.stringify({ mode, selectedId, stack, level, year }));
  }, [mode, selectedId, stack, level, year]);

  useEffect(() => {
    const syncFullscreenState = () => setIsFullscreen(document.fullscreenElement === workspaceRef.current);
    document.addEventListener('fullscreenchange', syncFullscreenState);
    return () => document.removeEventListener('fullscreenchange', syncFullscreenState);
  }, []);

  const allNodes = useMemo(() => data ? flattenTree(data.tree) : [], [data]);
  const selectedPath = useMemo(() => data ? findPath(data.tree, selectedId) || [data.tree] : [], [data, selectedId]);
  const selectedNode = selectedPath[selectedPath.length - 1];
  const activeDomain = selectedPath[1] || null;
  const activeFamily = selectedPath[2] || null;
  const roleJobsQuery = useQuery(
    ['capability-role-jobs', selectedNode?.id, selectedNode?.standard_category, selectedNode?.standard_direction, selectedNode?.standard_role],
    () => getCapabilityRoleJobs({
      category: selectedNode.standard_category,
      direction: selectedNode.standard_direction,
      role: selectedNode.standard_role,
      limit: 4,
    }),
    {
      enabled: selectedNode?.type === 'role',
      staleTime: 30 * 1000,
      cacheTime: 10 * 60 * 1000,
      refetchOnMount: true,
      keepPreviousData: true,
    },
  );

  useEffect(() => subscribeGraphDataChanged(() => {
    queryClient.invalidateQueries(['capability-graph']);
    queryClient.invalidateQueries(['capability-role-jobs']);
  }), [queryClient]);
  const roleOptions = useMemo(() => {
    const levelType = { 一级分类: 'domain', 岗位方向: 'family', 标准岗位: 'role' }[level];
    return allNodes
      .filter((node) => node.type !== 'root' && (!levelType || node.type === levelType))
      .map((node) => ({ value: node.id, label: `${node.label} · ${typeLabels[node.type]}` }));
  }, [allNodes, level]);

  if (loadError) return <div className="workbench-page graph-page graph-experience"><div className="page-loading graph-loading">岗位图谱暂时无法连接，请确认后端服务已启动。</div></div>;
  if (!data) return <div className="workbench-page graph-page graph-experience"><div className="page-loading graph-loading">正在同步岗位宇宙...</div></div>;

  const resetGraph = () => {
    setMode('overview');
    setSelectedId('root');
  };

  const navigateToNode = (id) => {
    if (id === 'root') {
      resetGraph();
      return;
    }
    const path = findPath(data.tree, id);
    if (!path?.[1]) return;
    setSelectedId(id);
    setMode(path[path.length - 1].type === 'domain' ? 'domain' : 'family');
  };

  const stepBack = () => {
    if (mode === 'family' && activeDomain) {
      setSelectedId(activeDomain.id);
      setMode('domain');
      return;
    }
    resetGraph();
  };

  const selectStack = (value) => {
    setStack(value);
    const category = data.tree.children.find((node) => node.label === value);
    if (category) navigateToNode(category.id);
    else resetGraph();
  };

  const toggleFullscreen = async () => {
    const workspace = workspaceRef.current;
    if (!workspace) return;

    if (isFullscreen || document.fullscreenElement === workspace) {
      try {
        if (document.fullscreenElement) await document.exitFullscreen?.();
      } finally {
        setIsFullscreen(false);
      }
      return;
    }

    if (!workspace.requestFullscreen) return;
    try {
      await workspace.requestFullscreen();
      setIsFullscreen(true);
    } catch {
      setIsFullscreen(false);
    }
  };

  return (
    <div className="workbench-page graph-page graph-experience">
      <section className={`graph-workspace graph-3d-workspace scene-${mode}`} ref={workspaceRef} data-testid="capability-graph">
        <header className="graph-hud">
          <div className="graph-hud-title">
            <span className="graph-live-indicator"><i /> LIVE ONTOLOGY</span>
              <div>
               <h1>新一代信息技术岗位银河</h1>
               <p>{year} 市场快照 · {data.summary.domains} 个一级分类 · {data.summary.families} 个岗位方向 · {data.summary.roles} 个标准岗位</p>
               {data.summary.needs_review > 0 && <span className="graph-role-context">待补充分类：{data.summary.needs_review.toLocaleString()} 条岗位数据</span>}
               {data.summary.single_role_families > 0 && <span className="graph-role-context">单岗位方向：{data.summary.single_role_families} 个 · 数据暂不足细分：{data.summary.sparse_single_role_families || 0} 个</span>}
               {roleContext && <span className="graph-role-context">当前岗位版本：{roleContext.role} · {roleContext.version}</span>}
             </div>
          </div>
          <div className="graph-hud-controls">
            <Select
              showSearch
              allowClear
              suffixIcon={<SearchOutlined />}
              className="graph-search"
              placeholder="搜索标准岗位并定位"
              optionFilterProp="label"
              options={roleOptions}
              onSelect={navigateToNode}
            />
            <Segmented value={stack} options={['全部技术栈', ...data.stacks]} onChange={selectStack} />
            <Select className="graph-level-select" value={level} onChange={setLevel} options={['全部层级', '一级分类', '岗位方向', '标准岗位'].map((value) => ({ value, label: value }))} />
            <Tooltip title={isFullscreen ? '退出全屏（Esc）' : '全屏探索'}><Button type="text" icon={isFullscreen ? <FullscreenExitOutlined /> : <ExpandOutlined />} aria-label={isFullscreen ? '退出全屏' : '全屏探索'} onClick={toggleFullscreen} /></Tooltip>
          </div>
        </header>

        <div className="graph-crumb-row">
          {mode !== 'overview' && <Button type="text" icon={<ArrowLeftOutlined />} onClick={stepBack}>{mode === 'family' ? '返回一级分类' : '返回银河'}</Button>}
          <nav aria-label="图谱层级">
            <button onClick={resetGraph}>岗位银河</button>
            {mode !== 'overview' && selectedPath.slice(1).map((node) => <React.Fragment key={node.id}><span>/</span><button onClick={() => navigateToNode(node.id)}>{node.label}</button></React.Fragment>)}
          </nav>
          <div className="graph-runtime"><RadarChartOutlined /><span>{data.summary.roles.toLocaleString()} 个标准岗位节点</span><b>{{ overview: 'GALAXY VIEW', domain: 'ROLE SYSTEM', family: 'ROLE ORBIT' }[mode]}</b></div>
        </div>

        <div className="graph-cosmos graph-three-cosmos">
          <GalaxyScene
            tree={data.tree}
            mode={mode}
            focusDomainId={activeDomain?.id}
            focusFamilyId={activeFamily?.id}
            selectedId={selectedId}
            onNodeSelect={navigateToNode}
          />

          <div className="graph-year-axis" aria-label="时间快照">
            <span>MARKET<br />TIMELINE</span>
            {['2024', '2025', '2026'].map((item) => <button key={item} className={year === item ? 'active' : ''} onClick={() => setYear(item)}><i />{item}</button>)}
          </div>

          <div className="galaxy-scene-index" aria-hidden="true">
            <span>{{ overview: 'MARKET GALAXY', domain: 'ROLE SYSTEM', family: 'ROLE ORBIT' }[mode]}</span>
            <strong>{mode === 'overview' ? '01 / OVERVIEW' : mode === 'domain' ? `02 / ${activeDomain?.label || 'SYSTEM'}` : `03 / ${activeFamily?.label || 'ORBIT'}`}</strong>
          </div>

          {mode === 'overview' && <div className="galaxy-overview-stats">
            <span><small>标准岗位</small><strong>{data.summary.roles.toLocaleString()}</strong></span>
            <span><small>能力节点</small><strong>{(data.summary.skills || 0).toLocaleString()}</strong></span>
            <span><small>岗位-技能关系</small><strong>{(data.summary.relationships || 0).toLocaleString()}</strong></span>
          </div>}

          {mode !== 'overview' && selectedNode && <aside className="galaxy-inspector" data-testid="galaxy-inspector">
            <header>
              <span><i /> {typeLabels[selectedNode.type]}</span>
              <button aria-label={mode === 'family' ? '返回一级分类' : '返回岗位银河'} onClick={stepBack}><ReloadOutlined /></button>
            </header>
            <h2>{selectedNode.label}</h2>
            <p>{selectedNode.detail}</p>
            <div className="galaxy-inspector-metrics">
              <span><small>{selectedNode.type === 'role' ? '招聘数据' : '覆盖数据'}</small><strong>{selectedNode.count}</strong></span>
              <span><small>市场增速</small><strong>{selectedNode.growth}</strong></span>
              <span><small>数据版本</small><strong>v{year.slice(2)}.7</strong></span>
            </div>
            <section>
              <span>核心能力</span>
              <div>{(selectedNode.skills || []).map((skill) => <b key={skill}>{skill}</b>)}</div>
            </section>
            {selectedNode.needs_review && <section><span>分类状态</span><div><b>待补充正式分类</b></div></section>}
            {selectedNode.type === 'family' && selectedNode.taxonomy_status && <section><span>方向证据</span><div><b className={`taxonomy-status-${selectedNode.is_single_role ? 'single' : 'multi'}`}>{selectedNode.taxonomy_status}</b></div></section>}
            {selectedNode.type === 'role' && <section className="galaxy-jd-section">
              <div className="galaxy-jd-heading"><span>对应岗位 JD</span><small>{roleJobsQuery.data?.total || selectedNode.count} 条 · {roleJobsQuery.isFetching ? '同步中' : '已同步'}</small></div>
              {roleJobsQuery.isLoading && <p className="galaxy-jd-state">正在读取岗位 JD...</p>}
              {!roleJobsQuery.isLoading && roleJobsQuery.data?.items?.length === 0 && <p className="galaxy-jd-state">当前标准岗位暂无可展示的 JD。</p>}
              <div className="galaxy-jd-list">{(roleJobsQuery.data?.items || []).map((job) => <details key={job.id}>
                <summary><strong>{job.title}</strong><small>{job.id} · {job.location}</small></summary>
                <div className="galaxy-jd-detail">
                  <p>{job.summary}</p>
                  {job.responsibilities?.length > 0 && <><span>核心职责</span><ul>{job.responsibilities.slice(0, 5).map((item) => <li key={item}>{item}</li>)}</ul></>}
                  {job.requiredSkills?.length > 0 && <><span>必备技能</span><div className="galaxy-jd-skills">{job.requiredSkills.map((skill) => <b key={skill.name}>{skill.name}</b>)}</div></>}
                </div>
              </details>)}</div>
              {(roleJobsQuery.data?.total || 0) > (roleJobsQuery.data?.items?.length || 0) && <small className="galaxy-jd-more">显示前 {roleJobsQuery.data.items.length} 条，完整岗位池共 {roleJobsQuery.data.total} 条</small>}
            </section>}
          </aside>}

          <div className="galaxy-topology-legend">
            {mode === 'overview' ? <>
              <span><i className="galaxy-legend-star" />一级分类恒星</span>
              <span><i className="galaxy-legend-dust" />市场岗位信号</span>
            </> : mode === 'domain' ? <>
              <span><i className="galaxy-legend-star" />一级分类 · 恒星</span>
              <span><i className="galaxy-legend-planet" />岗位方向 · 行星</span>
            </> : <>
              <span><i className="galaxy-legend-planet" />岗位方向 · 中心行星</span>
              <span><i className="galaxy-legend-moon" />标准岗位 · 卫星</span>
            </>}
          </div>
        </div>
      </section>
    </div>
  );
};

export default GraphPage;
