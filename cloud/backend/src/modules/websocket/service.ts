import { Server } from 'http';
import OpusScript from 'opusscript';
import { WebSocket, WebSocketServer } from 'ws';
import config from '../../config';
import { LLM_PROVIDERS } from '../../config/llm-providers';
import DatabaseService from '../../core/database';
import LoggerService from '../../core/logger';
import { isValidRobotId, RateLimiter, uuidv7 } from '../../core/utils/helpers';
import { ClientMessage, RobotConnection, ServerMessage } from '../../types';
import ASRService from '../conversation/asr-service';
import ConversationEngine from '../conversation/conversation-engine';
import TTSService from '../conversation/tts-service';
import { VideoStreamManager } from '../conversation/video-stream';


type Channel = 'control' | 'business' | 'audio_upload' | 'audio_download';

type AudioSession = {
  robotId: string;
  sessionId: string;
  format: 'opus';
  sampleRate: number;
  channels: number;
  frameDurationMs: number;
  chunks: Buffer[];
  startedAt: number;
  lastChunkAt: number;
};

class WebSocketService {
  private wssMap: Map<Channel, WebSocketServer> = new Map();
  // 机器人客户端连接（按通道）
  private robotConnections: Map<string, Map<Channel, RobotConnection>> = new Map();
  // UI 控制端连接（按通道，可多）
  private uiConnections: Map<string, Map<Channel, Set<WebSocket>>> = new Map();
  private logger: LoggerService;
  private conversationEngine: ConversationEngine;
  private database: DatabaseService;
  private ttsService: TTSService;
  private videoStreamManager: VideoStreamManager;
  private asrService: ASRService;
  private audioSessions: Map<string, AudioSession> = new Map();
  private inputMergeTimers: Map<string, NodeJS.Timeout> = new Map();
  private pendingInputs: Map<
    string,
    {
      text: string;
      ttsOptions?: any;
      inputType: 'text' | 'audio';
      audioMeta?: { asrTime: number; durationMs: number; sessionId: string };
      conversationId: string;
    }
  > = new Map();
  private inputRateLimiter = new RateLimiter(3, 3000);
  private ttsRateLimiter = new RateLimiter(5, 5000);
  private inputMergeWindowMs = 900;

  constructor(logger: LoggerService, database: DatabaseService) {
    this.logger = logger;
    this.database = database;
    this.conversationEngine = new ConversationEngine();
    this.ttsService = new TTSService();
    this.videoStreamManager = new VideoStreamManager();
    this.asrService = new ASRService();
  }

  /**
   * 初始化WebSocket服务器
   */
  init(server: Server, options: { path: string; channel: Channel }): void {
    const { path, channel } = options;
    const wss = new WebSocketServer({
      server,
      path,
    });

    wss.on('connection', (ws: WebSocket, req) => {
      this.handleConnection(ws, req, channel);
    });

    this.wssMap.set(channel, wss);
    this.logger.info('WebSocket服务已启动', { path, channel });
  }

