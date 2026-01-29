<template>
  <div class="robot-operation">
    <!-- Top Toolbar -->
    <div v-if="!props.embedded" class="top-bar">
      <div class="left-tools">
        <el-button link @click="goBack">
          <el-icon :size="20"><Back /></el-icon>
        </el-button>
        
        <el-divider direction="vertical" />
        
        <el-switch
          v-model="controlMode"
          active-text="姿态"
          inactive-text="移动"
          active-value="pose"
          inactive-value="move"
          inline-prompt
          style="--el-switch-on-color: #13ce66; --el-switch-off-color: #409eff"
        />

        <el-divider direction="vertical" />

        <el-select 
          v-model="selectedUuid" 
          placeholder="选择机器人" 
          style="width: 160px" 
          size="small"
          filterable
        >
          <el-option
            v-for="r in robots"
            :key="r.uuid"
            :label="r.name || r.uuid"
            :value="r.uuid"
          />
        </el-select>

        <el-divider direction="vertical" />
        
        <el-popover placement="bottom" :width="200" trigger="click">
          <template #reference>
            <el-button size="small" text>
              速度: {{ speed }}
            </el-button>
          </template>
          <div style="display: flex; align-items: center; gap: 10px; padding: 0 10px;">
            <span style="white-space: nowrap;">速度</span>
            <el-slider v-model="speed" :min="1" :max="10" size="small" />
          </div>
        </el-popover>

        <el-divider direction="vertical" />

        <el-switch
          v-model="showVideo"
          active-text="视频"
          inline-prompt
          @change="toggleVideo"
        />

        <el-divider direction="vertical" />

        <el-button type="danger" size="small" @click="emergencyStop" class="estop-btn" :icon="SwitchButton">
          急停
        </el-button>
      </div>

      <div class="right-info">
        <div class="info-item">
          <el-icon><Bot /></el-icon>
          <span>{{ robotBattery }}%</span>
        </div>
        <div class="info-item" v-if="phoneBattery !== null">
          <el-icon><Cellphone /></el-icon>
          <span>{{ phoneBattery }}%</span>
        </div>
        <div class="info-item time-display">
          <span>{{ currentTime }}</span>
        </div>
        <div class="info-item" style="position: relative;">
          <el-button circle :icon="Setting" @click="openSettings" />
          <div v-if="hasUpdate" class="setting-dot"></div>
        </div>
      </div>
    </div>

    

    <!-- Middle Video Area -->
    <div class="video-area">
      <div class="video-container" v-if="showVideo && currentVideoFrame">
        <img :src="currentVideoFrame" class="video-feed" alt="Live Feed" draggable="false" @dragstart.prevent  @pointerdown.prevent/>
      </div>
      <div class="video-placeholder" v-else>
        <el-icon :size="60" color="#909399"><VideoCamera /></el-icon>
        <p>{{ showVideo ? '等待视频信号...' : '视频已关闭' }}</p>
      </div>

      <!-- Floating Controls Layer -->
      <div
        ref="floatingLayerRef"
        class="floating-layer"
        :class="{ 'is-editing': layoutEditMode }"
      >
        <div
          class="floating-item"
          :style="getControlStyle('chatToggle')"
          @pointerdown="startDrag('chatToggle', $event)"
        >
          <el-button
            class="chat-toggle-btn"
            circle
            :icon="ChatLineSquare"
            @click="onChatClick"
          />
        </div>

        <div
          class="floating-item"
          :style="getControlStyle('micToggle')"
          @pointerdown="startDrag('micToggle', $event)"
        >
          <el-button
            class="mic-toggle-btn"
            circle
            :icon="micEnabled ? Mic : MicOff"
            @click="toggleMic"
          />
        </div>

        <div
          class="floating-item"
          :style="getControlStyle('leftJoystick')"
          @pointerdown="startDrag('leftJoystick', $event)"
        >
          <JoystickPad
            class="joystick-pad"
            :class="{ 'is-disabled': layoutEditMode || (controlMode === 'pose' && !twoLegStandActive) }"
            @change="onMoveJoystick"
            @end="onMoveJoystickEnd"
          />
        </div>

        <div
          v-for="btn in actionButtons"
          :key="btn.id"
          class="floating-item"
          :style="getControlStyle(btn.id)"
          @pointerdown="startDrag(btn.id, $event)"
        >
          <ActionButton
            :label="btn.label"
            :title="btn.title"
            :disabled="layoutEditMode"
            @click="sendAction(btn.action)"
          />
        </div>

        <div
          class="floating-item"
          :style="getControlStyle('rightJoystick')"
          @pointerdown="startDrag('rightJoystick', $event)"
        >
          <JoystickPad
            class="joystick-pad"
            :class="{ 'is-disabled': layoutEditMode || rightJoystickDisabled }"
            @change="onLookJoystick"
            @end="onLookJoystickEnd"
          />
        </div>
      </div>
    </div>
    
    <el-drawer 
      v-model="showChatPanel" 
      direction="rtl" 
      size="50%" 
      :with-header="false"
      :append-to-body="false"
      class="robot-agent-drawer"
    >
      <div class="chat-drawer">
        <div class="chat-drawer__header">
          <el-button link @click="closeChatPanel">
            <el-icon :size="20"><Back /></el-icon>
          </el-button>
          <div class="chat-drawer__title">对话</div>
          <div class="chat-drawer__spacer"></div>
        </div>
        <div class="chat-drawer__body">
          <ChatView :robotUuid="selectedUuid" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import JoystickPad from '@/components/JoystickPad.vue'
