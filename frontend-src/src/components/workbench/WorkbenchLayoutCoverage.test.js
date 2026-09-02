import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';

jest.mock('gsap', () => ({ __esModule: true, default: { registerPlugin: jest.fn(), matchMedia: () => ({ add: jest.fn(), revert: jest.fn() }) } }));
jest.mock('@gsap/react', () => ({ useGSAP: jest.fn() }));
jest.mock('framer-motion', () => ({ motion: { div: ({ children, ...props }) => <div {...props}>{children}</div> }, useReducedMotion: () => true }));
jest.mock('../../routeLoaders', () => ({ preloadRoute: jest.fn() }));
import { preloadRoute } from '../../routeLoaders';
import WorkbenchLayout from './WorkbenchLayout';

const View = () => <div data-testid="path">页面</div>;
const renderLayout = () => render(<MemoryRouter initialEntries={['/diagnosis']}><Routes><Route element={<WorkbenchLayout />}><Route path="*" element={<View />} /></Route></Routes></MemoryRouter>);
beforeAll(() => { window.matchMedia = () => ({ matches: true, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() }); });
beforeEach(() => localStorage.clear());
afterEach(() => jest.clearAllMocks());

it('switches workspace role, warms routes, and opens keyboard command navigation', () => {
  renderLayout();
  expect(screen.getByRole('radio', { name: /求职者/ }).getAttribute('aria-checked')).toBe('true');
  fireEvent.mouseEnter(screen.getByRole('button', { name: /全景图谱/ }));
  expect(preloadRoute).toHaveBeenCalledWith('/graph');
  fireEvent.click(screen.getByRole('radio', { name: /企业/ }));
  expect(localStorage.getItem('workspaceRole')).toBe('enterprise');
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  expect(screen.getByRole('dialog', { name: '全局命令搜索' })).toBeTruthy();
  const input = screen.getByPlaceholderText('搜索页面、岗位或操作...');
  fireEvent.change(input, { target: { value: '质检' } });
  expect(screen.getAllByText('JD 质检').length).toBeGreaterThan(1);
  fireEvent.keyDown(input, { key: 'Enter' });
  expect(screen.queryByRole('dialog', { name: '全局命令搜索' })).toBeNull();
});
