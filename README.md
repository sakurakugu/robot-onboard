// TODO: 到时候把前端和后端放到cloud文件夹中，记得把各种脚本等的路径也同时更改一下

后端
```bash
npm install
cp .env.example .env
npm run dev
```

前端
```bash
npm install
npm run dev
```

访问 http://localhost:5174

## 配置

修改 [vite.config.ts](vite.config.ts) 中的代理配置以连接到不同的后端服务器：

```typescript
server: {
  port: 5174,
  proxy: {
    '/api': {
      target: 'http://localhost:3000',
      changeOrigin: true
    }
  }
}
```
