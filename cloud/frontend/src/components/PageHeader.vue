<template>
  <el-page-header class="page-header" @back="emit('back')">
    <template #content>
      <div class="header-content">
        <el-icon v-if="icon" :size="iconSize">
          <component :is="icon" />
        </el-icon>
        <span class="title">{{ title }}</span>
      </div>
    </template>
    <template v-if="$slots.extra" #extra>
      <slot name="extra" />
    </template>
  </el-page-header>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

type Props = {
  title: string
  icon?: Component
  iconSize?: number
}

withDefaults(defineProps<Props>(), {
  iconSize: 24,
})

const emit = defineEmits<{ back: [] }>()
</script>

<style scoped>
.page-header {
  margin-bottom: 20px;
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

.title {
  line-height: 1;
}
</style>