  /**
   * 处理新连接
   */
  private handleConnection(ws: WebSocket, req: any, channel: Channel): void {
    // 从查询参数获取 robotId 与角色
    const url = new URL(req.url!, `http://${req.headers.host}`);
    let robotId = url.searchParams.get('robotId');
    const role = (url.searchParams.get('role') || '').toLowerCase();

    if (!robotId || !isValidRobotId(robotId)) {
      robotId = uuidv7();
      this.logger.info('生成新的机器狗ID', { robotId });
    }

    // UI 连接：不占用机器人连接槽位，加入 UI 订阅集合
    if (role === 'ui') {
      if (!this.uiConnections.has(robotId)) {
        this.uiConnections.set(robotId, new Map());
      }
      const byChannel = this.uiConnections.get(robotId)!;
      if (!byChannel.has(channel)) {
        byChannel.set(channel, new Set());
      }
      byChannel.get(channel)!.add(ws);
      this.logger.info('UI连接建立', {
        robotId,
        channel,
        uiCount: byChannel.get(channel)!.size,
      });
    } else {
      // 机器人连接：唯一
      const connection: RobotConnection = {
        robotId,
        websocket: ws,
        connectedAt: new Date(),
        lastActiveAt: new Date(),
        metadata: {},
        channel,
      };
      if (!this.robotConnections.has(robotId)) {
        this.robotConnections.set(robotId, new Map());
      }
      this.robotConnections.get(robotId)!.set(channel, connection);
    }

    // 更新数据库状态，避免覆盖名称与元数据
    const existing = this.database.getRobot(robotId);
    if (existing) {
      this.database.updateRobotStatus(robotId, 'online');
    } else {
      this.database.registerRobot({
        uuid: robotId,
        status: 'online',
        last_connected: new Date(),
      });
    }

    this.logger.logWebSocket({
      robotId,
      event: 'connected',
      details: { ip: req.socket.remoteAddress, role: role || 'robot' },
    });

    // 仅对机器人客户端发送连接确认消息
    if (role !== 'ui') {
      this.sendToRobot(robotId, {
        type: 'text_response',
        robotId,
        timestamp: Date.now(),
        data: {
          text: `连接成功！你的机器狗ID是: ${robotId}`,
        },
      }, channel);
    }

    // 设置消息处理器
    ws.on('message', (data: Buffer) => {
      this.handleMessage(robotId, data, channel);
    });

    // 设置关闭处理器
    ws.on('close', () => {
      if (role === 'ui') {
        const byChannel = this.uiConnections.get(robotId);
        if (byChannel) {
          const set = byChannel.get(channel);
          if (set) {
            set.delete(ws);
            if (set.size === 0) {
              byChannel.delete(channel);
            }
          }
          if (byChannel.size === 0) {
            this.uiConnections.delete(robotId);
          }
        }
        this.logger.info('UI连接关闭', { robotId, channel });
      } else {
        this.handleDisconnection(robotId, channel);
      }
    });

    // 设置错误处理器
    ws.on('error', (error) => {
      this.logger.error('WebSocket错误', error, { robotId });
    });

    // 设置心跳检测
    this.setupHeartbeat(robotId, channel);
  }

  /**
   * 处理客户端消息
   */
  private async handleMessage(robotId: string, data: Buffer, channel: Channel): Promise<void> {
    try {
      const message: ClientMessage = JSON.parse(data.toString());

      if (!this.isAllowedMessageType(channel, (message as any).type)) {
        this.logger.warn('消息通道不匹配', { robotId, channel, type: (message as any).type });
        this.sendError(robotId, 'CHANNEL_MISMATCH', '消息通道不匹配', channel);
        return;
      }

      // 更新最后活跃时间
      const rconn = this.robotConnections.get(robotId)?.get(channel);
      if (rconn) {
        rconn.lastActiveAt = new Date();
      }

      switch (message.type) {
        case 'text_input':
          await this.handleTextInput(
            robotId,
            message.data.text,
            (message as any).data?.ttsOptions,
            (message as any).data?.conversationId || (message as any).conversationId
          );
          break;
        case 'tts_input':
          await this.handleTTSInput(
            robotId,
            (message as any).data?.text,
            (message as any).data?.ttsOptions,
            (message as any).data?.conversationId || (message as any).conversationId
          );
          break;

        case 'audio_control':
          await this.handleAudioControl(robotId, (message as any).data);
          break;

        case 'audio_start':
          await this.handleAudioStart(robotId, (message as any).data);
          break;

        case 'audio_chunk':
          await this.handleAudioChunk(robotId, message.data);
          break;

        case 'audio_end':
          await this.handleAudioEnd(robotId, (message as any).data);
          break;

        case 'heartbeat':
          this.handleHeartbeat(robotId);
          break;

        case 'status': {
          this.handleStatus(robotId, message);
          break;
        }
        // 机器人注册
        case 'robot_register':
          await this.handleRobotRegister(robotId, message.data);
          break;

        case 'video_subscribe':
          await this.handleVideoSubscribe(robotId);
          break;

        case 'video_unsubscribe':
          await this.handleVideoUnsubscribe(robotId);
          break;

        case 'action_input':
          await this.handleActionInput(robotId, (message as any).data?.action, (message as any).data?.parameters);
          break;

        case 'control_input':
          await this.handleControlInput(robotId, (message as any).data);
          break;

        default:
          this.logger.warn('未知的消息类型', { robotId, type: (message as any).type });
      }
    } catch (error: any) {
      this.logger.error('处理消息失败', error, { robotId });
      this.sendError(robotId, 'MESSAGE_PARSE_ERROR', '消息解析失败', channel);
    }
  }

