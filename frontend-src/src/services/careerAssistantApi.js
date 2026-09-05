export const askCareerAssistant = async ({ message, history = [], pageContext = {} }) => {
  const response = await fetch('/api/v1/career-assistant/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, page_context: pageContext }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
};
