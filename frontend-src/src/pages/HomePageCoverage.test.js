import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HomePage from './HomePage';

beforeAll(() => {
  global.IntersectionObserver = class {
    observe() {} disconnect() {} unobserve() {}
  };
  window.matchMedia = () => ({ matches: false, addListener: jest.fn(), removeListener: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() });
});

it('renders the public job-search entry page and its primary actions', () => {
  render(<MemoryRouter><HomePage /></MemoryRouter>);
  expect(screen.getByText('Find Your Perfect Job Match with AI')).toBeTruthy();
  expect(screen.getByText('Senior Software Engineer')).toBeTruthy();
  expect(screen.getByText('Personalized Recommendations')).toBeTruthy();
  expect(screen.getByText('Search Jobs Now')).toBeTruthy();
});