  private isAllowedMessageType(channel: Channel, type: string): boolean {
    const map: Record<Channel, Set<string>> = {
      control: new Set(['control_input', 'heartbeat', 'status']),
      business: new Set([
        'text_input',
        'tts_input',
        'action_input',
        'audio_control',
        'robot_register',
        'video_subscribe',
        'video_unsubscribe',
        'heartbeat',
      ]),
      audio_upload: new Set(['audio_start', 'audio_chunk', 'audio_end', 'heartbeat']),
      audio_download: new Set(['heartbeat']),
    };
    return map[channel].has(type);
  }

  /**
   * 处理文本输入
   */
  private async handleTextInput(
    robotId: string,
    text: string,
    ttsOptions?: any,
    conversationId?: string
  ): Promise<void> {
    await this.queueUserText(robotId, text, ttsOptions, 'text', undefined, conversationId);
  }

  /**
   * 处理音频转写结果
   */
  private async handleAudioTranscript(
    robotId: string,
    text: string,
    meta: { asrTime: number; durationMs: number; sessionId: string }
  ): Promise<void> {
    this.sendToUI(robotId, {
      type: 'asr_transcript',
      robotId,
      timestamp: Date.now(),
      data: {
        text,
        sessionId: meta.sessionId,
        durationMs: meta.durationMs,
        asrTime: meta.asrTime,
      },
    }, 'business');
    await this.queueUserText(robotId, text, undefined, 'audio', meta, meta.sessionId);
  }

  /**
   * 统一处理文本（来源: text/audio）
   */
  private async processUserText(
    robotId: string,
    text: string,
    ttsOptions: any,
    inputType: 'text' | 'audio',
    audioMeta?: { asrTime: number; durationMs: number; sessionId: string },
    conversationId?: string
  ): Promise<void> {
    const startTime = Date.now();
    const traceId = conversationId || uuidv7();

    try {
      this.logger.info('收到文本输入', { robotId, text, inputType });

      // 使用对话引擎处理
      let systemPrompt: string | undefined = undefined;
      let temperature: number | undefined = undefined;
      let model: string | undefined = undefined;
      let maxHistory: number = 10;
      const robot = this.database.getRobot(robotId);
      if (robot) {
        // 仅当机器人模型是有效的LLM模型时才传递，否则使用系统配置的默认模型
        const provider = config.llm.provider;
        const allowedModels =
          LLM_PROVIDERS.find(p => p.value === (provider as any))?.models.map(m => m.value) || [];
        if (robot.model && allowedModels.includes(robot.model)) {
          model = robot.model;
        } else {
          model = undefined;
        }
        try {
          const meta = robot.metadata ? JSON.parse(robot.metadata) : {};
          systemPrompt = meta.ai_system_prompt || undefined;
          temperature = typeof meta.ai_temperature === 'number' ? meta.ai_temperature : undefined;
        } catch {}
        if (robot.role_id) {
          const role = this.database.getRole(robot.role_id);
          if (role) {
            if (typeof role.max_history === 'number') {
              maxHistory = role.max_history || 10;
            }
            if (!systemPrompt && role.system_prompt) {
              systemPrompt = role.system_prompt;
            }
            if (typeof temperature !== 'number' && typeof role.temperature === 'number') {
              temperature = role.temperature;
            }
            if (!model && role.llm_model) {
              model = role.llm_model;
            }
          }
        }
      }
      const response = await this.conversationEngine.processMessage(robotId, text, {
        history: [],
        maxHistory,
        systemPrompt,
        model,
        temperature
      });

      const processingTime = Date.now() - startTime;

      // 发送文本回复（广播到机器人和所有UI）
      this.broadcastMessage(robotId, {
        type: 'text_response',
        robotId,
        timestamp: Date.now(),
        conversationId: traceId,
        data: {
          text: response.text,
        },
      }, 'business');

      try {
        const ttsText = this.sanitizeTtsText(response.text);
        if (ttsText) {
          const audio = await this.ttsService.synthesize(ttsText, ttsOptions);
          this.broadcastMessage(robotId, {
            type: 'audio_response',
            robotId,
            timestamp: Date.now(),
            conversationId: traceId,
            data: audio,
          }, 'audio_download');
        } else {
          this.logger.info('TTS跳过：回复文本为空或仅包含表情', { robotId });
        }
      } catch (e: any) {
        this.logger.error('TTS生成失败', e, { robotId });
      }

      // 发送动作指令
      for (const action of response.actions) {
        this.sendToRobot(robotId, {
          type: 'action_command',
          robotId,
          timestamp: Date.now(),
          conversationId: traceId,
          data: {
            action: action.name,
            parameters: action.parameters,
            safetyChecked: true,
          },
        }, 'business');

        // 记录动作
        this.database.logAction(robotId, action.name, action.parameters, 'success');
      }

      // 记录对话
      this.database.insertConversation({
        robot_id: robotId,
        timestamp: new Date(),
        type: inputType,
        user_input: text,
        ai_response: response.text,
        actions: JSON.stringify(response.actions),
        processing_time: processingTime,
        metadata: JSON.stringify({
          ...response.metadata,
          conversationId: traceId,
          inputType,
          asrTime: audioMeta?.asrTime,
          audioDurationMs: audioMeta?.durationMs,
          audioSessionId: audioMeta?.sessionId,
        }),
      });

      this.logger.logConversation({
        robotId,
        input: text,
        output: response.text,
        processingTime,
        actions: response.actions,
      });
    } catch (error: any) {
      this.logger.error('处理文本输入失败', error, { robotId });
      this.sendError(robotId, 'PROCESSING_ERROR', error.message, 'business');
    }
  }

