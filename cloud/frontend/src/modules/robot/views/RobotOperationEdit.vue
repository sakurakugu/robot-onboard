<template>
  <div class="robot-operation-edit">
    <el-page-header @back="() => router.push('/operation')" class="page-header">
      <template #content>
        <div class="header-content">
          <el-icon :size="24"><Bot /></el-icon>
          <span class="title">机器人操作编辑</span>
        </div>
      </template>
    </el-page-header>

    <div class="toolbar">
      <el-select
        v-model="selectedUuid"
        placeholder="选择机器人"
        style="width: 200px"
        filterable
        size="small"
      >
        <el-option
          v-for="r in robots"
          :key="r.uuid"
          :label="r.name || r.uuid"
          :value="r.uuid"
        />
      </el-select>

      <div class="layout-editor" v-if="activeTab === 'layout'">
        <el-button v-if="!layoutEditMode" size="small" :icon="EditPen" @click="startLayoutEdit">
          编辑布局
        </el-button>
        <template v-else>
          <el-button size="small" type="success" :icon="Check" @click="saveLayout">
            保存
          </el-button>
          <el-button size="small" type="default" :icon="Close" @click="cancelLayoutEdit">
            取消
          </el-button>
        </template>
      </div>
    </div>

    <el-tabs v-model="activeTab" tab-position="left" class="edit-tabs">
      <el-tab-pane label="操作编辑" name="layout" lazy>
        <div class="layout-pane">
          <div class="layout-preview">
            <RobotOperation ref="operationRef" :embedded="true" :robotUuid="selectedUuid" />
          </div>
        </div>
      </el-tab-pane>
      <el-tab-pane label="基本信息" name="basic" lazy>
        <RobotSettings :embedded="true" :robotUuid="selectedUuid" :hideTabs="true" activeTab="basic" />
      </el-tab-pane>
      <el-tab-pane label="网络配置" name="network" lazy>
        <RobotSettings :embedded="true" :robotUuid="selectedUuid" :hideTabs="true" activeTab="network" />
      </el-tab-pane>
      <el-tab-pane label="日志管理" name="logs" lazy>
        <RobotSettings :embedded="true" :robotUuid="selectedUuid" :hideTabs="true" activeTab="logs" />
      </el-tab-pane>
      <el-tab-pane label="AI 配置" name="ai" lazy>
        <RobotSettings :embedded="true" :robotUuid="selectedUuid" :hideTabs="true" activeTab="ai" />
      </el-tab-pane>
      <el-tab-pane label="系统升级" name="upgrade" lazy>
        <RobotSettings :embedded="true" :robotUuid="selectedUuid" :hideTabs="true" activeTab="upgrade" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Check, Close, EditPen } from '@element-plus/icons-vue'
import { Bot } from 'lucide-vue-next'
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RobotOperation from '@/modules/robot/views/RobotOperation.vue'
import RobotSettings from '@/modules/robot/views/RobotSettings.vue'

const route = useRoute()
const router = useRouter()

const tabKeys = ['layout', 'basic', 'network', 'logs', 'ai', 'upgrade'] as const
type TabKey = (typeof tabKeys)[number]

const normalizeTab = (val: unknown): TabKey => {
  if (typeof val === 'string' && (tabKeys as readonly string[]).includes(val)) return val as TabKey
  return 'layout'
}

const activeTab = ref<TabKey>(normalizeTab(route.query.tab))
const selectedUuid = ref('')
const layoutEditMode = ref(false)
const operationRef = ref<any>(null)

type RobotItem = { uuid: string; name?: string; status?: string }
const robots = ref<RobotItem[]>([])

const fetchRobots = async () => {
  try {
    const res = await fetch('/api/v1/robots')
    const json = await res.json()
    const list: any[] = json?.data?.robots || []
    robots.value = list.map((r) => ({ uuid: r.uuid, name: r.name || '', status: r.status || 'offline' }))
    if (robots.value.length > 0 && !selectedUuid.value) {
      selectedUuid.value = robots.value[0].uuid
    }
  } catch (e) {
    console.error(e)
  }
}

watch(activeTab, (val) => {
  if (val !== 'layout' && layoutEditMode.value) {
    cancelLayoutEdit()
  }
})

watch(
  () => route.query.robotUuid,
  (val) => {
    if (typeof val === 'string' && val && val !== selectedUuid.value) {
      selectedUuid.value = val
    }
  },
  { immediate: true }
)

watch(
  () => route.query.tab,
  (val) => {
    const next = normalizeTab(val)
    if (next !== activeTab.value) {
      activeTab.value = next
    }
  },
  { immediate: true }
)

watch(selectedUuid, () => {
  if (layoutEditMode.value) {
    cancelLayoutEdit()
  }
})

const startLayoutEdit = () => {
  if (!selectedUuid.value) {
    ElMessage.warning('请先选择机器人')
    return
  }
  layoutEditMode.value = true
  operationRef.value?.startLayoutEdit?.()
}

const cancelLayoutEdit = () => {
  operationRef.value?.cancelLayoutEdit?.()
  layoutEditMode.value = false
}

const saveLayout = async () => {
  try {
    await operationRef.value?.saveLayout?.()
    layoutEditMode.value = false
  } catch (e) {
    ElMessage.error('布局保存失败')
  }
}

onMounted(() => {
  fetchRobots()
})
</script>

<style scoped>
.robot-operation-edit {
  padding: 20px;
  height: 100%;
  overflow: auto;
  background: var(--el-bg-color-page);
}

.page-header {
  margin-bottom: 16px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.header-content {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.layout-editor {
  display: flex;
  gap: 8px;
}

.edit-tabs :deep(.el-tabs__content) {
  padding: 0 0 0 20px;
}

.layout-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.layout-preview {
  height: 520px;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
  border: 1px solid var(--el-border-color-light);
}
</style>
