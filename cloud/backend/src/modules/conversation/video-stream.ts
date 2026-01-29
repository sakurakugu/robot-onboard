import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';

export interface VideoStreamOptions {
  rtspUrl: string;
  width?: number;
  height?: number;
  fps?: number;
  quality?: number; // JPEG quality 1-100
}

export class VideoStreamService extends EventEmitter {
  private gstProcess: ChildProcess | null = null;
  private isRunning = false;
  private frameBuffer: Buffer[] = [];
  private options: Required<VideoStreamOptions>;

  constructor(options: VideoStreamOptions) {
    super();
    this.options = {
      rtspUrl: options.rtspUrl,
      width: options.width || 640,
      height: options.height || 480,
      fps: options.fps || 15,
      quality: options.quality || 75,
    };
  }

  start(): void {
    if (this.isRunning) {
      return;
    }

    const { rtspUrl, width, height, fps, quality } = this.options;

    // GStreamer pipeline for low-latency RTSP to JPEG
    // 使用TCP传输、零延迟、最小缓冲
    const pipeline = [
      'rtspsrc',
      `location=${rtspUrl}`,
      'latency=0',
      'protocols=tcp',
      '!',
      'rtph264depay',
      '!',
      'h264parse',
      '!',
      'avdec_h264',
      'max-threads=2',
      '!',
      'videoscale',
      '!',
      `video/x-raw,width=${width},height=${height}`,
      '!',
      'videoconvert',
      '!',
      'videorate',
      `drop-only=true`,
      '!',
      `video/x-raw,framerate=${fps}/1`,
      '!',
      'jpegenc',
      `quality=${quality}`,
      '!',
      'fdsink',
      'fd=1',
      'sync=false',
    ];

    this.gstProcess = spawn('gst-launch-1.0', pipeline, {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    this.isRunning = true;

    // JPEG marker detection
    let currentFrame: Uint8Array[] = [];
    let inJpeg = false;

    this.gstProcess.stdout?.on('data', (chunk: Buffer) => {
      for (let i = 0; i < chunk.length; i++) {
        // JPEG start marker: 0xFF 0xD8
        if (chunk[i] === 0xff && chunk[i + 1] === 0xd8) {
          inJpeg = true;
          currentFrame = [];
        }

        if (inJpeg) {
          currentFrame.push(Uint8Array.from([chunk[i]]));
        }

        // JPEG end marker: 0xFF 0xD9
        if (chunk[i] === 0xff && chunk[i + 1] === 0xd9 && inJpeg) {
          currentFrame.push(Uint8Array.from([chunk[i + 1]]));
          const frame = Buffer.concat(currentFrame);
          this.emit('frame', frame);
          inJpeg = false;
          currentFrame = [];
          i++; // Skip next byte
        }
      }
    });

    this.gstProcess.stderr?.on('data', (data: Buffer) => {
      const msg = data.toString();
      // 只记录错误，忽略调试信息
      if (msg.includes('ERROR') || msg.includes('WARNING')) {
        console.error('[VideoStream] GStreamer:', msg);
      }
    });

    this.gstProcess.on('error', (err) => {
      console.error('[VideoStream] Process error:', err);
      this.emit('error', err);
      this.isRunning = false;
    });

    this.gstProcess.on('exit', (code) => {
      console.log('[VideoStream] Process exited with code:', code);
      this.isRunning = false;
      this.gstProcess = null;
      this.emit('exit', code);
    });

    console.log('[VideoStream] Started streaming from', rtspUrl);
  }

  stop(): void {
    if (this.gstProcess) {
      this.gstProcess.kill('SIGTERM');
      this.gstProcess = null;
    }
    this.isRunning = false;
    this.frameBuffer = [];
    console.log('[VideoStream] Stopped');
  }

  getStatus(): boolean {
    return this.isRunning;
  }
}

// 管理多个视频流
export class VideoStreamManager {
  private streams: Map<string, { service: VideoStreamService; subscribers: Set<string> }> = new Map();

  subscribe(robotId: string, rtspUrl: string, subscriberId: string): VideoStreamService {
    let streamData = this.streams.get(robotId);

    if (!streamData) {
      const service = new VideoStreamService({
        rtspUrl,
        width: 640,
        height: 480,
        fps: 15,
        quality: 75,
      });

      streamData = {
        service,
        subscribers: new Set(),
      };

      this.streams.set(robotId, streamData);

      // Auto-cleanup on error or exit
      service.on('exit', () => {
        this.cleanup(robotId);
      });
    }

    streamData.subscribers.add(subscriberId);

    // 如果还没启动，现在启动
    if (!streamData.service.getStatus()) {
      streamData.service.start();
    }

    return streamData.service;
  }

  unsubscribe(robotId: string, subscriberId: string): void {
    const streamData = this.streams.get(robotId);
    if (!streamData) return;

    streamData.subscribers.delete(subscriberId);

    // 如果没有订阅者了，停止流
    if (streamData.subscribers.size === 0) {
      streamData.service.stop();
      this.streams.delete(robotId);
    }
  }

  private cleanup(robotId: string): void {
    const streamData = this.streams.get(robotId);
    if (streamData) {
      streamData.service.stop();
      this.streams.delete(robotId);
    }
  }

  shutdown(): void {
    for (const [robotId, streamData] of this.streams.entries()) {
      streamData.service.stop();
    }
    this.streams.clear();
  }
}