  private async handleTTSInput(
    robotId: string,
    text: string,
    ttsOptions?: any,
    conversationId?: string
  ): Promise<void> {
    try {
      if (!this.ttsRateLimiter.check(robotId)) {
        this.logger.warn('TTS请求过于频繁', { robotId });
        this.sendError(robotId, 'RATE_LIMITED', '请求过于频繁，请稍后再试', 'business');
        return;
      }
      const audio = await this.ttsService.synthesize(text, ttsOptions);
      this.broadcastMessage(robotId, {
        type: 'audio_response',
        robotId,
        timestamp: Date.now(),
        conversationId,
        data: audio,
      }, 'audio_download');
    } catch (e: any) {
      this.logger.error('TTS生成失败', e, { robotId });
      this.sendError(robotId, 'TTS_ERROR', e?.message || 'TTS失败', 'business');
    }
  }

  /**
   * 处理动作输入 ({{action=xxx}})
   */
  private async handleActionInput(robotId: string, action: string, parameters?: Record<string, any>): Promise<void> {
    try {
      this.logger.info('收到动作输入', { robotId, action, parameters });

      // 验证动作名称
      if (!action || typeof action !== 'string') {
        this.sendError(robotId, 'INVALID_ACTION', '动作名称无效', 'business');
        return;
      }

      // 直接发送动作指令到机器狗
      this.sendToRobot(robotId, {
        type: 'action_command',
        robotId,
        timestamp: Date.now(),
        data: {
          action,
          parameters: parameters || {},
          safetyChecked: true,
        },
      }, 'business');

      // 记录动作
      this.database.logAction(robotId, action, parameters || {}, 'success');

      // 通知UI已发送（添加 noTTS 标记，不生成TTS音频）
      this.broadcastMessage(robotId, {
        type: 'text_response',
        robotId,
        timestamp: Date.now(),
        data: {
          text: `动作已发送: ${action}`,
          noTTS: true,  // 标记不需要生成TTS
        },
      }, 'business');

      this.logger.info('动作指令已发送，不生成TTS', { robotId, action });
    } catch (error: any) {
      this.logger.error('处理动作输入失败', error, { robotId, action });
      this.sendError(robotId, 'ACTION_ERROR', error.message || '动作处理失败', 'business');
    }
  }

  /**
   * 处理控制输入（摇杆/急停）
   */
  private async handleControlInput(robotId: string, data: any): Promise<void> {
    try {
      const command = data?.command;
      if (!command || typeof command !== 'string') {
        this.sendError(robotId, 'INVALID_CONTROL', '控制指令无效', 'control');
        return;
      }

      if (!['joystick', 'joystick_stop', 'estop'].includes(command)) {
        this.sendError(robotId, 'INVALID_CONTROL', '控制指令无效', 'control');
        return;
      }

      const payload = {
        command: command as 'joystick' | 'joystick_stop' | 'estop',
        channel: data?.channel,
        mode: data?.mode,
        x: data?.x,
        y: data?.y,
        speed: data?.speed,
      };

      const sent = this.sendToRobot(robotId, {
        type: 'control_command',
        robotId,
        timestamp: Date.now(),
        data: payload,
      }, 'control');

      if (!sent) {
        this.sendError(robotId, 'ROBOT_OFFLINE', '机器人未连接', 'control');
      }
    } catch (error: any) {
      this.logger.error('处理控制输入失败', error, { robotId });
      this.sendError(robotId, 'CONTROL_ERROR', error.message || '控制处理失败', 'control');
    }
  }

