const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  // Keep the dev proxy aligned with the local backend port used by the app.
  // API_PROXY_TARGET can still override this for another environment.
  const target = process.env.API_PROXY_TARGET || 'http://localhost:18088';

  // 只把后端请求代理到 API 服务，前端页面路由留给 React Router
  app.use(
    '/api',
    createProxyMiddleware({
      target,
      changeOrigin: true,
    })
  );

  app.use(
    '/health',
    createProxyMiddleware({
      target,
      changeOrigin: true,
    })
  );
};
