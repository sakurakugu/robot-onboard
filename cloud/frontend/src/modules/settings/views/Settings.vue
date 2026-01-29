<template>
  <div class="page">
    <PageHeader title="系统设置" :icon="Tools" />

    <div class="content">
      <el-card shadow="hover">
        <el-form :model="formData" label-width="140px" label-position="left">
          <el-form-item label="主题模式">
            <el-radio-group v-model="theme">
              <el-radio value="system">跟随系统</el-radio>
              <el-radio value="light">浅色</el-radio>
              <el-radio value="dark">深色</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="界面语言">
            <el-select v-model="language" placeholder="选择语言" style="width: 200px">
              <el-option label="简体中文" value="zh-CN" />
              <el-option label="English" value="en-US" />
            </el-select>
          </el-form-item>
          <el-form-item label="字体大小">
            <el-radio-group v-model="fontSize">
              <el-radio value="small">小</el-radio>
              <el-radio value="medium">中</el-radio>
              <el-radio value="large">大</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="save" :icon="Select">
              保存
            </el-button>
            <el-text v-if="saved" type="success" style="margin-left: 12px">
              已保存
            </el-text>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue'
import { Select, Tools } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

const formData = ref({})
const theme = ref<'system' | 'dark' | 'light'>('system')
const language = ref<'zh-CN' | 'en-US'>('zh-CN')
const fontSize = ref<'small' | 'medium' | 'large'>('medium')
const saved = ref(false)

onMounted(() => {
  theme.value = (localStorage.getItem('rc_theme') as any) || 'system'
  language.value = (localStorage.getItem('rc_language') as any) || 'zh-CN'
  fontSize.value = (localStorage.getItem('rc_fontSize') as any) || 'medium'
})

const save = () => {
  localStorage.setItem('rc_theme', theme.value)
  localStorage.setItem('rc_language', language.value)
  localStorage.setItem('rc_fontSize', fontSize.value)
  saved.value = true
  setTimeout(() => (saved.value = false), 1200)
}
</script>

<style scoped>
.page {
  height: 100%;
  padding: 20px;
  background: var(--el-bg-color-page);
  overflow: auto;
}

.content {
  max-width: 800px;
}

:deep(.el-card__body) {
  padding: 30px;
}
</style>