  /**
   * 处理麦克风开关
   */
  private async handleAudioControl(robotId: string, data: any): Promise<void> {
    try {
      const enabled = Boolean(data?.enabled);
      const sent = this.sendToRobot(robotId, {
        type: 'audio_control',
        robotId,
        timestamp: Date.now(),
        data: { enabled, source: 'ui' },
      }, 'business');
      if (!sent) {
        this.sendError(robotId, 'ROBOT_OFFLINE', '机器人未连接', 'business');
      }
    } catch (error: any) {
      this.logger.error('处理音频控制失败', error, { robotId });
      this.sendError(robotId, 'AUDIO_CONTROL_ERROR', error.message || '音频控制失败', 'business');
    }
  }

  /**
   * 处理音频开始
   */
  private async handleAudioStart(robotId: string, audioData: any): Promise<void> {
    const sessionId = String(audioData?.sessionId || '');
    if (!sessionId) {
      this.logger.warn('音频开始缺少sessionId', { robotId });
      return;
    }
    const sampleRate = Number(audioData?.sampleRate || 16000);
    const channels = Number(audioData?.channels || 1);
    const frameDurationMs = Number(audioData?.frameDurationMs || 20);
    this.audioSessions.set(sessionId, {
      robotId,
      sessionId,
      format: 'opus',
      sampleRate,
      channels,
      frameDurationMs,
      chunks: [],
      startedAt: Date.now(),
      lastChunkAt: Date.now(),
    });
    this.logger.debug('音频会话开始', { robotId, sessionId, sampleRate, channels, frameDurationMs });
  }

  /**
   * 处理音频数据块
   */
  private async handleAudioChunk(robotId: string, audioData: any): Promise<void> {
    const sessionId = String(audioData?.sessionId || '');
    const buffer = audioData?.buffer;
    if (!buffer) {
      return;
    }
    let session = sessionId ? this.audioSessions.get(sessionId) : undefined;
    if (!session) {
      const fallbackSessionId = sessionId || `${robotId}-${Date.now()}`;
      session = {
        robotId,
        sessionId: fallbackSessionId,
        format: 'opus',
        sampleRate: Number(audioData?.sampleRate || 16000),
        channels: Number(audioData?.channels || 1),
        frameDurationMs: Number(audioData?.frameDurationMs || 20),
        chunks: [],
        startedAt: Date.now(),
        lastChunkAt: Date.now(),
      };
      this.audioSessions.set(fallbackSessionId, session);
    }

    try {
      session.chunks.push(Buffer.from(buffer, 'base64'));
      session.lastChunkAt = Date.now();
    } catch (e) {
      this.logger.warn('音频块解码失败', { robotId, sessionId, error: String(e) });
    }
  }

  /**
   * 处理音频结束
   */
  private async handleAudioEnd(robotId: string, audioData: any): Promise<void> {
    const sessionId = String(audioData?.sessionId || '');
    if (!sessionId) {
      this.logger.warn('音频结束缺少sessionId', { robotId });
      return;
    }
    const session = this.audioSessions.get(sessionId);
    if (!session) {
      this.logger.warn('音频会话不存在', { robotId, sessionId });
      return;
    }
    this.audioSessions.delete(sessionId);

    const durationMs = session.frameDurationMs * session.chunks.length;
    const asrStart = Date.now();
    try {
      const wavBuffer = this.decodeOpusChunksToWav(session);
      const text = (await this.asrService.transcribeWav(wavBuffer)) || '';
      const asrTime = Date.now() - asrStart;

      if (!text.trim()) {
        this.logger.info('ASR结果为空', { robotId, sessionId });
        return;
      }

      await this.handleAudioTranscript(robotId, text.trim(), {
        asrTime,
        durationMs,
        sessionId,
      });
    } catch (error: any) {
      this.logger.error('音频处理失败', error, { robotId, sessionId });
      this.sendError(robotId, 'ASR_ERROR', error.message || '语音识别失败', 'business');
    }
  }

