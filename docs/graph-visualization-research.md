# React 18 / CRA 能力图谱方案调研

调研日期：2026-07-26。目标是为本仓库的 React 18.2 + `react-scripts` 5（Create React App）岗位能力图谱选择可落地的图可视化方案。以下结论只引用项目官方文档、官方 GitHub README/源码和 npm registry metadata；`dist.unpackedSize` 是 npm 包解包体积，不等于生产 bundle 的 gzip/minzip 体积。

## 快速结论

| 方案 | React 18/CRA 接入 | 展开/折叠 | 自定义节点/边 | 布局与渲染 | npm metadata（2026-07-26） | 适合度 |
|---|---|---|---|---|---|---|
| **@relation-graph/react** | 官方 React 包；`RGProvider` + `RelationGraph`，Hooks/slots | 内建 expand holder、展开/收起 API，支持展开后重排 | React slot 可直接渲染任意 React/HTML 节点；线条有 shape/options | center、force 等；以关系图交互为主，README 未给出规模基准 | v3.0.13，MIT，约 1.98 MB unpacked，无运行时依赖 | **岗位技能树最快落地**，交互能力开箱即用 |
| **@xyflow/react (React Flow)** | 原生 React 组件，React >=17（因此支持 React 18/CRA） | 官方 Expand & Collapse 示例；通常通过 `hidden`/状态过滤子树实现 | 一等公民：custom node、multiple handles、custom edge；JSX 组件 | 画布交互、只重渲染变化节点；布局通常接 dagre/elkjs 等外部包 | v12.11.2，MIT，约 1.21 MB unpacked；依赖 zustand、d3 系统包 | **最推荐的可维护 React 方案**，但树布局/数据折叠需自行组织 |
| **@antv/g6** | TypeScript 引擎；官方称支持 React nodes，通常在 React `useEffect` 中创建 Graph | 官方 collapse-expand / collapse-expand-tree 示例与 tree behaviors | 丰富内建 node/edge/Combo，支持 data callback 和 custom element；React 节点 | 10+ 布局，部分 GPU/Rust 并行；Canvas/SVG/WebGL/SSR | v5.1.1，MIT，约 7.60 MB unpacked，依赖较多 | 大图/复杂分析能力强；集成和包体成本较高 |
| **cytoscape.js** | 核心是命令式 JS；CRA 中用 ref + `useEffect` 初始化；React wrapper 是社区包 | 核心无树折叠 UI；官方生态 `cytoscape-expand-collapse` 插件提供 API | 样式选择器、renderer、扩展机制很强；节点/边模型非 JSX | 图论模型 + 可选 renderer，布局和扩展生态成熟 | v3.34.0，MIT，约 5.70 MB unpacked | 需要图算法/选择器/扩展时合适；React 心智模型较重 |
| **sigma** | 核心是命令式 Sigma + Graphology；官方 Demo 是 React 应用，可选 `@react-sigma/core` wrapper | 核心不提供层级折叠；通过 Graphology 增删/隐藏节点自行实现 | 节点/边属性和程序化渲染器可定制；HTML/React overlay 需额外层 | 面向“数千节点/边”的 WebGL；布局通常由 graphology-layout 或外部算法提供 | v3.0.3，MIT，约 0.97 MB unpacked；依赖 events、graphology-utils | 大规模网络性能优先；岗位技能树需自建层级交互 |
| **react-force-graph** | React bindings；`react-force-graph-2d/3d/vr/ar` 独立包，CRA 可直接使用 | 无内建层级折叠；通过 `graphData` 过滤/重建子树 | accessor props、自定义 Canvas node shape、Three.js geometry、link 样式 | d3-force-3d 迭代布局；2D Canvas、3D WebGL；可配 DAG 方向 | v1.48.2，MIT，约 23.90 MB unpacked（聚合包含 2D/3D/VR/AR 依赖） | 适合探索式力导向/3D；不适合首选的稳定技能树层级布局 |

## 逐项证据与官方示例

### 1. relation-graph

