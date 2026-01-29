import fs from 'fs';
import path from 'path';
import winston from 'winston';
import config from '../../config';

class LoggerService {
  private logger: winston.Logger;

  constructor() {
    const logDir = config.logging.dir;

    // 确保日志目录存在
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }

    this.logger = winston.createLogger({
      level: config.logging.level,
      format: winston.format.combine(
        winston.format.timestamp({
          format: 'YYYY-MM-DDTHH:mm:ss'
        }),
        winston.format.errors({ stack: true }),
        winston.format.splat(),
        winston.format.printf((info) => {
          const { timestamp, level, message, service, ...rest } = info as any;
          const now = new Date();
          const offsetMinutes = -now.getTimezoneOffset();
          const sign = offsetMinutes >= 0 ? '+' : '-';
          const abs = Math.abs(offsetMinutes);
          const hh = String(Math.floor(abs / 60)).padStart(2, '0');
          const mm = String(abs % 60).padStart(2, '0');
          const ts = `${timestamp}${sign}${hh}:${mm}`;
          const ordered = {
            timestamp: ts,
            level,
            message,
            service,
            ...rest,
          };
          return JSON.stringify(ordered);
        })
      ),
      defaultMeta: { service: 'robot-dog-conversation' },
      transports: [
        // 错误日志
        new winston.transports.File({
          filename: path.join(logDir, 'error.log'),
          level: 'error',
          maxsize: 10 * 1024 * 1024, // 10MB
          maxFiles: 5,
        }),
        // 所有日志
        new winston.transports.File({
          filename: path.join(logDir, 'combined.log'),
          maxsize: 10 * 1024 * 1024,
          maxFiles: 10,
        }),
      ],
    });

    // 开发环境输出到控制台
    if (config.nodeEnv !== 'production') {
      this.logger.add(
        new winston.transports.Console({
          format: winston.format.combine(
            winston.format.colorize(),
            winston.format.simple()
          ),
        })
      );
    }
  }

  info(message: string, meta?: any): void {
    this.logger.info(message, meta);
  }

  warn(message: string, meta?: any): void {
    this.logger.warn(message, meta);
  }

  error(message: string, error?: Error, meta?: any): void {
    this.logger.error(message, {
      error: error?.message,
      stack: error?.stack,
      ...meta,
    });
  }

  debug(message: string, meta?: any): void {
    this.logger.debug(message, meta);
  }

  logConversation(data: {
    robotId: string;
    input: string;
    output: string;
    processingTime: number;
    actions?: any[];
  }): void {
    this.info('对话记录', {
      type: 'conversation',
      ...data,
    });
  }

  logAction(data: {
    robotId: string;
    action: string;
    parameters: any;
    status: string;
  }): void {
    this.info('动作执行', {
      type: 'action',
      ...data,
    });
  }

  logWebSocket(data: {
    robotId: string;
    event: string;
    details?: any;
  }): void {
    this.info('WebSocket事件', {
      type: 'websocket',
      ...data,
    });
  }
}

export default LoggerService;