  private decodeOpusChunksToWav(session: AudioSession): Buffer {
    const frameSize = Math.floor((session.sampleRate * session.frameDurationMs) / 1000);
    const decoder = new (OpusScript as any)(
      session.sampleRate,
      session.channels,
      (OpusScript as any).Application.VOIP
    );

    const pcmBuffers: Uint8Array[] = [];
    const toUint8Array = (value: any): Uint8Array => {
      if (value instanceof Uint8Array) return value;
      if (value?.buffer) return new Uint8Array(value.buffer);
      return new Uint8Array(value);
    };

    for (const chunk of session.chunks) {
      const decoded = decoder.decode(chunk, frameSize);
      pcmBuffers.push(toUint8Array(decoded));
    }

    const pcmData = Buffer.concat(pcmBuffers);
    return this.buildWavBuffer(pcmData, session.sampleRate, session.channels);
  }

  private buildWavBuffer(pcmData: Buffer, sampleRate: number, channels: number): Buffer {
    const bitsPerSample = 16;
    const byteRate = (sampleRate * channels * bitsPerSample) / 8;
    const blockAlign = (channels * bitsPerSample) / 8;
    const dataSize = pcmData.length;
    const buffer = Buffer.alloc(44 + dataSize);

    buffer.write('RIFF', 0);
    buffer.writeUInt32LE(36 + dataSize, 4);
    buffer.write('WAVE', 8);
    buffer.write('fmt ', 12);
    buffer.writeUInt32LE(16, 16);
    buffer.writeUInt16LE(1, 20);
    buffer.writeUInt16LE(channels, 22);
    buffer.writeUInt32LE(sampleRate, 24);
    buffer.writeUInt32LE(byteRate, 28);
    buffer.writeUInt16LE(blockAlign, 32);
    buffer.writeUInt16LE(bitsPerSample, 34);
    buffer.write('data', 36);
    buffer.writeUInt32LE(dataSize, 40);
    buffer.set(pcmData, 44);

    return buffer;
  }

  private sanitizeTtsText(text: string): string {
    if (!text) return '';
    const emojiRegex = /[\u{1F1E6}-\u{1F1FF}\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]/gu;
    return text.replace(emojiRegex, '').trim();
  }

  private async queueUserText(
    robotId: string,
    text: string,
    ttsOptions: any,
    inputType: 'text' | 'audio',
    audioMeta?: { asrTime: number; durationMs: number; sessionId: string },
    conversationId?: string
  ): Promise<void> {
    const cleaned = String(text || '').trim();
    if (!cleaned) return;
    const existing = this.pendingInputs.get(robotId);
    if (existing) {
      existing.text = `${existing.text} ${cleaned}`.trim();
      if (ttsOptions !== undefined) {
        existing.ttsOptions = ttsOptions;
      }
      existing.inputType = existing.inputType === 'audio' || inputType === 'audio' ? 'audio' : 'text';
      if (inputType === 'audio' && audioMeta) {
        existing.audioMeta = audioMeta;
      }
      this.pendingInputs.set(robotId, existing);
    } else {
      this.pendingInputs.set(robotId, {
        text: cleaned,
        ttsOptions,
        inputType,
        audioMeta,
        conversationId: conversationId || uuidv7(),
      });
    }

    const timer = this.inputMergeTimers.get(robotId);
    if (timer) {
      clearTimeout(timer);
    }
    this.inputMergeTimers.set(
      robotId,
      setTimeout(() => {
        void this.flushUserText(robotId);
      }, this.inputMergeWindowMs)
    );
  }

  private async flushUserText(robotId: string): Promise<void> {
    const pending = this.pendingInputs.get(robotId);
    if (!pending) return;
    this.pendingInputs.delete(robotId);
    const timer = this.inputMergeTimers.get(robotId);
    if (timer) {
      clearTimeout(timer);
      this.inputMergeTimers.delete(robotId);
    }
    if (!this.inputRateLimiter.check(robotId)) {
      this.logger.warn('输入过于频繁', { robotId });
      this.sendError(robotId, 'RATE_LIMITED', '请求过于频繁，请稍后再试', 'business');
      return;
    }
    await this.processUserText(
      robotId,
      pending.text,
      pending.ttsOptions,
      pending.inputType,
      pending.audioMeta,
      pending.conversationId
    );
  }

  /**
   * 处理心跳
   */
  private handleHeartbeat(robotId: string): void {
    this.logger.debug('收到心跳', { robotId });
    // 心跳响应已经通过更新lastActiveAt实现
  }

