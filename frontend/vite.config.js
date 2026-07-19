import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    // صراحتاً روی IPv4 لوکال بالا می‌آید تا همیشه با http://127.0.0.1:5173 قابل‌دسترس باشد
    host: '127.0.0.1',
    port: 5173,
  },
});
