import { createServer } from 'http';
import { Application } from './app';
import config from './config';

const app = new Application();
const httpServer = createServer(app.app);
const controlServer = createServer();
const businessServer = createServer();
const audioUploadServer = createServer();
const audioDownloadServer = createServer();

// 初始化WebSocket服务（多端口拆分）
app.websocketService.init(controlServer, { path: config.ws.path, channel: 'control' });
app.websocketService.init(businessServer, { path: config.ws.path, channel: 'business' });
app.websocketService.init(audioUploadServer, { path: config.ws.path, channel: 'audio_upload' });
app.websocketService.init(audioDownloadServer, { path: config.ws.path, channel: 'audio_download' });
if (config.ws.path !== '/api/v1/conversation/connect') {
  app.websocketService.init(controlServer, { path: '/api/v1/conversation/connect', channel: 'control' });
  app.websocketService.init(businessServer, { path: '/api/v1/conversation/connect', channel: 'business' });
  app.websocketService.init(audioUploadServer, { path: '/api/v1/conversation/connect', channel: 'audio_upload' });
  app.websocketService.init(audioDownloadServer, { path: '/api/v1/conversation/connect', channel: 'audio_download' });
}

// 启动服务器
httpServer.listen(config.ports.http, () => {
  app.logger.info(`HTTP/REST 服务启动成功`, {
    port: config.ports.http,
    env: process.env.NODE_ENV || 'development',
  });
});

controlServer.listen(config.ports.control, () => {
  app.logger.info(`控制通道服务启动成功`, {
    port: config.ports.control,
    wsPath: config.ws.path,
  });
});

businessServer.listen(config.ports.business, () => {
  app.logger.info(`业务通道服务启动成功`, {
    port: config.ports.business,
    wsPath: config.ws.path,
  });
});

audioUploadServer.listen(config.ports.audioUpload, () => {
  app.logger.info(`音频上传通道服务启动成功`, {
    port: config.ports.audioUpload,
    wsPath: config.ws.path,
  });
});

audioDownloadServer.listen(config.ports.audioDownload, () => {
  app.logger.info(`音频下载通道服务启动成功`, {
    port: config.ports.audioDownload,
    wsPath: config.ws.path,
  });
});

// 优雅关闭
process.on('SIGINT', () => {
  app.logger.info('收到SIGINT信号，正在关闭服务器...');
  httpServer.close(() => {
    controlServer.close(() => {
      businessServer.close(() => {
        audioUploadServer.close(() => {
          audioDownloadServer.close(() => {
            app.logger.info('服务器已关闭');
            process.exit(0);
          });
        });
      });
    });
  });
});

process.on('SIGTERM', () => {
  app.logger.info('收到SIGTERM信号，正在关闭服务器...');
  httpServer.close(() => {
    controlServer.close(() => {
      businessServer.close(() => {
        audioUploadServer.close(() => {
          audioDownloadServer.close(() => {
            app.logger.info('服务器已关闭');
            process.exit(0);
          });
        });
      });
    });
  });
});

// 未捕获的异常处理
process.on('uncaughtException', (error) => {
  app.logger.error('未捕获的异常', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason: any) => {
  const errorMsg = reason?.message || String(reason);
  app.logger.error('未处理的Promise拒绝', new Error(errorMsg));
});