  /**
   * 处理状态更新
   */
  private handleStatus(robotId: string, msg: any): void {
    const payload = {
      robotId: msg?.robotId ?? robotId,
      seq: msg?.seq,
      timestamp: msg?.timestamp,
      data: msg?.data ?? msg,
    };
    this.logger.debug('收到状态更新', { robotId, payload });
    
    // 更新机器狗状态到数据库
    const robot = this.database.getRobot(payload.robotId || robotId);
    if (robot) {
      try {
        const metadata = robot.metadata ? JSON.parse(robot.metadata) : {};
        metadata.lastStatus = payload.data;
        metadata.lastStatusSeq = payload.seq;
        metadata.lastStatusTime = typeof payload.timestamp === 'number'
          ? new Date(Math.floor(payload.timestamp * 1000)).toISOString()
          : new Date().toISOString();
        this.database.updateRobot(payload.robotId || robotId, { metadata: JSON.stringify(metadata) });
      } catch (error) {
        this.logger.error('保存状态失败', error as Error, { robotId });
      }
    }

    // 广播电量状态到UI
    try {
      const levelRaw = (payload.data && (payload.data.battery ?? payload.data.level)) as any;
      const levelNum = typeof levelRaw === 'number' ? levelRaw : parseFloat(levelRaw);
      if (!Number.isNaN(levelNum)) {
        this.sendToUI(payload.robotId || robotId, {
          type: 'battery_status',
          robotId: payload.robotId || robotId,
          timestamp: Date.now(),
          data: {
            level: Math.round(levelNum),
          },
        }, 'control');
      }
    } catch (err: any) {
      this.logger.error('广播电量状态失败', err, { robotId });
    }

    // 同步广播完整状态到UI（便于前端冗余处理）
    try {
      this.sendToUI(payload.robotId || robotId, {
        type: 'status_update',
        robotId: payload.robotId || robotId,
        timestamp: Date.now(),
        data: payload.data || {},
      }, 'control');
    } catch (err: any) {
      this.logger.error('广播状态更新失败', err, { robotId });
    }
  }

  /**
   * 处理机器人注册
   */
  private async handleRobotRegister(robotId: string, data: any): Promise<void> {
    this.logger.info('收到机器人注册', { robotId, data });
    
    try {
      const { name, model, version, metadata } = data;
      
      // 更新机器狗信息
      const robot = this.database.getRobot(robotId);
      const existingMetadata = robot?.metadata ? JSON.parse(robot.metadata) : {};
      
      this.database.updateRobot(robotId, {
        name: name !== undefined ? (name || robot?.name) : robot?.name,
        model: model !== undefined ? (model || robot?.model) : robot?.model,
        version: version !== undefined ? (version || robot?.version) : robot?.version,
        status: 'online',
        last_connected: new Date(),
        metadata: JSON.stringify({
          ...existingMetadata,
          ...metadata,
          registeredAt: new Date().toISOString(),
        }),
      });
      
      // 更新连接元数据
      const connection = this.robotConnections.get(robotId)?.get('business');
      if (connection) {
        connection.metadata = {
          name: name || connection.metadata.name,
          model: model || connection.metadata.model,
          version: version || connection.metadata.version,
        };
      }
      
      this.logger.info('客户端注册成功', { robotId, name, model });
      
      // 发送注册确认（广播到UI与机器人）
      this.broadcastMessage(robotId, {
        type: 'text_response',
        robotId,
        timestamp: Date.now(),
        data: {
          text: `客户端注册成功！欢迎 ${name || '机器狗'}`,
        },
      }, 'business');
    } catch (error: any) {
      this.logger.error('处理客户端注册失败', error, { robotId });
      this.sendError(robotId, 'REGISTER_ERROR', error.message, 'business');
    }
  }

  /**
   * 处理视频流订阅
   */
  private async handleVideoSubscribe(robotId: string): Promise<void> {
    try {
      // 从数据库获取机器人IP
      const robot = this.database.getRobot(robotId);
      if (!robot || !robot.ip) {
        this.sendError(robotId, 'NO_ROBOT_IP', '机器人IP未配置');
        return;
      }

      const rtspUrl = `rtsp://${robot.ip}:8554/test`;
      const videoService = this.videoStreamManager.subscribe(robotId, rtspUrl, robotId);

      // 监听视频帧并转发给UI客户端
      videoService.on('frame', (frameBuffer: Buffer) => {
        const base64Frame = frameBuffer.toString('base64');
        this.sendToUI(robotId, {
          type: 'video_frame',
          robotId,
          timestamp: Date.now(),
          data: {
            frame: base64Frame,
          },
        }, 'business');
      });

      this.logger.info('视频流订阅成功', { robotId, rtspUrl });
    } catch (error: any) {
      this.logger.error('视频流订阅失败', error, { robotId });
      this.sendError(robotId, 'VIDEO_SUBSCRIBE_ERROR', '视频流订阅失败', 'business');
    }
  }