import { useWebSocket } from '@/composables/useWebSocket'
import ChatView from '@/modules/conversation/views/ChatView.vue'
import ActionButton from '@/modules/robot/components/ActionButton.vue'
import {
  Back,
  Cellphone,
  ChatLineSquare,
  Setting,
  SwitchButton,
  VideoCamera
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { Bot, Mic, MicOff } from 'lucide-vue-next'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps<{ embedded?: boolean; robotUuid?: string }>()
const router = useRouter()

// WebSocket & Robot State
const {
  isConnected,
  isControlConnected,
  robotId,
  connect: wsConnect,
  disconnect: wsDisconnect,
  sendMessage: wsSendMessage,
  onMessage,
} = useWebSocket()

// UI State
const controlMode = ref('move')
const selectedUuid = ref('')
const speed = ref(5)
const showVideo = ref(true)
const robotBattery = ref(85) // Mock value
const phoneBattery = ref<number | null>(null) // Mock value, null to hide
const currentTime = ref('')
const currentVideoFrame = ref<string | null>(null)
const hasUpdate = ref(true)
const showChatPanel = ref(false)
const layoutEditMode = ref(false)
const floatingLayerRef = ref<HTMLDivElement | null>(null)
const micEnabled = ref(true)
const twoLegStandActive = ref(false)
const rightJoystickDisabled = ref(false)

watch(twoLegStandActive, (val) => {
  rightJoystickDisabled.value = val
})

// Robots List (Mock or Fetch)
type RobotItem = { uuid: string; name?: string; status?: string }
const robots = ref<RobotItem[]>([])

type ControlLayout = Record<string, { x: number; y: number }>

const defaultControlLayout: ControlLayout = {
  chatToggle: { x: 92, y: 12 },
  micToggle: { x: 92, y: 24 },
  leftJoystick: { x: 15, y: 80 },
  rightJoystick: { x: 85, y: 80 },
  action_stand_up: { x: 34, y: 78 },
  action_sit_down: { x: 44, y: 78 },
  action_front_jump: { x: 54, y: 78 },
  action_jump: { x: 64, y: 78 },
  action_backflip: { x: 36, y: 88 },
  action_two_leg_stand: { x: 50, y: 88 },
  action_shake_hand: { x: 64, y: 88 },
}

const controlLayout = ref<ControlLayout>({ ...defaultControlLayout })
const originalLayoutSnapshot = ref<ControlLayout>({ ...defaultControlLayout })

const actionButtons = [
  { id: 'action_stand_up', action: 'stand_up', label: '起立', title: '起立' },
  { id: 'action_sit_down', action: 'sit_down', label: '趴下', title: '趴下' },
  { id: 'action_front_jump', action: 'front_jump', label: '向前跳', title: '向前跳' },
  { id: 'action_jump', action: 'jump', label: '向上跳', title: '向上跳' },
  { id: 'action_backflip', action: 'backflip', label: '后空翻', title: '后空翻' },
  { id: 'action_two_leg_stand', action: 'two_leg_stand', label: '双腿站立', title: '双腿站立' },
  { id: 'action_shake_hand', action: 'shake_hand', label: '打招呼', title: '打招呼' },
]

// Timer for clock
let timeInterval: any = null

// Functions
const goBack = () => {
  router.back()
}

const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const emergencyStop = () => {
  if (!isControlConnected.value) {
    ElMessage.warning('控制通道未连接')
    return
  }
  ElMessage.error('触发急停！')
  wsSendMessage({
    type: 'control_input',
    robotId: robotId.value,
    timestamp: Date.now(),
    data: { command: 'estop' },
  })
}

const toggleVideo = (val: boolean) => {
  if (val) {
    if (isConnected.value) {
      wsSendMessage({ type: 'video_subscribe' })
    }
  } else {
    if (isConnected.value) {
      wsSendMessage({ type: 'video_unsubscribe' })
    }
    currentVideoFrame.value = null
  }
}

const openChatPanel = () => {
  showChatPanel.value = true
}

const closeChatPanel = () => {
  showChatPanel.value = false
}

const onChatClick = () => {
  if (layoutEditMode.value) return
  openChatPanel()
}

const toggleMic = () => {
  if (layoutEditMode.value) return
  if (!isConnected.value) {
    ElMessage.warning('未连接机器人')
    return
  }
  micEnabled.value = !micEnabled.value
  wsSendMessage({
    type: 'audio_control',
    robotId: robotId.value,
    timestamp: Date.now(),
    data: { enabled: micEnabled.value },
  })
}

const sendAction = (action: string) => {
  if (layoutEditMode.value) return
  if (!isConnected.value) {
    ElMessage.warning('未连接机器人')
    return
  }
  if (action === 'two_leg_stand') {
    const nextAction = twoLegStandActive.value ? 'cancel_two_leg_stand' : 'two_leg_stand'
    twoLegStandActive.value = !twoLegStandActive.value
    ElMessage.success(twoLegStandActive.value ? '进入双腿站立' : '退出双腿站立')
    wsSendMessage({
      type: 'action_input',
      robotId: robotId.value,
      timestamp: Date.now(),
      data: { action: nextAction },
    })
    return
  }
  ElMessage.success(`发送动作: ${action}`)
  wsSendMessage({
    type: 'action_input',
    robotId: robotId.value,
    timestamp: Date.now(),
    data: { action },
  })
}

type JoystickPayload = { x: number; y: number }

const sendJoystick = (channel: 'move' | 'look' | 'pose', payload: JoystickPayload) => {
  if (layoutEditMode.value) return
  if (!isControlConnected.value) return
  const effectiveMode = twoLegStandActive.value ? 'two_leg' : controlMode.value
  wsSendMessage({
    type: 'control_input',
    robotId: robotId.value,
    timestamp: Date.now(),
    data: {
      command: 'joystick',
      channel,
      x: payload.x,
      y: payload.y,
      speed: speed.value,
      mode: effectiveMode,
    },
  })
}

const stopJoystick = (channel: 'move' | 'look' | 'pose', modeOverride?: 'move' | 'pose') => {
  if (layoutEditMode.value) return
  if (!isControlConnected.value) return
  const effectiveMode = twoLegStandActive.value ? 'two_leg' : (modeOverride || controlMode.value)
  wsSendMessage({
    type: 'control_input',
    robotId: robotId.value,
    timestamp: Date.now(),
    data: {
      command: 'joystick_stop',
      channel,
      mode: effectiveMode,
    },
  })
}

const onMoveJoystick = (payload: JoystickPayload) => {
  if (controlMode.value === 'pose' && !twoLegStandActive.value) return
  sendJoystick('move', payload)
}

const onLookJoystick = (payload: JoystickPayload) => {
  if (rightJoystickDisabled.value) return
  if (controlMode.value === 'pose') {
    sendJoystick('pose', payload)
    return
  }
  sendJoystick('look', payload)
}

const onMoveJoystickEnd = () => {
  if (controlMode.value === 'pose' && !twoLegStandActive.value) return
  stopJoystick('move')
}

const onLookJoystickEnd = () => {
  if (rightJoystickDisabled.value) return
  if (controlMode.value === 'pose') {
    stopJoystick('pose')
    return
  }
  stopJoystick('look')
}

const openSettings = () => {
  if (!selectedUuid.value) {
    ElMessage.warning('请先选择机器人')
    return
  }
  router.push({ path: '/operation/edit', query: { robotUuid: selectedUuid.value, tab: 'basic' } })
}

const clampPercent = (value: number) => Math.min(100, Math.max(0, value))

const getControlStyle = (id: string) => {
  const pos = controlLayout.value[id] || defaultControlLayout[id]
  const x = pos?.x ?? 50
  const y = pos?.y ?? 50
  return {
    left: `${x}%`,
    top: `${y}%`,
  }
}

const startDrag = (id: string, event: PointerEvent) => {
  if (!layoutEditMode.value) return
  const layer = floatingLayerRef.value
  if (!layer) return
  event.preventDefault()
  const rect = layer.getBoundingClientRect()

  const updatePosition = (ev: PointerEvent) => {
    const x = clampPercent(((ev.clientX - rect.left) / rect.width) * 100)
    const y = clampPercent(((ev.clientY - rect.top) / rect.height) * 100)
    controlLayout.value = {
      ...controlLayout.value,
      [id]: { x, y },
    }
  }

  const onMove = (ev: PointerEvent) => updatePosition(ev)
  const onUp = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }

  updatePosition(event)
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

const startLayoutEdit = () => {
  layoutEditMode.value = true
  originalLayoutSnapshot.value = JSON.parse(JSON.stringify(controlLayout.value))
}

const cancelLayoutEdit = () => {
  controlLayout.value = JSON.parse(JSON.stringify(originalLayoutSnapshot.value))
  layoutEditMode.value = false
}

const saveLayout = async () => {
  try {
    await fetch('/api/v1/config/ui', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ controlLayout: controlLayout.value }),
    })
    ElMessage.success('布局已保存')
    layoutEditMode.value = false
  } catch (e) {
    ElMessage.error('布局保存失败')
  }
}


