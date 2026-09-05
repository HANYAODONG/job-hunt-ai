import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CareerAssistant from './CareerAssistant';
import { askCareerAssistant } from '../../services/careerAssistantApi';

jest.mock('../../services/careerAssistantApi', () => ({ askCareerAssistant: jest.fn() }));

test('opens candidate assistant and sends a contextual question', async () => {
  askCareerAssistant.mockResolvedValue({ answer: '**优先级**\n- 补齐SQL项目证据\n- 准备STAR案例', available: true });
  render(<CareerAssistant pathname="/diagnosis" />);
  fireEvent.click(screen.getByRole('button', { name: '打开求职AI助手' }));
  expect(screen.getByText('页面上下文已连接')).toBeTruthy();
  expect(screen.getByText('导入我的简历和分析结果')).toBeTruthy();
  fireEvent.change(screen.getByPlaceholderText('输入你的求职问题...'), { target: { value: '我该先学什么？' } });
  fireEvent.click(screen.getByRole('button', { name: '发送' }));
  await waitFor(() => expect(screen.getByText('优先级').tagName).toBe('STRONG'));
  expect(screen.getByText('补齐SQL项目证据').closest('li')).toBeTruthy();
  expect(askCareerAssistant).toHaveBeenCalledWith(expect.objectContaining({
    message: '我该先学什么？',
    pageContext: { page: '人岗诊断', path: '/diagnosis' },
  }));
});
