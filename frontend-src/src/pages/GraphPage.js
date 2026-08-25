import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Segmented, Select, Tooltip } from 'antd';
import {
  ArrowLeftOutlined,
  DatabaseOutlined,
  ExpandOutlined,
  FullscreenExitOutlined,
  RadarChartOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import GalaxyScene from '../components/workbench/GalaxyScene';
import { getCapabilityGraph } from '../services/talentApi';

const typeLabels = {
  root: '岗位宇宙',
  domain: '一级岗位',
  family: '二级岗位',
  role: '三级岗位',
};

const stackDomainMap = {
  大模型技术栈: 'ai',
  数据智能技术栈: 'data',
  智能终端技术栈: 'intelligent-system',
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
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [mode, setMode] = useState('overview');
  const [selectedId, setSelectedId] = useState('root');
  const [stack, setStack] = useState('全部技术栈');
  const [level, setLevel] = useState('全部层级');
  const [year, setYear] = useState('2026');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [roleContext] = useState(() => {
    try { return JSON.parse(localStorage.getItem('roleEvolutionContext') || 'null'); } catch { return null; }
  });
  const workspaceRef = useRef(null);

  useEffect(() => {
    getCapabilityGraph().then(setData).catch((error) => setLoadError(error));
  }, []);

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
  const roleOptions = useMemo(() => {
    const levelType = { 岗位大类: 'domain', 岗位族: 'family', 具体岗位: 'role' }[level];
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
    const domainId = stackDomainMap[value];
    if (domainId) navigateToNode(domainId);
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
               <p>{year} 市场快照 · {data.summary.domains} 个岗位大类 · {data.summary.families} 个岗位族 · {data.summary.roles} 个核心岗位</p>
               {roleContext && <span className="graph-role-context">当前岗位版本：{roleContext.role} · {roleContext.version}</span>}
             </div>
          </div>
          <div className="graph-hud-controls">
            <Select
              showSearch
              allowClear
              suffixIcon={<SearchOutlined />}
              className="graph-search"
              placeholder="搜索岗位并定位"
              optionFilterProp="label"
              options={roleOptions}
              onSelect={navigateToNode}
            />
            <Segmented value={stack} options={['全部技术栈', ...data.stacks]} onChange={selectStack} />
            <Select className="graph-level-select" value={level} onChange={setLevel} options={['全部层级', '岗位大类', '岗位族', '具体岗位'].map((value) => ({ value, label: value }))} />
            <Tooltip title={isFullscreen ? '退出全屏（Esc）' : '全屏探索'}><Button type="text" icon={isFullscreen ? <FullscreenExitOutlined /> : <ExpandOutlined />} aria-label={isFullscreen ? '退出全屏' : '全屏探索'} onClick={toggleFullscreen} /></Tooltip>
          </div>
        </header>

        <div className="graph-crumb-row">
          {mode !== 'overview' && <Button type="text" icon={<ArrowLeftOutlined />} onClick={stepBack}>{mode === 'family' ? '返回一级岗位' : '返回银河'}</Button>}
          <nav aria-label="图谱层级">
            <button onClick={resetGraph}>岗位银河</button>
            {mode !== 'overview' && selectedPath.slice(1).map((node) => <React.Fragment key={node.id}><span>/</span><button onClick={() => navigateToNode(node.id)}>{node.label}</button></React.Fragment>)}
          </nav>
          <div className="graph-runtime"><RadarChartOutlined /><span>{data.summary.roles.toLocaleString()} 个岗位节点</span><b>{{ overview: 'GALAXY VIEW', domain: 'ROLE SYSTEM', family: 'ROLE ORBIT' }[mode]}</b></div>
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
            <span><small>岗位定义</small><strong>{data.summary.roles.toLocaleString()}</strong></span>
            <span><small>能力节点</small><strong>{(data.summary.skills || 0).toLocaleString()}</strong></span>
            <span><small>岗位-技能关系</small><strong>{(data.summary.relationships || 0).toLocaleString()}</strong></span>
          </div>}

          {mode !== 'overview' && selectedNode && <aside className="galaxy-inspector" data-testid="galaxy-inspector">
            <header>
              <span><i /> {typeLabels[selectedNode.type]}</span>
              <button aria-label={mode === 'family' ? '返回一级岗位' : '返回岗位银河'} onClick={stepBack}><ReloadOutlined /></button>
            </header>
            <h2>{selectedNode.label}</h2>
            <p>{selectedNode.detail}</p>
            <div className="galaxy-inspector-metrics">
              <span><small>岗位样本</small><strong>{selectedNode.count}</strong></span>
              <span><small>市场增速</small><strong>{selectedNode.growth}</strong></span>
              <span><small>数据版本</small><strong>v{year.slice(2)}.7</strong></span>
            </div>
            <section>
              <span>核心能力</span>
              <div>{(selectedNode.skills || []).map((skill) => <b key={skill}>{skill}</b>)}</div>
            </section>
            <footer><DatabaseOutlined /><span><strong>岗位证据持续更新</strong><small>最近同步于 2 小时前</small></span></footer>
          </aside>}

          <div className="galaxy-topology-legend">
            {mode === 'overview' ? <>
              <span><i className="galaxy-legend-star" />一级岗位恒星</span>
              <span><i className="galaxy-legend-dust" />市场岗位信号</span>
            </> : mode === 'domain' ? <>
              <span><i className="galaxy-legend-star" />一级岗位 · 恒星</span>
              <span><i className="galaxy-legend-planet" />二级岗位 · 行星</span>
            </> : <>
              <span><i className="galaxy-legend-planet" />二级岗位 · 中心行星</span>
              <span><i className="galaxy-legend-moon" />三级岗位 · 卫星</span>
            </>}
          </div>
        </div>
      </section>
    </div>
  );
};

export default GraphPage;
