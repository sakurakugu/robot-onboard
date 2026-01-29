<template>
  <div class="page">
    <PageHeader title="知识库" :icon="Collection">
      <template #extra>
        <el-button :icon="Refresh" @click="refresh" :loading="loading">
          刷新
        </el-button>
      </template>
    </PageHeader>

    <div class="content" v-loading="loading">
      <el-empty
        v-if="!loading && docs.length === 0"
        description="暂无文档"
        :image-size="120"
      />
      <el-row :gutter="20" v-else>
        <el-col
          v-for="doc in docs"
          :key="doc.uuid"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
        >
          <el-card shadow="hover" class="doc-card">
            <template #header>
              <div class="doc-header">
                <el-icon><Document /></el-icon>
                <span class="doc-title">{{ doc.title }}</span>
              </div>
            </template>
            <div class="doc-meta">
              <el-tag size="small" type="info">
                {{ doc.category || '未分类' }}
              </el-tag>
              <el-text size="small" type="info">
                {{ formatTime(doc.updated_at) }}
              </el-text>
            </div>
            <el-text class="doc-excerpt" line-clamp="3">
              {{ doc.content }}
            </el-text>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue'
import { Collection, Document, Refresh } from '@element-plus/icons-vue'
import { ref } from 'vue'

type Doc = {
  uuid: string
  title: string
  content: string
  category?: string | null
  tags?: string | null
  updated_at?: string | null
}

const loading = ref(false)
const docs = ref<Doc[]>([])

const refresh = async () => {
  loading.value = true
  docs.value = []
  loading.value = false
}

const formatTime = (val?: string | null) => {
  if (!val) return '-'
  try { return new Date(val).toLocaleString('zh-CN') } catch { return val }
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
  min-height: 400px;
}

.doc-card {
  margin-bottom: 20px;
  height: 280px;
  display: flex;
  flex-direction: column;
}

.doc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.doc-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.doc-excerpt {
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
</style>