// Fetch robots
const fetchRobots = async () => {
  try {
    const res = await fetch('/api/v1/robots')
    const json = await res.json()
    const list: any[] = json?.data?.robots || []
    robots.value = list.map((r) => ({ uuid: r.uuid, name: r.name || '', status: r.status || 'offline' }))
    if (robots.value.length > 0 && !selectedUuid.value && !props.robotUuid) {
      selectedUuid.value = robots.value[0].uuid
    }
  } catch (e) {
    console.error(e)
  }
}

const fetchControlLayout = async () => {
  try {
    const res = await fetch('/api/v1/config/ui')
    const json = await res.json()
    const layout = json?.data?.controlLayout
    if (layout && typeof layout === 'object') {
      const next: ControlLayout = { ...defaultControlLayout }
      for (const key of Object.keys(layout)) {
        const item = layout[key]
        const x = Number(item?.x)
        const y = Number(item?.y)
        if (!Number.isNaN(x) && !Number.isNaN(y)) {
          next[key] = { x: clampPercent(x), y: clampPercent(y) }
        }
      }
      controlLayout.value = next
      originalLayoutSnapshot.value = JSON.parse(JSON.stringify(next))
    }
  } catch (e) {
    console.error('加载布局失败', e)
  }
}

// WebSocket Message Handling
onMessage((data) => {
  if (data.type === 'video_frame') {
    try {
      const frameBase64 = data.data.frame
      currentVideoFrame.value = `data:image/jpeg;base64,${frameBase64}`
    } catch (error) {
      console.error('Video frame error', error)
    }
  } else if (data.type === 'battery_status') {
    robotBattery.value = data.data.level
  } else if (data.type === 'status_update') {
    const level = typeof data.data?.battery === 'number' ? data.data.battery : Number(data.data?.battery)
    if (!Number.isNaN(level)) {
      robotBattery.value = Math.round(level)
    }
  } else if (data.type === 'error') {
    const msg = data.data?.message || '发生错误'
    if (data.data?.code === 'NO_ROBOT_IP') {
      ElMessage.warning(msg)
    } else {
      ElMessage.error(msg)
    }
  }
})

