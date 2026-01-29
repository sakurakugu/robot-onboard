import {
  WS_AUDIO_DOWNLOAD_BASE_URL,
  WS_AUDIO_UPLOAD_BASE_URL,
  WS_BIZ_BASE_URL,
  WS_CONTROL_BASE_URL,
  WS_PATH,
} from '@/constants'
import { v7 as uuidv7 } from 'uuid'
import { ref } from 'vue'

// 定义 WebSocket 消息处理函数类型
interface MessageHandler {
  (data: any): void
}

// 函数：使用 WebSocket 连接机器人
export function useWebSocket() {
  const wsBusiness = ref<WebSocket | null>(null)
  const wsControl = ref<WebSocket | null>(null)
  const wsAudioUpload = ref<WebSocket | null>(null)
  const wsAudioDownload = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isControlConnected = ref(false)
  const isAudioUploadConnected = ref(false)
  const isAudioDownloadConnected = ref(false)
  const robotId = ref('')
  const messageHandlers: MessageHandler[] = []

  const generateUUID = (): string => uuidv7() // 统一使用 UUIDv7 生成 robotId

  const buildWsUrl = (server: string, wsPath: string) => {
    const path = wsPath || WS_PATH
    const raw = (server || '').trim()
    if (raw) {
      if (/^wss?:\/\//i.test(raw) || /^https?:\/\//i.test(raw)) {
        const u = new URL(raw)
        const wsScheme = u.protocol === 'https:' ? 'wss:' : 'ws:'
        return `${wsScheme}//${u.host}${path}?robotId=${robotId.value}&role=ui`
      }
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${protocol}//${raw}${path}?robotId=${robotId.value}&role=ui`
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${path}?robotId=${robotId.value}&role=ui`
  }

  // 函数：获取 UI 配置
  const fetchUiConfig = async (): Promise<{
    serverUrl?: string
    wsPath?: string
    wsControlUrl?: string
    wsBusinessUrl?: string
    wsAudioUploadUrl?: string
    wsAudioDownloadUrl?: string
  } | null> => {
    try {
      const res = await fetch('/api/v1/config/ui').then(r => r.json())
      if (res?.success && res.data) {
        const serverUrl: string = res.data.serverUrl || ''
        const wsPath: string = res.data.wsPath || WS_PATH
        const wsControlUrl: string = res.data.wsControlUrl || ''
        const wsBusinessUrl: string = res.data.wsBusinessUrl || ''
        const wsAudioUploadUrl: string = res.data.wsAudioUploadUrl || ''
        const wsAudioDownloadUrl: string = res.data.wsAudioDownloadUrl || ''
        localStorage.setItem('rc_server_url', serverUrl)
        localStorage.setItem('rc_ws_path', wsPath)
        if (wsControlUrl) localStorage.setItem('rc_ws_control_url', wsControlUrl)
        if (wsBusinessUrl) localStorage.setItem('rc_ws_business_url', wsBusinessUrl)
        if (wsAudioUploadUrl) localStorage.setItem('rc_ws_audio_upload_url', wsAudioUploadUrl)
        if (wsAudioDownloadUrl) localStorage.setItem('rc_ws_audio_download_url', wsAudioDownloadUrl)
        return { serverUrl, wsPath, wsControlUrl, wsBusinessUrl, wsAudioUploadUrl, wsAudioDownloadUrl }
      }
    } catch {}
    return null
  }

  const connectSocket = (
    baseUrl: string,
    paths: string[],
    wsRef: { value: WebSocket | null },
    connectedRef: { value: boolean }
  ): Promise<void> => {
    return new Promise((resolve, reject) => {
      let index = 0
      let settled = false
      const attempt = () => {
        const path = paths[index]
        const wsUrl = buildWsUrl(baseUrl, path)
        try {
          wsRef.value = new WebSocket(wsUrl)

          const timeoutMs = 8000
          const timer = setTimeout(() => {
            if (!settled && !connectedRef.value) {
              if (index < paths.length - 1) {
                clearTimeout(timer)
                index += 1
                attempt()
                return
              }
              settled = true
              reject(new Error('连接超时'))
            }
          }, timeoutMs)

          wsRef.value.onopen = () => {
            connectedRef.value = true
            if (!settled) {
              settled = true
              clearTimeout(timer)
              resolve()
            }
          }

          wsRef.value.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data)
              messageHandlers.forEach((handler) => handler(data))
            } catch (error) {}
          }

          wsRef.value.onerror = () => {}

          wsRef.value.onclose = () => {
            connectedRef.value = false
            if (!settled) {
              if (index < paths.length - 1) {
                clearTimeout(timer)
                index += 1
                attempt()
                return
              }
              settled = true
              clearTimeout(timer)
              reject(new Error('连接被关闭'))
            }
          }
        } catch (error) {
          if (index < paths.length - 1) {
            index += 1
            attempt()
            return
          }
          reject(error as any)
        }
      }
      attempt()
    })
  }

  const connect = (): Promise<void> => {
    return new Promise(async (resolve, reject) => {
      try {
        if (!robotId.value) {
          robotId.value = generateUUID()
        }

        let savedServer = localStorage.getItem('rc_server_url') || ''
        let savedPath = localStorage.getItem('rc_ws_path') || WS_PATH
        let savedControlUrl = localStorage.getItem('rc_ws_control_url') || ''
        let savedBusinessUrl = localStorage.getItem('rc_ws_business_url') || ''
        let savedAudioUploadUrl = localStorage.getItem('rc_ws_audio_upload_url') || ''
        let savedAudioDownloadUrl = localStorage.getItem('rc_ws_audio_download_url') || ''

        if (!savedServer || !localStorage.getItem('rc_ws_path') || !savedBusinessUrl || !savedControlUrl) {
          const cfg = await fetchUiConfig()
          if (cfg) {
            savedServer = cfg.serverUrl || savedServer
            savedPath = cfg.wsPath || savedPath
            savedControlUrl = cfg.wsControlUrl || savedControlUrl
            savedBusinessUrl = cfg.wsBusinessUrl || savedBusinessUrl
            savedAudioUploadUrl = cfg.wsAudioUploadUrl || savedAudioUploadUrl
            savedAudioDownloadUrl = cfg.wsAudioDownloadUrl || savedAudioDownloadUrl
          }
        }

        const candidates: string[] = []
        const p = (savedPath || '').trim()
        if (p) candidates.push(p)
        if (!candidates.includes('/api/v1/conversation/connect')) candidates.push('/api/v1/conversation/connect')
        if (!candidates.includes('/api/conversation/connect')) candidates.push('/api/conversation/connect')

        const businessBase = savedBusinessUrl || WS_BIZ_BASE_URL
        const controlBase = savedControlUrl || WS_CONTROL_BASE_URL
        const audioUploadBase = savedAudioUploadUrl || WS_AUDIO_UPLOAD_BASE_URL
        const audioDownloadBase = savedAudioDownloadUrl || WS_AUDIO_DOWNLOAD_BASE_URL

        await connectSocket(businessBase, candidates, wsBusiness, isConnected)
        connectSocket(controlBase, candidates, wsControl, isControlConnected).catch(() => {})
        connectSocket(audioUploadBase, candidates, wsAudioUpload, isAudioUploadConnected).catch(() => {})
        connectSocket(audioDownloadBase, candidates, wsAudioDownload, isAudioDownloadConnected).catch(() => {})
        resolve()
      } catch (error) {
        reject(error)
      }
    })
  }

  const disconnect = () => {
    if (wsBusiness.value) {
      wsBusiness.value.close()
      wsBusiness.value = null
    }
    if (wsControl.value) {
      wsControl.value.close()
      wsControl.value = null
    }
    if (wsAudioUpload.value) {
      wsAudioUpload.value.close()
      wsAudioUpload.value = null
    }
    if (wsAudioDownload.value) {
      wsAudioDownload.value.close()
      wsAudioDownload.value = null
    }
    isConnected.value = false
    isControlConnected.value = false
    isAudioDownloadConnected.value = false
  }

  const sendText = (text: string) => {
    if (!wsBusiness.value || !isConnected.value) {
      console.error('业务通道未连接')
      return
    }

    const message = {
      type: 'text_input',
      robotId: robotId.value,
      timestamp: Date.now(),
      data: {
        text,
      },
    }

    wsBusiness.value.send(JSON.stringify(message))
  }

  const onMessage = (handler: MessageHandler) => {
    messageHandlers.push(handler)
  }

  const sendTextWithTTS = (text: string, ttsOptions: any) => {
    if (!wsBusiness.value || !isConnected.value) {
      console.error('业务通道未连接')
      return
    }
    const message = {
      type: 'text_input',
      robotId: robotId.value,
      timestamp: Date.now(),
      data: {
        text,
        ttsOptions,
      },
    }
    wsBusiness.value.send(JSON.stringify(message))
  }

  const sendTTS = (text: string, ttsOptions: any) => {
    if (!wsBusiness.value || !isConnected.value) {
      console.error('业务通道未连接')
      return
    }
    const message = {
      type: 'tts_input',
      robotId: robotId.value,
      timestamp: Date.now(),
      data: {
        text,
        ttsOptions,
      },
    }
    wsBusiness.value.send(JSON.stringify(message))
  }

  const sendMessage = (message: any) => {
    const type = message?.type
    if (type === 'control_input' || type === 'status' || type === 'heartbeat') {
      if (!wsControl.value || !isControlConnected.value) {
        console.error('控制通道未连接')
        return
      }
      wsControl.value.send(JSON.stringify(message))
      return
    }

    if (type === 'audio_chunk') {
      if (!wsAudioUpload.value) {
        console.error('音频上传通道未连接')
        return
      }
      wsAudioUpload.value.send(JSON.stringify(message))
      return
    }

    if (!wsBusiness.value || !isConnected.value) {
      console.error('业务通道未连接')
      return
    }
    wsBusiness.value.send(JSON.stringify(message))
  }

  return {
    ws: wsBusiness,
    isConnected,
    isControlConnected,
    isAudioDownloadConnected,
    robotId,
    connect,
    disconnect,
    sendText,
    sendTextWithTTS,
    sendTTS,
    sendMessage,
    onMessage,
  }
}