  /**
   * 处理视频流取消订阅
   */
  private async handleVideoUnsubscribe(robotId: string): Promise<void> {
    try {
      this.videoStreamManager.unsubscribe(robotId, robotId);
      this.logger.info('视频流取消订阅', { robotId });
    } catch (error: any) {
      this.logger.error('视频流取消订阅失败', error, { robotId });
    }
  }

  /**
   * 处理断开连接
   */
  private handleDisconnection(robotId: string, channel: Channel): void {
    const connections = this.robotConnections.get(robotId);
    if (connections) {
      connections.delete(channel);
      if (connections.size === 0) {
        this.robotConnections.delete(robotId);
        this.database.updateRobotStatus(robotId, 'offline');
        this.logger.logWebSocket({
          robotId,
          event: 'disconnected',
        });
      }
    }
  }

  /**
   * 广播消息到机器人和对应的所有UI
   */
  private broadcastMessage(robotId: string, message: ServerMessage, channel: Channel = 'business'): void {
    // 机器人客户端
    this.sendToRobot(robotId, message, channel);
    // 所有UI订阅者
    const uis = this.uiConnections.get(robotId);
    const byChannel = uis?.get(channel);
    if (byChannel && byChannel.size > 0) {
      for (const uiWs of byChannel.values()) {
        try {
          uiWs.send(JSON.stringify(message));
        } catch (error: any) {
          this.logger.error('发送消息到UI失败', error, { robotId });
        }
      }
    }
  }

  /**
   * 发送消息到UI客户端（不包括机器人）
   */
  private sendToUI(robotId: string, message: ServerMessage, channel: Channel = 'business'): void {
    const uis = this.uiConnections.get(robotId);
    const byChannel = uis?.get(channel);
    if (byChannel && byChannel.size > 0) {
      for (const uiWs of byChannel.values()) {
        try {
          uiWs.send(JSON.stringify(message));
        } catch (error: any) {
          this.logger.error('发送消息到UI失败', error, { robotId });
        }
      }
    }
  }

  /**
   * 发送错误消息
   */
  private sendError(robotId: string, code: string, message: string, channel: Channel = 'business'): void {
    this.broadcastMessage(robotId, {
      type: 'error',
      robotId,
      timestamp: Date.now(),
      data: {
        code,
        message,
      },
    }, channel);
  }

  /**
   * 设置心跳检测
   */
  private setupHeartbeat(robotId: string, channel: Channel): void {
    const interval = setInterval(() => {
      const connection = this.robotConnections.get(robotId)?.get(channel);
      if (!connection) {
        clearInterval(interval);
        return;
      }

      // 检查是否超时（5分钟无活动）
      const now = Date.now();
      const lastActive = connection.lastActiveAt.getTime();
      if (now - lastActive > 5 * 60 * 1000) {
        this.logger.warn('连接超时，自动断开', { robotId });
        connection.websocket.close();
        clearInterval(interval);
      }
    }, 60000); // 每分钟检查一次
  }

  /**
   * 获取机器人连接
   */
  getConnections(): Map<string, Map<Channel, RobotConnection>> {
    return this.robotConnections;
  }

  /**
   * 获取在线机器狗数量
   */
  getOnlineCount(): number {
    let count = 0;
    for (const connections of this.robotConnections.values()) {
      if (connections.size > 0) {
        count += 1;
      }
    }
    return count;
  }

  /**
   * 关闭WebSocket服务器
   */
  close(): void {
    this.videoStreamManager.shutdown();
    for (const wss of this.wssMap.values()) {
      wss.close();
    }
    this.logger.info('WebSocket服务已关闭');
  }

  /**
   * 对外暴露：发送消息到机器人客户端
   */
  sendToRobot(robotId: string, message: ServerMessage, channel: Channel = 'business'): boolean {
    const connection = this.robotConnections.get(robotId)?.get(channel);
    if (!connection) {
      this.logger.warn('机器人未连接，无法发送', { robotId, channel });
      return false;
    }
    try {
      connection.websocket.send(JSON.stringify(message));
      return true;
    } catch (error: any) {
      this.logger.error('发送到机器人失败', error, { robotId });
      return false;
    }
  }
}

export default WebSocketService;
