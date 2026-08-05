import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { motion, useReducedMotion } from 'framer-motion';
import { Input, Layout } from 'antd';
import {
  BankOutlined,
  BookOutlined,
  ClusterOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  RadarChartOutlined,
  SearchOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import './workbench.css';
import './workflow.css';
import './v0-upgrade.css';

const { Header, Content } = Layout;

gsap.registerPlugin(useGSAP);

const enterpriseItems = [
  { key: '/recruitment', icon: <FileTextOutlined />, label: '我的招聘' },
  { key: '/candidates', icon: <TeamOutlined />, label: '候选匹配', badge: 5 },
  { key: '/signals', icon: <RadarChartOutlined />, label: '岗位市场雷达', badge: 18 },
  { key: '/graph', icon: <ClusterOutlined />, label: '全景图谱' },
];

const candidateItems = [
  { key: '/diagnosis', icon: <FileSearchOutlined />, label: '人岗诊断' },
  { key: '/learning', icon: <BookOutlined />, label: '学习路径' },
  { key: '/graph', icon: <ClusterOutlined />, label: '全景图谱' },
];

const WorkbenchLayout = () => {
  const [workspaceRole, setWorkspaceRole] = useState(() => localStorage.getItem('workspaceRole') || 'candidate');
  const [commandQuery, setCommandQuery] = useState('');
  const [commandOpen, setCommandOpen] = useState(false);
  const [activeCommandIndex, setActiveCommandIndex] = useState(0);
  const [indicator, setIndicator] = useState({ left: 0, width: 0, ready: false });
  const [hoverIndicator, setHoverIndicator] = useState({ left: 0, width: 0, ready: false });
  const [roleIndicator, setRoleIndicator] = useState({ left: 0, width: 0, ready: false });
  const [roleHoverIndicator, setRoleHoverIndicator] = useState({ left: 0, width: 0, ready: false });
  const location = useLocation();
  const navigate = useNavigate();
  const routeRef = useRef(null);
  const commandSearchRef = useRef(null);
  const tabsRef = useRef(null);
  const tabButtonRefs = useRef([]);
  const roleSwitchRef = useRef(null);
  const roleButtonRefs = useRef([]);
  const reduceMotion = useReducedMotion();
  const enterpriseMode = workspaceRole === 'enterprise';
  const navItems = enterpriseMode ? enterpriseItems : candidateItems;
  const aliases = { '/discovery': '/signals', '/evolution': '/signals' };
  const selectedKey = aliases[location.pathname] || navItems.find((item) => item.key === location.pathname)?.key || '/';

  useEffect(() => {
    localStorage.setItem('workspaceRole', workspaceRole);
    const enterpriseOnlyRoutes = ['/recruitment', '/candidates', '/signals', '/discovery', '/evolution'];
    const candidateOnlyRoutes = ['/diagnosis', '/learning'];
    if (!enterpriseMode && enterpriseOnlyRoutes.includes(location.pathname)) navigate('/diagnosis', { replace: true });
    if (enterpriseMode && candidateOnlyRoutes.includes(location.pathname)) navigate('/recruitment', { replace: true });
  }, [enterpriseMode, location.pathname, navigate, workspaceRole]);

  useEffect(() => {
    const positionIndicator = () => {
      const activeIndex = navItems.findIndex((item) => item.key === selectedKey);
      const activeButton = tabButtonRefs.current[activeIndex];
      const container = tabsRef.current;
      if (!activeButton || !container) return;
      setIndicator({ left: activeButton.offsetLeft, width: activeButton.offsetWidth, ready: true });
      setHoverIndicator({ left: 0, width: container.offsetWidth, ready: true });
    };
    positionIndicator();
    window.addEventListener('resize', positionIndicator);
    return () => window.removeEventListener('resize', positionIndicator);
  }, [navItems, selectedKey]);

  useEffect(() => {
    const positionRoleIndicator = () => {
      const activeIndex = workspaceRole === 'candidate' ? 0 : 1;
      const activeButton = roleButtonRefs.current[activeIndex];
      const container = roleSwitchRef.current;
      if (!activeButton || !container) return;
      setRoleIndicator({ left: activeButton.offsetLeft, width: activeButton.offsetWidth, ready: true });
      setRoleHoverIndicator({ left: 0, width: container.offsetWidth, ready: true });
    };
    positionRoleIndicator();
    window.addEventListener('resize', positionRoleIndicator);
    return () => window.removeEventListener('resize', positionRoleIndicator);
  }, [workspaceRole]);

  useEffect(() => {
    const focusCommandSearch = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setCommandOpen((open) => !open);
      }
      if (event.key === 'Escape') setCommandOpen(false);
    };
    window.addEventListener('keydown', focusCommandSearch);
    return () => window.removeEventListener('keydown', focusCommandSearch);
  }, []);

  useEffect(() => {
    if (commandOpen) {
      setActiveCommandIndex(0);
      commandSearchRef.current?.focus();
    }
  }, [commandOpen]);

  useGSAP(() => {
    const motion = gsap.matchMedia();
    motion.add({ reduceMotion: '(prefers-reduced-motion: reduce)' }, ({ conditions }) => {
      gsap.fromTo(routeRef.current, {
        autoAlpha: conditions.reduceMotion ? 1 : 0.82,
        y: conditions.reduceMotion ? 0 : 6,
      }, {
        autoAlpha: 1,
        y: 0,
        duration: conditions.reduceMotion ? 0 : 0.22,
        ease: 'power4.out',
        clearProps: 'transform,opacity,visibility',
      });
    });
    return () => motion.revert();
  }, { scope: routeRef, dependencies: [location.pathname, workspaceRole], revertOnUpdate: true });

  const handleNavigate = (key) => navigate(key);
  const changeWorkspaceRole = (role) => {
    setWorkspaceRole(role);
    navigate(role === 'enterprise' ? '/recruitment' : '/diagnosis');
  };
  const setTabHover = (index) => {
    const button = tabButtonRefs.current[index];
    if (button) setHoverIndicator({ left: button.offsetLeft, width: button.offsetWidth, ready: true });
  };
  const resetTabHover = () => {
    const container = tabsRef.current;
    if (container) setHoverIndicator({ left: 0, width: container.offsetWidth, ready: true });
  };
  const setRoleHover = (index) => {
    const button = roleButtonRefs.current[index];
    if (button) setRoleHoverIndicator({ left: button.offsetLeft, width: button.offsetWidth, ready: true });
  };
  const resetRoleHover = () => {
    const container = roleSwitchRef.current;
    if (container) setRoleHoverIndicator({ left: 0, width: container.offsetWidth, ready: true });
  };
  const commandItems = navItems.map((item) => ({
    ...item,
    meta: item.key === '/graph' ? 'Capability graph' : item.key === '/diagnosis' ? 'Person-role diagnosis' : item.key === '/learning' ? 'Learning plan' : item.key === '/signals' ? 'Market evolution' : item.key === '/recruitment' ? 'Job postings' : 'Candidate review',
  }));
  const matchingCommands = commandItems.filter((item) => `${item.label} ${item.meta}`.toLowerCase().includes(commandQuery.toLowerCase()));
  const executeCommand = (key) => {
    setCommandOpen(false);
    setCommandQuery('');
    handleNavigate(key);
  };
  const handleCommandKeyDown = (event) => {
    if (!matchingCommands.length) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveCommandIndex((index) => Math.min(index + 1, matchingCommands.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveCommandIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      executeCommand(matchingCommands[activeCommandIndex]?.key || matchingCommands[0].key);
    }
  };

  return (
    <Layout className={`workbench-layout workbench-top-layout workspace-role-${workspaceRole} ${location.pathname === '/graph' ? 'graph-route-shell' : ''}`}>
      <Header className="workbench-header workbench-topbar">
        <Link className="topbar-brand" to="/" aria-label="返回工作台">
          <span className="brand-mark"><ClusterOutlined /></span>
          <span><strong>职能图谱</strong><small>ROLE INTELLIGENCE</small></span>
        </Link>

        <nav className="top-page-tabs" ref={tabsRef} aria-label="主导航" onMouseLeave={resetTabHover}>
          <motion.div
            className="top-page-tabs-hover"
            aria-hidden="true"
            initial={false}
            animate={hoverIndicator.ready ? { left: hoverIndicator.left, width: hoverIndicator.width, opacity: 1 } : { opacity: 0 }}
            transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 400, damping: 30 }}
          />
          <motion.div
            className="top-page-tabs-active"
            aria-hidden="true"
            initial={false}
            animate={indicator.ready ? { left: indicator.left, width: indicator.width, opacity: 1 } : { opacity: 0 }}
            transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 400, damping: 30 }}
          />
          {navItems.map((item, index) => <button
            key={item.key}
            ref={(element) => { tabButtonRefs.current[index] = element; }}
            type="button"
            className={item.key === selectedKey ? 'active' : ''}
            aria-current={item.key === selectedKey ? 'page' : undefined}
            onClick={() => handleNavigate(item.key)}
            onMouseEnter={() => setTabHover(index)}
          >
            {item.icon}<span>{item.label}</span>{item.badge && <b>{item.badge}</b>}
          </button>)}
        </nav>

        <div className="topbar-tools">
          <div className="top-role-switch" ref={roleSwitchRef} role="radiogroup" aria-label="切换工作台角色" onMouseLeave={resetRoleHover}>
            <motion.div className="top-role-switch-hover" aria-hidden="true" initial={false} animate={roleHoverIndicator.ready ? { left: roleHoverIndicator.left, width: roleHoverIndicator.width, opacity: 1 } : { opacity: 0 }} transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 400, damping: 30 }} />
            <motion.div className="top-role-switch-active" aria-hidden="true" initial={false} animate={roleIndicator.ready ? { left: roleIndicator.left, width: roleIndicator.width, opacity: 1 } : { opacity: 0 }} transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 400, damping: 30 }} />
            {[{ value: 'candidate', label: '求职者', icon: <UserOutlined /> }, { value: 'enterprise', label: '企业', icon: <BankOutlined /> }].map((item, index) => <button
              key={item.value}
              ref={(element) => { roleButtonRefs.current[index] = element; }}
              type="button"
              role="radio"
              aria-checked={workspaceRole === item.value}
              className={workspaceRole === item.value ? 'active' : ''}
              onClick={() => changeWorkspaceRole(item.value)}
              onMouseEnter={() => setRoleHover(index)}
            >{item.icon}<span>{item.label}</span></button>)}
          </div>
        </div>
      </Header>

      {commandOpen && <div className="command-overlay" role="presentation" onMouseDown={() => setCommandOpen(false)}>
        <section className="command-dialog" role="dialog" aria-modal="true" aria-label="全局命令搜索" onMouseDown={(event) => event.stopPropagation()}>
          <header>
            <SearchOutlined />
            <Input ref={commandSearchRef} value={commandQuery} onChange={(event) => { setCommandQuery(event.target.value); setActiveCommandIndex(0); }} placeholder="搜索页面、岗位或操作..." variant="borderless" onKeyDown={handleCommandKeyDown} />
            <kbd>Esc</kbd>
          </header>
          <div className="command-section-label">QUICK NAVIGATION</div>
          <div className="command-results">
            {matchingCommands.map((item, index) => <button key={item.key} type="button" className={index === activeCommandIndex ? 'active' : ''} onMouseEnter={() => setActiveCommandIndex(index)} onClick={() => executeCommand(item.key)}>
              <span className="command-result-icon">{item.icon}</span><span><strong>{item.label}</strong><small>{item.meta}</small></span><span className="command-result-enter">Enter</span>
            </button>)}
            {!matchingCommands.length && <div className="command-empty">没有匹配的页面或操作</div>}
          </div>
          <footer><span><kbd>↑↓</kbd> 选择</span><span><kbd>Enter</kbd> 打开</span><span><kbd>Esc</kbd> 关闭</span></footer>
        </section>
      </div>}
      <Content className="workbench-content"><div className="route-stage" ref={routeRef}><Outlet context={{ workspaceRole }} /></div></Content>
    </Layout>
  );
};

export default WorkbenchLayout;
