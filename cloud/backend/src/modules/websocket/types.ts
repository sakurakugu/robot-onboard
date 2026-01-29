// WebSocket消息类型定义

export interface RobotConnection {
  robotId: string;
  websocket: any;
  connectedAt: Date;
  lastActiveAt: Date;
  channel?: 'control' | 'business' | 'audio_upload' | 'audio_download';
  metadata: {
    name?: string;
    model?: string;
    version?: string;
  };
}

// 音频相关
export interface AudioChunk {
  format: 'opus' | 'pcm' | 'mp3';
  sampleRate: 16000 | 48000;
  channels: 1 | 2;
  sessionId?: string;
  seq?: number;
  frameDurationMs?: number;
  buffer: string; // base64编码的音频数据
}

export interface AudioStart {
  format: 'opus';
  sampleRate: 16000 | 48000;
  channels: 1 | 2;
  frameDurationMs: number;
  sessionId: string;
}

export interface AudioEnd {
  sessionId: string;
  reason?: 'silence' | 'max_length' | 'manual' | 'error';
}

export interface AudioResponse {
  format: 'opus' | 'mp3';
  buffer: string; // base64编码
  duration: number;
}

// 客户端消息
export type ClientMessage =
  | AudioStartMessage
  | AudioChunkMessage
  | AudioEndMessage
  | TextInputMessage
  | HeartbeatMessage
  | StatusMessage
  | ClientRegisterMessage
  | TTSInputMessage
  | VideoSubscribeMessage
  | VideoUnsubscribeMessage
  | ActionInputMessage
  | ControlInputMessage
  | AudioControlMessage;

export interface AudioStartMessage {
  type: 'audio_start';
  robotId: string;
  timestamp: number;
  data: AudioStart;
}

export interface AudioChunkMessage {
  type: 'audio_chunk';
  robotId: string;
  timestamp: number;
  data: AudioChunk;
}

export interface AudioEndMessage {
  type: 'audio_end';
  robotId: string;
  timestamp: number;
  data: AudioEnd;
}

export interface TextInputMessage {
  type: 'text_input';
  robotId: string;
  timestamp: number;
  data: {
    text: string;
    context?: string;
    ttsOptions?: TTSOptions;
    conversationId?: string;
  };
}

export interface HeartbeatMessage {
  type: 'heartbeat';
  robotId: string;
  timestamp: number;
  data?: any;
}

export interface StatusMessage {
  type: 'status';
  robotId: string;
  timestamp: number;
  data: {
    battery?: number;
    temperature?: number;
    position?: string;
  };
}

export interface ClientRegisterMessage {
  type: 'robot_register';
  robotId: string;
  timestamp: number;
  data: {
    name?: string;
    model?: string;
    version?: string;
    metadata?: any;
  };
}

export interface TTSInputMessage {
  type: 'tts_input';
  robotId: string;
  timestamp: number;
  data: {
    text: string;
    ttsOptions?: TTSOptions;
    conversationId?: string;
  };
}

export interface VideoSubscribeMessage {
  type: 'video_subscribe';
  robotId?: string;
  timestamp?: number;
}

export interface VideoUnsubscribeMessage {
  type: 'video_unsubscribe';
  robotId?: string;
  timestamp?: number;
}

export interface ActionInputMessage {
  type: 'action_input';
  robotId: string;
  timestamp: number;
  data: {
    action: string;
    parameters?: Record<string, any>;
  };
}

export interface ControlInputMessage {
  type: 'control_input';
  robotId: string;
  timestamp: number;
  data: {
    command: 'joystick' | 'joystick_stop' | 'estop';
    channel?: 'move' | 'look' | 'pose';
    mode?: 'move' | 'pose';
    x?: number;
    y?: number;
    speed?: number;
  };
}

export interface AudioControlMessage {
  type: 'audio_control';
  robotId: string;
  timestamp: number;
  data: {
    enabled: boolean;
  };
}

// 服务端消息
export type ServerMessage =
  | AudioResponseMessage
  | ActionCommandMessage
  | ControlCommandMessage
  | TextResponseMessage
  | VideoFrameMessage
  | ErrorMessage
  | BatteryStatusMessage
  | StatusUpdateMessage
  | AudioControlCommandMessage
  | AsrTranscriptMessage;

export interface AudioResponseMessage {
  type: 'audio_response';
  robotId: string;
  timestamp: number;
  conversationId?: string;
  data: AudioResponse;
}

export interface ActionCommandMessage {
  type: 'action_command';
  robotId: string;
  timestamp: number;
  conversationId?: string;
  data: ActionCommand;
}

export interface ControlCommandMessage {
  type: 'control_command';
  robotId: string;
  timestamp: number;
  data: {
    command: 'joystick' | 'joystick_stop' | 'estop';
    channel?: 'move' | 'look' | 'pose';
    mode?: 'move' | 'pose';
    x?: number;
    y?: number;
    speed?: number;
  };
}

export interface TextResponseMessage {
  type: 'text_response';
  robotId: string;
  timestamp: number;
  conversationId?: string;
  data: {
    text: string;
    noTTS?: boolean; // 标记是否需要生成TTS（动作响应不需要）
    actions?: string[];
  };
}

export interface ErrorMessage {
  type: 'error';
  robotId: string;
  timestamp: number;
  data: {
    code: string;
    message: string;
    details?: any;
  };
}

export interface VideoFrameMessage {
  type: 'video_frame';
  robotId: string;
  timestamp: number;
  data: {
    frame: string; // base64 encoded JPEG
  };
}

export interface BatteryStatusMessage {
  type: 'battery_status';
  robotId: string;
  timestamp: number;
  data: {
    level: number;
  };
}

export interface StatusUpdateMessage {
  type: 'status_update';
  robotId: string;
  timestamp: number;
  data: {
    battery?: number;
    temperature?: number;
    position?: string;
    [key: string]: any;
  };
}

export interface AudioControlCommandMessage {
  type: 'audio_control';
  robotId: string;
  timestamp: number;
  data: {
    enabled: boolean;
    source?: 'ui' | 'system';
  };
}

export interface AsrTranscriptMessage {
  type: 'asr_transcript';
  robotId: string;
  timestamp: number;
  data: {
    text: string;
    sessionId?: string;
    durationMs?: number;
    asrTime?: number;
  };
}

// 引用conversation模块的类型
import type { ActionCommand, TTSOptions } from '../conversation/types';
