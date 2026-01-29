<template>
  <div class="robot-manager">
    <PageHeader title="机器人管理" :icon="Bot">
      <template #extra>
        <el-space>
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="card">
              <el-icon><Grid /></el-icon>
            </el-radio-button>
            <el-radio-button value="list">
              <el-icon><List /></el-icon>
            </el-radio-button>
          </el-radio-group>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">
            添加机器人
          </el-button>
        </el-space>
      </template>
    </PageHeader>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      style="margin: 20px 20px 0"
    />

    <!-- 卡片视图 -->
    <div v-if="viewMode === 'card'" class="robot-cards" v-loading="loading">
      <el-card
        v-for="robot in robots"
        :key="robot.uuid"
        shadow="hover"
        class="robot-card"
      >
        <template #header>
          <div class="card-header-content">
            <div class="card-title">
              <el-icon :size="20"><Bot /></el-icon>
              <span>{{ robot.name || '未命名' }}</span>
            </div>
            <el-tag
              :type="getStatusType(robot.status)"
              size="small"
              effect="dark"
            >
              {{ statusText(robot.status) }}
            </el-tag>
          </div>
        </template>

        <el-descriptions :column="1" size="small" border>
          <el-descriptions-item label="UUID">
            <el-text class="mono" size="small">{{ robot.uuid }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="型号">
            {{ robot.model || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="最近连接">
            {{ formatTime(robot.last_connected) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="robot.status === 'offline' && connectionErrors[robot.uuid]"
          :title="connectionErrors[robot.uuid]"
          type="warning"
          :closable="true"
          @close="dismissError(robot.uuid)"
          style="margin-top: 12px"
        />

        <template #footer>
          <el-space wrap>
            <el-button
              size="small"
              :type="robot.status === 'online' ? 'success' : 'primary'"
              :loading="testing[robot.uuid]"
              :disabled="robot.status === 'online' && connectReady[robot.uuid] === false"
              @click="testConnection(robot)"
            >
              {{ testing[robot.uuid] ? '测试中' : (robot.status === 'online' ? '连接' : '测试连接') }}
            </el-button>
            <el-button 
              size="small" 
              :icon="Upload" 
              :loading="updating[robot.uuid]"
              @click="updateFirmware(robot)"
              title="更新客户端代码到机器人"
            >
              {{ updating[robot.uuid] ? '更新中' : '更新固件' }}
            </el-button>
            <el-button size="small" :icon="ChatLineSquare" @click="openChat(robot)">
              对话
            </el-button>
            <el-button size="small" :icon="Edit" @click="editRobot(robot)">
              编辑
            </el-button>
            <el-button
              size="small"
              :icon="Delete"
              type="danger"
              @click="deleteRobotConfirm(robot)"
            >
              删除
            </el-button>
          </el-space>
        </template>
      </el-card>

      <el-empty
        v-if="!loading && robots.length === 0"
        description="暂无机器人"
      >
        <el-button type="primary" @click="openAddDialog">添加第一个机器人</el-button>
      </el-empty>
    </div>

    <!-- 列表视图 -->
    <div v-else class="robot-list" v-loading="loading">
      <el-table :data="robots" stripe style="width: 100%">
        <el-table-column prop="name" label="名称" width="150">
          <template #default="{ row }">
            <div class="name-cell">
              <el-icon><Bot /></el-icon>
              <span>{{ row.name || '未命名' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model" label="型号" width="150" />
        <el-table-column prop="uuid" label="UUID" min-width="200">
          <template #default="{ row }">
            <el-text class="mono" size="small">{{ row.uuid }}</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="last_connected" label="最近连接" width="180">
          <template #default="{ row }">
            {{ formatTime(row.last_connected) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="350" fixed="right">
          <template #default="{ row }">
            <el-space>
              <el-button
                size="small"
                :type="row.status === 'online' ? 'success' : 'primary'"
                :loading="testing[row.uuid]"
                :disabled="row.status === 'online' && connectReady[row.uuid] === false"
                @click="testConnection(row)"
              >
                {{ testing[row.uuid] ? '测试中' : (row.status === 'online' ? '连接' : '测试') }}
              </el-button>
              <el-button 
                size="small" 
                :loading="updating[row.uuid]"
                @click="updateFirmware(row)"
                title="更新固件"
              >
                {{ updating[row.uuid] ? '更新中' : '更新' }}
              </el-button>
              <el-button size="small" @click="openChat(row)">对话</el-button>
              <el-button size="small" @click="editRobot(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteRobotConfirm(row)">删除</el-button>
              <el-tooltip
                v-if="row.status === 'offline' && connectionErrors[row.uuid]"
                :content="connectionErrors[row.uuid]"
                placement="top"
              >
                <el-icon color="var(--el-color-warning)"><Warning /></el-icon>
              </el-tooltip>
            </el-space>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && robots.length === 0"
        description="暂无机器人"
      >
        <el-button type="primary" @click="openAddDialog">添加第一个机器人</el-button>
      </el-empty>
    </div>

    <!-- 添加机器人对话框 -->
    <el-dialog
      v-model="showAddDialog"
      title="添加机器人"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="formData" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="formData.name" placeholder="例如：机器狗1" />
        </el-form-item>
        <el-form-item label="机器人IP">
          <el-input v-model="formData.robot_ip" placeholder="例如：192.168.1.110" />
          <el-text v-if="formData.robot_ip && !isValidIp(formData.robot_ip)" type="danger" size="small">
            IP格式不正确
          </el-text>
        </el-form-item>
        <el-form-item label="分组">
          <el-select 
            v-model="formData.group_name" 
            placeholder="选择分组" 
            allow-create 
            filterable 
            default-first-option
          >
            <el-option label="默认分组" value="Default" />
            <el-option label="开发测试" value="Dev" />
            <el-option label="演示展厅" value="Demo" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" @click="saveRobot" :disabled="!isFormValid">
          添加
        </el-button>
      </template>
    </el-dialog>

    <!-- 重启运控对话框 -->
    <el-dialog
      v-model="showRestartDialog"
      title="重启运控"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="请确认设备已卧倒，避免急停"
        type="warning"
        :closable="false"
        style="margin-bottom: 16px"
      />
      <el-text v-if="restarting">将在 {{ countdown }} 秒后执行重启，可随时取消。</el-text>
      <template #footer>
        <el-button @click="closeRestartDialog">取消</el-button>
        <el-button type="primary" @click="confirmRestart" :disabled="restarting">
          {{ restarting ? '倒计时中' : '确认设备已卧倒' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue'
import {
    ChatLineSquare,
    Delete,
    Edit,
    Grid, List,
    Plus,
    Upload,
    Warning
} from '@element-plus/icons-vue'
import type { TagProps } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bot } from 'lucide-vue-next'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

type Robot = {
  uuid: string
  name?: string | null
  model?: string | null
  status: 'online' | 'offline' | 'connecting' | 'error'
  last_connected?: string | null
  robot_ip?: string | null
  local_ip?: string | null
  local_port?: number
  group_name?: string | null
}

const router = useRouter()

const robots = ref<Robot[]>([])
const viewMode = ref<'card' | 'list'>('card')
const showAddDialog = ref(false)
const testing = ref<Record<string, boolean>>({})
const updating = ref<Record<string, boolean>>({})
const connectionErrors = ref<Record<string, string>>({})
const connectReady = ref<Record<string, boolean>>({})
const showRestartDialog = ref(false)
const restartRobot = ref<Robot | null>(null)
const restarting = ref(false)
const countdown = ref(3)
let countdownTimer: any = null
const error = ref('')
const loading = ref(false)

type FormData = {
  name: string
  robot_ip: string
  group_name: string
}
const formData = ref<FormData>({
  name: '',
  robot_ip: '',
  group_name: ''
})

const isValidIp = (ip: string) => {
  const ipv4 = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/
  return ipv4.test(ip)
}

const isFormValid = computed(() => {
  return Boolean(
    formData.value.name &&
    (!formData.value.robot_ip || isValidIp(formData.value.robot_ip))
  )
})

function statusText(status: string): string {
  const map: Record<string, string> = {
    online: '在线',
    offline: '离线',
    connecting: '连接中',
    error: '异常'
  }
  return map[status] || status
}

function getStatusType(status: string): TagProps['type'] {
  const map: Record<string, TagProps['type']> = {
    online: 'success',
    offline: 'info',
    connecting: 'warning',
    error: 'danger'
  }
  return map[status] || 'info'
}

function formatTime(val?: string | null) {
  if (!val) return '-'
  const d = new Date(val as any)
  const t = d.getTime()
  if (isNaN(t)) return typeof val === 'string' ? val : '-'
  return d.toLocaleString('zh-CN')
}

async function loadRobots() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/v1/robots')
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || `HTTP ${res.status}`)
    }
    let json: any
    try {
      json = await res.json()
    } catch {
      const text = await res.text()
      throw new Error(text || '接口返回空内容')
    }
    if (!json.success) throw new Error(json.error || '加载失败')
    const list: any[] = json.data.robots || []
    robots.value = list.map((r) => {
      let meta: any = {}
      try {
        meta = r.metadata ? JSON.parse(r.metadata) : {}
      } catch {
        meta = {}
      }
      return {
        uuid: r.uuid,
        name: r.name || '',
        model: r.model || '',
        status: r.status || 'offline',
        last_connected: r.last_connected || null,
        robot_ip: r.robot_ip ?? meta.robot_ip ?? '',
        local_ip: r.local_ip ?? meta.local_ip ?? '',
        local_port: r.local_port ?? meta.local_port ?? 10000,
        group_name: r.group_name ?? meta.group_name ?? ''
      }
    })
  } catch (e: any) {
    error.value = e?.message || '加载失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

// 顶部本机IP及相关逻辑已移除

async function testConnection(robot: Robot) {
  if (robot.status === 'online') {
    return connectNow(robot)
  }
  testing.value[robot.uuid] = true
  connectionErrors.value[robot.uuid] = ''
  try {
    const res = await fetch(`/api/v1/robots/${robot.uuid}/test-connection`, { method: 'POST' })
    const json = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`)
    if (json.success && json.connected) {
      robot.status = 'online'
      connectReady.value[robot.uuid] = false
      setTimeout(() => {
        connectReady.value[robot.uuid] = true
      }, 1000)
      ElMessage.success(json.message || '测试通过，请点击连接')
    } else {
      robot.status = 'offline'
      const errMsg = json?.message || json?.error || '测试失败'
      connectionErrors.value[robot.uuid] = errMsg
      ElMessage.error(errMsg)
    }
  } catch (e: any) {
    robot.status = 'offline'
    const errMsg = e?.message || '连接测试失败'
    connectionErrors.value[robot.uuid] = errMsg
    ElMessage.error(errMsg)
  } finally {
    testing.value[robot.uuid] = false
  }
}

async function connectNow(robot: Robot) {
  if (connectReady.value[robot.uuid] === false) {
    return
  }
  testing.value[robot.uuid] = true
  connectionErrors.value[robot.uuid] = ''
  try {
    const res = await fetch(`/api/v1/robots/${robot.uuid}/connect`, { method: 'POST' })
    const json = await res.json().catch(() => ({}))
    if (res.ok && json.success) {
      ElMessage.success(json.message || '连接成功')
      restartRobot.value = robot
      countdown.value = 3
      showRestartDialog.value = true
    } else {
      robot.status = 'offline'
      const errMsg = json?.message || json?.error || `HTTP ${res.status}`
      connectionErrors.value[robot.uuid] = errMsg
      ElMessage.error(errMsg || '连接失败')
    }
  } catch (e: any) {
    robot.status = 'offline'
    const errMsg = e?.message || '连接失败'
    connectionErrors.value[robot.uuid] = errMsg
    ElMessage.error(errMsg)
  } finally {
    testing.value[robot.uuid] = false
  }
}

function editRobot(robot: Robot) {
  router.push(`/robots/${robot.uuid}`)
}

async function updateFirmware(robot: Robot) {
  try {
    await ElMessageBox.confirm(
      `确定要更新机器人"${robot.name || robot.uuid}"的客户端代码吗？\n\n这将把最新的客户端代码复制到机器人。`,
      '更新固件',
      { 
        type: 'warning', 
        confirmButtonText: '确定更新', 
        cancelButtonText: '取消' 
      }
    )
    
    updating.value[robot.uuid] = true
    
    const res = await fetch(`/api/v1/robots/${robot.uuid}/update-firmware`, {
      method: 'POST'
    })
    
    const json = await res.json().catch(() => ({}))
    
    if (!res.ok || !json.success) {
      throw new Error(json.error || `HTTP ${res.status}`)
    }
    
    ElMessage.success({
      message: json.message || '客户端代码更新成功',
      duration: 3000
    })
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error({
        message: e?.message || '更新失败',
        duration: 5000
      })
    }
  } finally {
    updating.value[robot.uuid] = false
  }
}

function openChat(robot: Robot) {
  router.push(`/chat/${robot.uuid}`)
}

function notifyRobotsUpdated() {
  try {
    window.dispatchEvent(new CustomEvent('robots_updated'))
  } catch {}
}

async function saveRobot() {
  const payload = {
    name: formData.value.name,
    robot_ip: formData.value.robot_ip,
    group_name: formData.value.group_name || ''
  }
  try {
    const res = await fetch('/api/v1/robots', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok || !json.success) throw new Error(json.error || `HTTP ${res.status}`)
    const saved = json.data
    let meta: any = {}
    try {
      meta = saved.metadata ? JSON.parse(saved.metadata) : {}
    } catch {
      meta = {}
    }
    robots.value.push({
      uuid: saved.uuid,
      name: saved.name || '',
      model: saved.model || '',
      status: saved.status || 'offline',
      last_connected: saved.last_connected || null,
      robot_ip: saved.robot_ip ?? meta.robot_ip ?? '',
      local_ip: saved.local_ip ?? meta.local_ip ?? '',
      local_port: saved.local_port ?? meta.local_port ?? 10000,
      group_name: saved.group_name ?? meta.group_name ?? ''
    })
    notifyRobotsUpdated()
    closeDialog()
    ElMessage.success('添加成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function deleteRobotConfirm(robot: Robot) {
  try {
    await ElMessageBox.confirm(
      `确定要删除机器人"${robot.name || robot.uuid}"吗？`,
      '提示',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const res = await fetch(`/api/v1/robots/${robot.uuid}`, { method: 'DELETE' })
    const json = await res.json().catch(() => ({}))
    if (!res.ok || !json.success) throw new Error(json.error || `HTTP ${res.status}`)
    robots.value = robots.value.filter((r) => r.uuid !== robot.uuid)
    notifyRobotsUpdated()
    ElMessage.success('已删除')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

function closeDialog() {
  showAddDialog.value = false
  formData.value = {
    name: '',
    robot_ip: '',
    group_name: ''
  }
}

const openAddDialog = () => {
  showAddDialog.value = true
  formData.value = {
    name: '',
    robot_ip: '',
    group_name: ''
  }
}

function dismissError(uuid: string) {
  if (connectionErrors.value[uuid]) {
    delete connectionErrors.value[uuid]
  }
}

function closeRestartDialog() {
  showRestartDialog.value = false
  restartRobot.value = null
  restarting.value = false
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  countdown.value = 3
}

async function confirmRestart() {
  if (!restartRobot.value || restarting.value) return
  restarting.value = true
  countdown.value = 3
  countdownTimer = setInterval(async () => {
    countdown.value -= 1
    if (countdown.value <= 0 && restartRobot.value) {
      clearInterval(countdownTimer)
      countdownTimer = null
      ElMessage.success('已发送重启指令')
      closeRestartDialog()
    }
  }, 1000)
}

onMounted(() => {
  loadRobots()
})

onUnmounted(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
  }
})
</script>

<style scoped>
.robot-manager {
  padding: 20px;
  height: 100%;
  overflow: auto;
  background: var(--el-bg-color-page);
}

.robot-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  padding: 4px;
}

.robot-card {
  transition: transform 0.2s;
}

.robot-card:hover {
  transform: translateY(-4px);
}

.card-header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
}

.robot-list {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mono {
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Roboto Mono', monospace;
  font-size: 12px;
}
</style>