// Watchers
watch(controlMode, (val) => {
  if (val === 'pose') {
    stopJoystick('move', 'move')
    stopJoystick('look', 'move')
  } else {
    stopJoystick('pose', 'pose')
  }
})

watch(selectedUuid, async (val) => {
  if (val) {
    twoLegStandActive.value = false
    if (isConnected.value) {
      wsDisconnect()
    }
    robotId.value = val
    try {
      await wsConnect()
      if (showVideo.value) {
        wsSendMessage({ type: 'video_subscribe' })
      }
    } catch (e) {
      ElMessage.error('连接失败，请检查后端服务或网络')
    }
  }
})

watch(
  () => props.robotUuid,
  (val) => {
    if (val && val !== selectedUuid.value) {
      selectedUuid.value = val
    }
  },
  { immediate: true }
)

// Lifecycle
onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  
  // Try to get phone battery if API available (Mock for now)
  if ('getBattery' in navigator) {
    (navigator as any).getBattery().then((battery: any) => {
      phoneBattery.value = Math.round(battery.level * 100)
    })
  }

  fetchRobots()
  fetchControlLayout()
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  wsDisconnect()
})

const setLayoutEditMode = (val: boolean) => {
  if (val) {
    startLayoutEdit()
  } else {
    cancelLayoutEdit()
  }
}

