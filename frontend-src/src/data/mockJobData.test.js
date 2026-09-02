import { getMockSearchResults, mockApiDelay } from './mockJobData';

afterEach(() => jest.restoreAllMocks());

it('generates paginated fallback jobs and reranking statistics', async () => {
  jest.spyOn(Math, 'random').mockReturnValue(0.5);
  jest.useFakeTimers();
  const result = getMockSearchResults({ location: 'Boston', job_type: 'contract', experience_level: 'senior', remote_allowed: true, visa_sponsorship: false, min_salary: 100000, page: 1, page_size: 5 }, true);
  expect(result.is_mock_data).toBe(true);
  expect(result.jobs.length).toBeLessThanOrEqual(5);
  expect(result.jobs.every((job) => job.location.city === 'Boston')).toBe(true);
  expect(result.reranking_statistics).toEqual(expect.objectContaining({ average_score: expect.any(Number) }));
  const delayed = mockApiDelay();
  jest.runAllTimers();
  await delayed;
  jest.useRealTimers();
});

it('returns default pagination without reranking metrics', () => {
  jest.spyOn(Math, 'random').mockReturnValue(0.1);
  const result = getMockSearchResults({ page: 2, page_size: 3 }, false);
  expect(result.page).toBe(2);
  expect(result.page_size).toBe(3);
  expect(result.reranking_statistics).toBeNull();
});