- 官方 README 明确支持 React、Vue、Svelte、WebComponent；React 安装为 `npm install @relation-graph/react`，示例使用 `RGProvider`、`RGHooks.useGraphInstance()` 和 `<RelationGraph>`。[README React 示例](https://github.com/relation-graph/relation-graph/blob/master/README.md#use-relation-graph-in-react)
- 同一示例通过 `graphOptions.defaultExpandHolderPosition`、`reLayoutWhenExpandedOrCollapsed` 配置展开按钮和展开后重排；官方仓库还展示 `expand-node`、`open-all-close-all` 动画/交互示例。[Examples](https://relation-graph.com/examples)
- `RGSlotOnNode` 接收 `RGNodeSlotProps`，官方 `CustomNode.tsx` 直接返回 React JSX，因此适合把技能等级、图标、徽章放入自定义节点；`RGSlotOnView` 可放入 `RGMiniView`。[React starter](https://github.com/relation-graph/relation-graph-startup-for-react)
- npm：[package metadata](https://www.npmjs.com/package/@relation-graph/react)（v3.0.13，MIT）。官方 README 没有给出节点规模或 benchmark，生产评估应以目标数据量实测。

### 2. React Flow / `@xyflow/react`

- 官方 README 定义为“highly customizable React component”，安装 `@xyflow/react`；peer dependency `react >=17` / `react-dom >=17`，所以与 React 18.2 和 CRA 5 兼容。[README](https://github.com/xyflow/xyflow/blob/main/packages/react/README.md)
- 官方能力清单包含 custom node/edge、多个 handles、缩放/平移/选择，以及“Only nodes that have changed are re-rendered”。[Features](https://reactflow.dev/learn)
- 可直接复制的最小 React 示例在 README 的 Quickstart；官方可复制示例还包括 [Custom Nodes](https://reactflow.dev/learn/customization/custom-nodes)、[Custom Edges](https://reactflow.dev/learn/customization/custom-edges)、[Expand & Collapse](https://reactflow.dev/examples/layout/expand-collapse)、[Dagre layout](https://reactflow.dev/examples/layout/dagre)。
- Expand & Collapse 示例通过节点/边状态和可见性组织子树；它不是自动识别任意业务层级的组件，岗位数据应维护 parent/children 和 expanded 集合，并在折叠时过滤 descendants。
- npm：[package metadata](https://www.npmjs.com/package/@xyflow/react)（v12.11.2，MIT，约 1.21 MB unpacked）。官方 README 说明依赖 d3-zoom、d3-drag、zustand；dagre/elkjs 属于外接布局方案，不在核心包内。

### 3. AntV G6

- 官方 README 将 G6 定义为 TypeScript graph visualization framework，能力覆盖绘制、布局、分析、交互、动画、插件；明确写有“supports React nodes”。[README](https://github.com/antvis/G6/blob/v5/README.md)
- Quick Start 是 `new Graph({ container, data, layout: { type: 'force' }, behaviors: [...] })`；在 React 中应把 Graph 生命周期放在 `useEffect` 并在卸载时销毁实例。[Quick Start](https://g6.antv.antgroup.com/en/manual/getting-started/quick-start)
- 官方交互示例：[collapse-expand](https://g6.antv.antgroup.com/en/examples/interaction/collapse-expand)、[collapse-expand-tree](https://g6.antv.antgroup.com/en/examples/interaction/collapse-expand-tree)。节点/边/Combo 支持样式配置、data callbacks 和 custom elements；可用 React 节点增强展示。[Elements/API](https://g6.antv.antgroup.com/en/manual/element/node)
- README 宣称 10+ 常见布局，部分布局使用 GPU 或 Rust parallel computing；支持 Canvas、SVG、WebGL 及 Node SSR。这里是项目能力声明，不代表所有布局在 CRA 目标数据上都达到同一性能。
- npm：[package metadata](https://www.npmjs.com/package/@antv/g6)（v5.1.1，MIT，约 7.60 MB unpacked；依赖 `@antv/g`、`@antv/layout`、`@antv/algorithm` 等）。

### 4. Cytoscape.js

- 官方 README 描述为 graph theory library，包含图模型和可选 renderer；最小调用为 `cytoscape({ elements, container })`。因此 React 集成通常是 ref + effect 的命令式桥接，而不是 JSX 节点树。[README](https://github.com/cytoscape/cytoscape.js/blob/master/README.md)
- 官方 Tokyo railway demo 同时给出 live demo 和源码，可直接复制初始化、样式和布局。[Tokyo demo](https://js.cytoscape.org/demos/tokyo-railways/)
- 层级折叠不在核心 API；官方生态插件 [cytoscape.js-expand-collapse](https://github.com/iVis-at-Bilkent/cytoscape.js-expand-collapse) 提供 expand/collapse、compound nodes 和事件。插件 npm v4.1.1、MIT，peer dependency `cytoscape ^3.3.0`。[npm metadata](https://www.npmjs.com/package/cytoscape-expand-collapse)
- 核心支持 selector-based style、多个布局/renderer 和约 70 个扩展（README badge），适合后续图分析、过滤和复杂关系；但需要额外维护 React 生命周期与插件实例。
- npm：[package metadata](https://www.npmjs.com/package/cytoscape)（v3.34.0，MIT，约 5.70 MB unpacked）。

### 5. Sigma.js

- 官方 README 定位为基于 WebGL、面向“thousands of nodes and edges”的图可视化库，建立在 Graphology 之上；核心使用 `new Sigma(graph, container)` 的命令式 API。[README](https://github.com/jacomyal/sigma.js/blob/main/README.md)
- 官方资源页提供 [Docs](https://www.sigmajs.org/docs/)、[Storybook](https://www.sigmajs.org/storybook) 和 [React-based demo](https://www.sigmajs.org/demo/)。React 项目可使用社区/官方生态 wrapper [`@react-sigma/core`](https://github.com/sim51/react-sigma)，其 npm metadata v5.0.6、MIT；核心 Sigma 本身不是 React 组件。
- Graphology 负责节点/边数据和算法；层级展开/折叠需要在 Graphology 中增删/隐藏 descendants，再调用 Sigma refresh。官方文档没有内建 tree collapse 控件。
- Sigma 通过 WebGL 获得大图性能；节点/边属性（颜色、尺寸、标签）由 Graphology attributes 提供，复杂 DOM/React 节点需 overlay 或自定义 renderer，交互实现成本高于 React Flow。
- npm：[sigma metadata](https://www.npmjs.com/package/sigma)（v3.0.3，MIT，约 0.97 MB unpacked）。

### 6. react-force-graph

- 官方 README 说明是 force-graph 套件的 React bindings，导出 2D/3D/VR/AR 四个包；2D 基于 HTML Canvas，3D 基于 ThreeJS/WebGL，底层使用 d3-force-3d。[README](https://github.com/vasturiano/react-force-graph/blob/master/README.md)
- 官方示例可直接复制：[Basic](https://vasturiano.github.io/react-force-graph/example/basic/)、[HTML nodes](https://vasturiano.github.io/react-force-graph/example/html-nodes/)、[Custom 2D node shape](https://vasturiano.github.io/react-force-graph/example/custom-node-shape/index-canvas.html)、[Dynamic data](https://vasturiano.github.io/react-force-graph/example/dynamic/)、[Large graph](https://vasturiano.github.io/react-force-graph/example/large-graph/)。
- 节点/边均有 accessor props（颜色、尺寸、可见性、标签、曲率等）；2D 可覆盖 `nodeCanvasObject`，3D 可提供自定义 Three.js geometry。`dagMode` 支持 `td/bu/lr/rl/radial...` 方向约束，但仅适用于 DAG。
- README/API 明确 `enablePointerInteraction` 会增加鼠标跟踪成本，为最大性能可关闭；`warmupTicks`、`cooldownTicks`、`onEngineStop` 可控制初始布局和冻结时机。层级折叠没有内建 API，应通过 `graphData` 过滤 descendants。
- npm：[package metadata](https://www.npmjs.com/package/react-force-graph)（v1.48.2，MIT，约 23.90 MB unpacked；聚合依赖包含 2D/3D/VR/AR）。若仅需 2D，应安装 `react-force-graph-2d` 以减少依赖范围。

## 面向岗位技能树的建议

1. **首选 `@xyflow/react`**：项目是 React 18/CRA，节点和边可以直接写 JSX，官方 Expand & Collapse 与 Dagre 示例可复用，状态可和现有 React Query/Redux 逻辑自然组合。需要自行实现 parent/children 展开状态及布局调用。
2. **若希望最少业务代码，选 `@relation-graph/react`**：内建关系图数据格式、展开按钮、展开后重排、MiniView 和 React slot；先验证其默认布局在岗位数量和标签长度下的可读性。
3. **大图/分析型需求再评估 G6 或 Sigma**：G6 功能最全但包体和命令式生命周期成本高；Sigma 的 WebGL 优势适合数千节点网络，却需要自行补齐树折叠、React overlay 和层级布局。
4. **Cytoscape.js** 更适合需要图算法、selector 和扩展生态的关系分析；**react-force-graph** 更适合力导向探索或 3D 展示，不建议作为二维岗位技能树的默认实现。

## 复核清单

- 在真实岗位数据（建议 100/500/2,000 节点）上测首屏时间、折叠/展开帧率、Canvas/WebGL 内存和 CRA production gzip；npm unpacked size 只能作为依赖复杂度信号。
- 统一验证键盘可达性、屏幕阅读器语义、移动端触控和 URL 状态恢复；Canvas/WebGL 方案通常需要额外 DOM overlay 才能满足这些要求。
- 锁定许可证和版本：上述六个核心包及列出的折叠/React wrapper 均为 MIT，但仍应在最终 lockfile 与许可证扫描中复核传递依赖。
