import React from 'react';
import { act, fireEvent, render } from '@testing-library/react';
import '@testing-library/jest-dom';
import GalaxyScene from './GalaxyScene';

const mockRendererInstances = [];
const mockResizeObservers = [];

jest.mock('gsap', () => ({
  __esModule: true,
  default: {
    to: jest.fn(() => ({ kill: jest.fn() })),
    timeline: jest.fn(() => {
      const timeline = {
        addLabel: jest.fn(() => timeline),
        to: jest.fn(() => timeline),
        call: jest.fn((callback) => { callback?.(); return timeline; }),
        kill: jest.fn(),
      };
      return timeline;
    }),
  },
}));

jest.mock('three/examples/jsm/controls/OrbitControls.js', () => ({
  OrbitControls: jest.fn().mockImplementation(() => ({
    enableDamping: false,
    dampingFactor: 0,
    enablePan: true,
    minDistance: 0,
    maxDistance: 0,
    target: { set: jest.fn() },
    update: jest.fn(),
    dispose: jest.fn(),
  })),
}));
jest.mock('three/examples/jsm/controls/OrbitControls', () => ({
  OrbitControls: class MockOrbitControls {
    constructor() { this.target = { set() {} }; this.update = jest.fn(); this.dispose = jest.fn(); }
  },
}));

jest.mock('three/examples/jsm/renderers/CSS2DRenderer.js', () => {
  const actualThree = jest.requireActual('three');
  function MockCSS2DRenderer() {
    this.domElement = global.document.createElement('div');
    this.setSize = jest.fn();
    this.render = jest.fn();
  }
  class MockCSS2DObject extends actualThree.Object3D {
    constructor(element) { super(); this.element = element; this.isCSS2DObject = true; }
  }
  return { CSS2DRenderer: MockCSS2DRenderer, CSS2DObject: MockCSS2DObject };
});


jest.mock('three', () => {
  const actualThree = jest.requireActual('three');
  class MockWebGLRenderer {
    constructor() {
      this.domElement = global.document.createElement('canvas');
      this.domElement.getBoundingClientRect = () => ({ left: 0, top: 0, width: 640, height: 360 });
      this.setPixelRatio = jest.fn();
      this.setClearColor = jest.fn();
      this.setSize = jest.fn();
      this.render = jest.fn();
      this.dispose = jest.fn();
      mockRendererInstances.push(this);
    }
  }
  return { ...actualThree, WebGLRenderer: MockWebGLRenderer };
});

beforeAll(() => {
  const contextFactory = () => ({
    createRadialGradient: () => ({ addColorStop: jest.fn() }),
    fillRect: jest.fn(),
    fillStyle: '',
  });
  jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(contextFactory);
  window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
  window.requestAnimationFrame = jest.fn(() => 1);
  window.cancelAnimationFrame = jest.fn();
  global.ResizeObserver = class {
    constructor(callback) { this.callback = callback; mockResizeObservers.push(this); }
    observe = jest.fn();
    disconnect = jest.fn();
  };
  global.IntersectionObserver = class {
    constructor(callback) { this.callback = callback; }
    observe = jest.fn();
    disconnect = jest.fn();
  };
});

afterEach(() => {
  mockRendererInstances.length = 0;
  mockResizeObservers.length = 0;
  jest.clearAllMocks();
});

const tree = {
  id: 'root', label: '岗位宇宙', type: 'root', count: 2, growth: '稳定', children: [{
    id: 'domain-1', label: '智能技术', type: 'domain', count: 2, growth: '增长', children: [{
      id: 'family-1', label: '算法工程', type: 'family', count: 1, growth: '增长', children: [{
        id: 'role-1', label: '机器学习工程师', type: 'role', count: 1, growth: '增长', is_single_role: true, taxonomy_status: '正式',
      }],
    }],
  }],
};

test('does not initialize a renderer without graph data', () => {
  const { container } = render(<GalaxyScene tree={null} mode="overview" onNodeSelect={jest.fn()} />);
  expect(container.querySelector('canvas')).not.toBeInTheDocument();
  expect(mockRendererInstances).toHaveLength(0);
});

test('initializes, resizes, handles pointer events, switches modes, and cleans up', () => {
  const onNodeSelect = jest.fn();
  const view = render(<GalaxyScene tree={tree} mode="overview" selectedId="root" onNodeSelect={onNodeSelect} />);
  const mount = view.container.firstChild;
  const renderer = mockRendererInstances[0];

  expect(renderer.domElement).toHaveAttribute('aria-label', '三维岗位银河');
  expect(renderer.domElement).toBeInTheDocument();
  expect(mockResizeObservers[0].observe).toHaveBeenCalledWith(mount);

  act(() => mockResizeObservers[0].callback());
  fireEvent.pointerMove(renderer.domElement, { clientX: 10, clientY: 10 });
  fireEvent.pointerLeave(renderer.domElement);
  fireEvent.click(renderer.domElement, { clientX: 10, clientY: 10 });

  view.unmount();
  expect(renderer.dispose).toHaveBeenCalled();
  expect(mockResizeObservers[0].disconnect).toHaveBeenCalled();
  expect(window.cancelAnimationFrame).toHaveBeenCalled();
});
