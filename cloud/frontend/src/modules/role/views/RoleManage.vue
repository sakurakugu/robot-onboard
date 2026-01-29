<template>
  <div class="role-manage">
    <PageHeader title="角色管理" :icon="UserFilled">
      <template #extra>
        <el-button type="primary" @click="showCreateDialog">创建角色</el-button>
      </template>
    </PageHeader>

    <div class="content">
      <el-table :data="roles" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="角色名称" width="180" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="llm_provider" label="服务商" width="150">
          <template #default="scope">
            {{ getProviderLabel(scope.row.llm_provider) }}
          </template>
        </el-table-column>
        <el-table-column prop="llm_model" label="模型" width="180" show-overflow-tooltip />
        <el-table-column label="绑定机器人" width="120" align="center">
          <template #default="scope">
            <el-button type="text" @click="showRobots(scope.row)">
              {{ scope.row.robot_count || 0 }} 台
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button type="primary" link @click="editRole(scope.row)">编辑</el-button>
            <el-button type="danger" link @click="deleteRole(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建/编辑角色对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑角色' : '创建角色'"
      width="600px"
    >
      <el-form :model="roleForm" label-width="120px" label-position="left">
        <el-form-item label="角色名称" required>
          <el-input v-model="roleForm.name" placeholder="请输入角色名称" maxlength="32" show-word-limit />
        </el-form-item>
        <el-form-item label="角色描述">
          <el-input
            v-model="roleForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入角色描述"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-divider content-position="left">模型配置</el-divider>
        <el-form-item label="服务商">
          <el-select v-model="roleForm.llm_provider" placeholder="选择服务商" style="width: 100%">
            <el-option
              v-for="p in providers"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="使用模型">
          <el-select v-model="roleForm.llm_model" placeholder="选择模型" style="width: 100%">
            <el-option
              v-for="m in availableModels"
              :key="m.value"
              :label="m.label"
              :value="m.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="温度">
          <el-slider
            v-model="roleForm.temperature"
            :min="0"
            :max="2"
            :step="0.1"
            show-input
            :input-size="'small'"
          />
        </el-form-item>
        <el-form-item label="最大历史轮数">
          <el-input-number v-model="roleForm.max_history" :min="0" :max="100" />
        </el-form-item>
        <el-divider content-position="left">系统提示词</el-divider>
        <el-form-item label="系统提示词">
          <el-input
            v-model="roleForm.system_prompt"
            type="textarea"
            :rows="6"
            placeholder="例如：你是一个友好的机器人助手..."
          />
        </el-form-item>
        <el-form-item label="音色">
          <el-select v-model="roleForm.voice" placeholder="选择音色" style="width: 100%">
            <el-option label="女声-温柔" value="female-soft" />
            <el-option label="女声-活泼" value="female-bright" />
            <el-option label="男声-低沉" value="male-deep" />
            <el-option label="男声-洪亮" value="male-bright" />
            <el-option label="童声" value="child" />
            <el-option label="电子音" value="robotic" />
          </el-select>
        </el-form-item>
        <el-form-item label="意图识别">
          <el-select v-model="roleForm.intent_strategy" placeholder="选择方案" style="width: 100%">
            <el-option label="规则引擎" value="rule-based" />
            <el-option label="LLM分类器" value="llm-classifier" />
            <el-option label="混合策略" value="hybrid" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRole" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 机器人列表对话框 -->
    <el-dialog v-model="robotsDialogVisible" title="绑定的机器人" width="600px">
      <el-table :data="boundRobots" v-loading="loadingRobots">
        <el-table-column prop="name" label="机器人名称" />
        <el-table-column prop="model" label="型号" />
        <el-table-column prop="ip" label="IP地址" />
        <el-table-column label="操作" width="100">
          <template #default="scope">
            <el-button type="text" @click="unbindRobot(scope.row)">解绑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue'
import { UserFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'

interface Role {
  uuid: string
  name: string
  description?: string
  llm_provider?: string
  llm_model?: string
  temperature?: number
  system_prompt?: string
  voice?: string
  intent_strategy?: string
  max_history?: number
  robot_count?: number
}

const loading = ref(false)
const roles = ref<Role[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const providers = ref<any[]>([])

const roleForm = ref({
  uuid: '',
  name: '',
  description: '',
  llm_provider: '',
  llm_model: '',
  temperature: 0.7,
  system_prompt: '',
  voice: '',
  intent_strategy: 'hybrid',
  max_history: 10
})

const robotsDialogVisible = ref(false)
const loadingRobots = ref(false)
const boundRobots = ref<any[]>([])
const currentRole = ref<Role | null>(null)

const availableModels = computed(() => {
  const provider = providers.value.find(p => p.value === roleForm.value.llm_provider)
  return provider?.models || []
})

onMounted(async () => {
  loadRoles()
  loadProviders()
})

watch(() => roleForm.value.llm_provider, () => {
  if (!availableModels.value.find((m: any) => m.value === roleForm.value.llm_model)) {
    roleForm.value.llm_model = availableModels.value[0]?.value || ''
  }
})

const loadProviders = async () => {
  try {
    const res = await fetch('/api/v1/config/llm/providers')
    const json = await res.json()
    if (json.success) {
      providers.value = json.data || []
    }
  } catch {}
}

const loadRoles = async () => {
  loading.value = true
  try {
    const res = await fetch('/api/v1/roles')
    const json = await res.json()
    if (json.success) {
      roles.value = json.data || []
      
      // 获取每个角色绑定的机器人数量
      for (const role of roles.value) {
        try {
          const robotRes = await fetch(`/api/v1/roles/${role.uuid}/robots`)
          const robotJson = await robotRes.json()
          if (robotJson.success) {
            role.robot_count = robotJson.data?.length || 0
          }
        } catch {}
      }
    }
  } catch (e) {
    ElMessage.error('加载角色列表失败')
  } finally {
    loading.value = false
  }
}

const getProviderLabel = (value?: string) => {
  const provider = providers.value.find(p => p.value === value)
  return provider?.label || value || '-'
}

const showCreateDialog = () => {
  isEdit.value = false
  roleForm.value = {
    uuid: '',
    name: '',
    description: '',
    llm_provider: providers.value[0]?.value || '',
    llm_model: '',
    temperature: 0.7,
    system_prompt: '',
    voice: 'female-soft',
    intent_strategy: 'hybrid',
    max_history: 10
  }
  dialogVisible.value = true
}

const editRole = (role: Role) => {
  isEdit.value = true
  roleForm.value = {
    uuid: role.uuid,
    name: role.name,
    description: role.description || '',
    llm_provider: role.llm_provider || '',
    llm_model: role.llm_model || '',
    temperature: role.temperature || 0.7,
    system_prompt: role.system_prompt || '',
    voice: role.voice || '',
    intent_strategy: role.intent_strategy || 'hybrid',
    max_history: typeof role.max_history === 'number' ? role.max_history : 10
  }
  dialogVisible.value = true
}

const saveRole = async () => {
  if (!roleForm.value.name) {
    ElMessage.warning('请输入角色名称')
    return
  }

  saving.value = true
  try {
    const url = isEdit.value ? `/api/v1/roles/${roleForm.value.uuid}` : '/api/v1/roles'
    const method = isEdit.value ? 'PUT' : 'POST'
    
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(roleForm.value)
    })

    const json = await res.json()
    if (json.success) {
      ElMessage.success(isEdit.value ? '角色更新成功' : '角色创建成功')
      dialogVisible.value = false
      loadRoles()
    } else {
      ElMessage.error(json.error || '操作失败')
    }
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    saving.value = false
  }
}

const deleteRole = async (role: Role) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除角色 "${role.name}" 吗？删除后，绑定该角色的机器人将解除绑定。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await fetch(`/api/v1/roles/${role.uuid}`, { method: 'DELETE' })
    const json = await res.json()
    
    if (json.success) {
      ElMessage.success('角色删除成功')
      loadRoles()
    } else {
      ElMessage.error(json.error || '删除失败')
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const showRobots = async (role: Role) => {
  currentRole.value = role
  robotsDialogVisible.value = true
  loadingRobots.value = true
  
  try {
    const res = await fetch(`/api/v1/roles/${role.uuid}/robots`)
    const json = await res.json()
    if (json.success) {
      boundRobots.value = json.data || []
    }
  } catch (e) {
    ElMessage.error('加载机器人列表失败')
  } finally {
    loadingRobots.value = false
  }
}

const unbindRobot = async (robot: any) => {
  try {
    await ElMessageBox.confirm(`确定要解绑机器人 "${robot.name}" 吗？`, '解绑确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const res = await fetch(`/api/v1/robots/${robot.uuid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role_id: null })
    })

    const json = await res.json()
    if (json.success) {
      ElMessage.success('解绑成功')
      showRobots(currentRole.value!)
      loadRoles()
    } else {
      ElMessage.error(json.error || '解绑失败')
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('解绑失败')
    }
  }
}
</script>

<style scoped>
.role-manage {
  padding: 20px;
  height: 100%;
  overflow: auto;
  background: var(--el-bg-color-page);
}

.content {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}
</style>
