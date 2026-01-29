import cors from 'cors';
import express from 'express';
import config from './config';
import DatabaseService from './core/database';
import LoggerService from './core/logger';
import { ConversationController } from './modules/conversation/controller';
import { createConversationRoutes } from './modules/conversation/routes';
import { ConversationService } from './modules/conversation/service';
import { RobotController } from './modules/robot/controller';
import { createRobotRoutes } from './modules/robot/routes';
import { RobotService } from './modules/robot/service';
import { RoleController } from './modules/role/controller';
import { createRoleRoutes } from './modules/role/routes';
import { RoleService } from './modules/role/service';
import { SettingsController } from './modules/settings/controller';
import { createSettingsRoutes } from './modules/settings/routes';
import { SettingsService } from './modules/settings/service';
import { createSystemRoutes } from './modules/system/routes';
import WebSocketService from './modules/websocket/service';

export class Application {
  public app: express.Application;
  public logger: LoggerService;
  public database: DatabaseService;
  public websocketService: WebSocketService;

  // 服务实例
  private robotService: RobotService;
  private conversationService: ConversationService;
  private settingsService: SettingsService;
  private roleService: RoleService;

  // 控制器实例
  private robotController: RobotController;
  private conversationController: ConversationController;
  private settingsController: SettingsController;
  private roleController: RoleController;

  // 应用初始化
  constructor() {
    this.app = express();
    this.logger = new LoggerService();
    this.database = new DatabaseService();
    this.websocketService = new WebSocketService(this.logger, this.database);

    // 初始化服务
    this.robotService = new RobotService(this.database, this.logger);
    this.conversationService = new ConversationService(this.database);
    this.settingsService = new SettingsService(this.database);
    this.roleService = new RoleService(this.database, this.logger);

    // 初始化控制器
    this.robotController = new RobotController(this.robotService);
    this.conversationController = new ConversationController(this.conversationService, this.database);
    this.settingsController = new SettingsController(this.settingsService);
    this.roleController = new RoleController(this.roleService);

    this.loadPersistedConfig();
    this.setupMiddleware();
    this.setupRoutes();
  }

  /**
   * 从数据库加载持久化配置并覆盖内存配置
   */
  private loadPersistedConfig(): void {
    try {
      const s = this.database.getAllSettings();
      
      // LLM Provider
      const provider = s['llm.provider'];
      if (provider && (['openai','bigmodel','anthropic','deepseek'].includes(provider))) {
        (config.llm as any).provider = provider;
        this.logger.info(`LLM Provider: ${provider} (来自数据库)`);
      } else {
        this.logger.warn(`未配置 LLM Provider，使用默认值: ${config.llm.provider}。请通过参数管理页面配置！`);
      }
      
      // OpenAI
      const openaiApiKey = s['openai.apiKey'];
      const openaiModel = s['openai.model'];
      const openaiBaseUrl = s['openai.baseUrl'];
      if (openaiApiKey || openaiModel || openaiBaseUrl) {
        config.llm.openai = config.llm.openai || { apiKey: '', model: '' };
        if (openaiApiKey) config.llm.openai.apiKey = openaiApiKey;
        if (openaiModel) config.llm.openai.model = openaiModel;
        if (openaiBaseUrl) config.llm.openai.baseUrl = openaiBaseUrl;
        this.logger.info('OpenAI 配置已从数据库加载');
      }
      
      // BigModel
      const bigApiKey = s['bigmodel.apiKey'];
      const bigModel = s['bigmodel.model'];
      const bigBaseUrl = s['bigmodel.baseUrl'];
      if (bigApiKey || bigModel || bigBaseUrl) {
        config.llm.bigmodel = config.llm.bigmodel || { apiKey: '', model: '' };
        if (bigApiKey) config.llm.bigmodel.apiKey = bigApiKey;
        if (bigModel) config.llm.bigmodel.model = bigModel;
        if (bigBaseUrl) config.llm.bigmodel.baseUrl = bigBaseUrl;
        this.logger.info('BigModel 配置已从数据库加载');
      }
      
      this.logger.info('持久化配置加载完成', {
        provider: config.llm.provider,
        hasOpenAIKey: !!(config.llm.openai?.apiKey),
        hasBigModelKey: !!(config.llm.bigmodel?.apiKey)
      });
      
      if (!config.llm.openai?.apiKey && !config.llm.bigmodel?.apiKey) {
        this.logger.warn('⚠️  未找到任何 LLM API 密钥配置！');
        this.logger.warn('⚠️  请访问前端参数管理页面进行配置：http://localhost:5174/params');
      }
    } catch (e: any) {
      this.logger.error('加载持久化配置失败，请通过参数管理页面配置', e);
    }
  }

  /**
   * 设置中间件
   */
  private setupMiddleware(): void {
    // CORS
    this.app.use(cors());

    // JSON解析
    this.app.use(express.json());

    // 请求日志
    this.app.use((req, res, next) => {
      this.logger.info(`${req.method} ${req.path}`, {
        ip: req.ip,
        query: req.query,
      });
      next();
    });
  }

  /**
   * 设置路由
   */
  private setupRoutes(): void {
    const router = express.Router();

    // 注册各模块路由
    router.use('/robots', createRobotRoutes(this.robotController));
    router.use('/conversations', createConversationRoutes(this.conversationController));
    router.use('/config', createSettingsRoutes(this.settingsController));
    router.use('/roles', createRoleRoutes(this.roleController));
    router.use('/', createSystemRoutes(this.database, this.websocketService));

    // 兼容旧路由 - 发送命令到机器人
    router.post('/robot/:robotId/command', (req, res) => {
      this.conversationController.sendCommand(req, res);
    });

    // 挂载到 /api/v1 路径
    this.app.use('/api/v1', router);

    // 错误处理
    this.app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
      this.logger.error('未处理的错误', err);
      res.status(500).json({
        success: false,
        error: err.message || '服务器内部错误',
      });
    });
  }
}