defineExpose({
  startLayoutEdit,
  cancelLayoutEdit,
  saveLayout,
  setLayoutEditMode,
})
</script>

<style>
/* 全局禁止页面滚动 */
html, body, #app {
  overflow: hidden !important;
  height: 100%;
  width: 100%;
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

*, *::before, *::after {
  box-sizing: border-box;
}
</style>

<style scoped>
.robot-operation {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background-color: #1a1a1a;
  color: #fff;
  overflow: hidden;
  position: relative;
  box-sizing: border-box;
}

.top-bar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background-color: #2c2c2c;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
  height: 50px;
  z-index: 100;
  box-sizing: border-box;
  width: 100%;
  overflow: hidden;
}

.left-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.right-info {
  display: flex;
  align-items: center;
  gap: 20px;
  font-size: 14px;
}

.video-area {
  flex: 1;
  min-height: 0;
  background-color: #000;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: hidden;
  width: 100%;
}

.video-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.video-feed {
  width: 100%;
  height: 100%;
  object-fit: cover;
  user-select: none;
  -webkit-user-drag: none;
  touch-action: none;
}

.video-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #909399;
}

.floating-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  box-sizing: border-box;
}

.floating-layer.is-editing {
  pointer-events: auto;
}

.floating-item {
  position: absolute;
  transform: translate(-50%, -50%);
  pointer-events: auto;
}

.floating-layer.is-editing .floating-item {
  outline: 1px dashed rgba(255, 255, 255, 0.6);
  border-radius: 8px;
  padding: 4px;
  cursor: move;
}

.chat-toggle-btn {
  width: 56px;
  height: 56px;
  font-size: 24px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.mic-toggle-btn {
  width: 52px;
  height: 52px;
  font-size: 22px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.25);
}

.joystick-pad {
  pointer-events: auto;
}

.joystick-pad.is-disabled {
  opacity: 0.7;
  pointer-events: none;
}

:deep(.el-overlay) {
  position: absolute !important;
  inset: 0 !important;
  height: 100% !important;
  overflow: hidden !important;
}

:deep(.el-drawer) {
  position: absolute !important;
  top: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  left: auto !important;
  height: 100% !important;
  overflow: hidden !important;
}

:deep(.el-drawer .el-drawer__body) {
  padding: 0;
  height: 100%;
  width: 100%;
  overflow: hidden !important;
  display: flex;
  flex-direction: column;
}

.chat-drawer {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  background: var(--el-bg-color);
}

.chat-drawer__header {
  flex-shrink: 0;
  height: 48px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 8px;
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
}

.chat-drawer__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.chat-drawer__spacer {
  flex: 1;
}

.chat-drawer__body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
