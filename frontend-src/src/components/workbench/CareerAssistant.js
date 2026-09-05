import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  BulbOutlined,
  CloseOutlined,
  MessageOutlined,
  ImportOutlined,
  RobotOutlined,
  SendOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { askCareerAssistant } from '../../services/careerAssistantApi';
import { collectCareerAssistantContext } from '../../services/careerAssistantContext';
import './career-assistant.css';

const routeNames = {
  '/diagnosis': '人岗诊断',
  '/learning': '学习路径',
  '/graph': '全景图谱',
  '/settings': '系统设置',
};

const quickPrompts = [
  '帮我分析当前最该补齐的三项技能',
  '怎样把项目经历写得更有说服力',
  '为目标岗位生成一份面试准备清单',
];

const renderInlineMarkdown = (text, keyPrefix) => String(text).split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
  if (part.startsWith('**') && part.endsWith('**')) {
    return <strong key={`${keyPrefix}-${index}`}>{part.slice(2, -2)}</strong>;
  }
  return <React.Fragment key={`${keyPrefix}-${index}`}>{part}</React.Fragment>;
});

const MarkdownMessage = ({ content }) => {
  const blocks = [];
  let listItems = [];
  let listType = null;
  const flushList = () => {
    if (!listItems.length) return;
    const ListTag = listType === 'ordered' ? 'ol' : 'ul';
    blocks.push(<ListTag key={`list-${blocks.length}`}>{listItems}</ListTag>);
    listItems = [];
    listType = null;
  };

  String(content || '').split('\n').forEach((rawLine, index) => {
    const line = rawLine.trim();
    const unordered = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      const nextType = ordered ? 'ordered' : 'unordered';
      if (listType && listType !== nextType) flushList();
      listType = nextType;
      listItems.push(<li key={`item-${index}`}>{renderInlineMarkdown((unordered || ordered)[1], `item-${index}`)}</li>);
      return;
    }
    flushList();
    if (!line) return;
    if (/^---+$/.test(line)) {
      blocks.push(<hr key={`hr-${index}`} />);
    } else {
      blocks.push(<p key={`p-${index}`}>{renderInlineMarkdown(line, `p-${index}`)}</p>);
    }
  });
  flushList();
  return <div className="career-markdown">{blocks}</div>;
};

