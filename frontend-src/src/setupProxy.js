const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  // 只把 /api 开头的请求代理到后端，前端页面路由留给 React Router
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:8000',
      changeOrigin: true,
    })
  );
};