const CareerAssistant = ({ pathname }) => {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [imported, setImported] = useState({ context: null, sections: [], importedAt: null });
  const [messages, setMessages] = useState([{
    role: 'assistant',
    content: '你好，我是你的求职AI助手。可以结合当前页面，帮你分析技能差距、优化简历或准备面试。',
  }]);
  const endRef = useRef(null);
  const reduceMotion = useReducedMotion();
  const pageName = routeNames[pathname] || '求职工作台';
  const basePageContext = useMemo(() => ({ page: pageName, path: pathname }), [pageName, pathname]);
  const pageContext = imported.context ? { ...imported.context, ...basePageContext } : basePageContext;

  useEffect(() => {
    if (typeof endRef.current?.scrollIntoView === 'function') {
      endRef.current.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' });
    }
  }, [messages, loading, reduceMotion]);

  const send = async (preset) => {
    const content = String(preset || input).trim();
    if (!content || loading) return;
    const prior = messages.slice(-8);
    setMessages((current) => [...current, { role: 'user', content }]);
    setInput('');
    setLoading(true);
    try {
      const result = await askCareerAssistant({ message: content, history: prior, pageContext });
      setMessages((current) => [...current, { role: 'assistant', content: result.answer }]);
    } catch (error) {
      setMessages((current) => [...current, {
        role: 'assistant',
        error: true,
        content: `暂时没有连接到AI服务：${error.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  const importAnalysis = () => {
    const result = collectCareerAssistantContext(basePageContext);
    if (!result.hasData) {
      setMessages((current) => [...current, {
        role: 'assistant',
        content: '还没有可导入的个人分析结果。请先在人岗诊断页上传简历并完成匹配；生成学习路径后还可以再次导入。',
      }]);
      return;
    }
    setImported({ context: result.context, sections: result.sections, importedAt: new Date().toLocaleTimeString('zh-CN', { hour12: false }) });
    setMessages((current) => [...current, {
      role: 'assistant',
      content: `已导入：**${result.sections.join('、')}**。接下来我会基于这些个人结果回答，不再只给通用建议。`,
    }]);
  };

  return <>
    <motion.button
      type="button"
      className={`career-assistant-launcher ${open ? 'is-open' : ''}`}
      aria-label={open ? '关闭求职AI助手' : '打开求职AI助手'}
      onClick={() => setOpen((value) => !value)}
      whileHover={reduceMotion ? undefined : { y: -2, scale: 1.02 }}
      whileTap={reduceMotion ? undefined : { scale: 0.97 }}
    >
      <span className="career-launcher-orbit" aria-hidden="true" />
      <span className="career-launcher-icon">{open ? <CloseOutlined /> : <ThunderboltOutlined />}</span>
      <span className="career-launcher-copy"><strong>求职AI助手</strong><small>DeepSeek在线</small></span>
    </motion.button>

    <AnimatePresence>
      {open && <motion.aside
        className="career-assistant-panel"
        initial={{ x: 36, opacity: 0, scale: 0.98 }}
        animate={{ x: 0, opacity: 1, scale: 1 }}
        exit={{ x: 28, opacity: 0, scale: 0.98 }}
        transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 340, damping: 30 }}
        aria-label="求职AI助手对话侧栏"
      >
        <div className="career-panel-glow" aria-hidden="true" />
        <header className="career-assistant-header">
          <div className="career-ai-mark"><RobotOutlined /></div>
          <div><span>CAREER COPILOT</span><strong>求职AI助手</strong></div>
          <button type="button" aria-label="关闭" onClick={() => setOpen(false)}><CloseOutlined /></button>
        </header>

        <div className="career-context-strip">
          <span className="career-live-dot" />
          <span>正在理解</span>
          <strong>{pageName}</strong>
          <small>{imported.context ? '个人分析已连接' : '页面上下文已连接'}</small>
        </div>

        <div className={`career-import-box ${imported.context ? 'is-imported' : ''}`}>
          <button type="button" onClick={importAnalysis}>
            <ImportOutlined />
            <span><strong>导入我的简历和分析结果</strong><small>{imported.context ? `${imported.sections.join(' · ')} · ${imported.importedAt}` : '导入画像、匹配、能力缺口与学习路径'}</small></span>
          </button>
        </div>

        <div className="career-message-list">
          {messages.map((item, index) => <div key={`${item.role}-${index}`} className={`career-message ${item.role} ${item.error ? 'error' : ''}`}>
            {item.role === 'assistant' && <span className="career-message-avatar"><ThunderboltOutlined /></span>}
            <MarkdownMessage content={item.content} />
          </div>)}
          {loading && <div className="career-message assistant">
            <span className="career-message-avatar"><ThunderboltOutlined /></span>
            <div className="career-thinking"><i /><i /><i /><span>正在梳理建议</span></div>
          </div>}
          <div ref={endRef} />
        </div>

        {messages.length < 3 && <div className="career-quick-prompts">
          <div><BulbOutlined /> 可以这样问</div>
          {quickPrompts.map((prompt) => <button key={prompt} type="button" onClick={() => send(prompt)}>{prompt}<MessageOutlined /></button>)}
        </div>}

        <footer className="career-composer">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={2000}
            rows={2}
            placeholder="输入你的求职问题..."
          />
          <button type="button" disabled={!input.trim() || loading} onClick={() => send()} aria-label="发送"><SendOutlined /></button>
          <small>AI建议仅供参考，请结合自身情况判断</small>
        </footer>
      </motion.aside>}
    </AnimatePresence>
  </>;
};

export default CareerAssistant;
