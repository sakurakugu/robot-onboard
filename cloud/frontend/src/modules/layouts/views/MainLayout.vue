<template>
  <el-container class="layout-container">
    <el-header class="layout-header">
      <div class="header-content">
        <el-icon class="logo-icon" :size="24"><Bot /></el-icon>
        <h1>机器狗管理应用</h1>
      </div>
    </el-header>
    <el-container class="main-container">
      <el-aside :width="asideWidth + 'px'" class="layout-aside" :class="{ collapsed: isCollapse }">
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          :collapse="isCollapse"
          :collapse-transition="false"
          router
        >
          <el-menu-item index="/robots">
            <el-icon><List /></el-icon>
            <template #title>机器人管理</template>
          </el-menu-item>
          <el-menu-item index="/roles">
            <el-icon><UserFilled /></el-icon>
            <template #title>角色管理</template>
          </el-menu-item>
          <el-menu-item index="/operation">
            <el-icon><VideoPlay /></el-icon>
            <template #title>机器人操作</template>
          </el-menu-item>
          <el-menu-item index="/params">
            <el-icon><Setting /></el-icon>
            <template #title>参数管理</template>
          </el-menu-item>
          <el-menu-item index="/kb">
            <el-icon><Collection /></el-icon>
            <template #title>知识库</template>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Tools /></el-icon>
            <template #title>系统设置</template>
          </el-menu-item>
        </el-menu>
        <div class="collapse-toggle" @click="toggleCollapse">
          <el-icon><DArrowLeft v-if="!isCollapse" /><DArrowRight v-else /></el-icon>
        </div>
      </el-aside>
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { Collection, DArrowLeft, DArrowRight, List, Setting, Tools, UserFilled, VideoPlay } from '@element-plus/icons-vue'
import { Bot } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()      // 获取当前路由信息
const isCollapse = ref(false) // 是否折叠侧边栏
const asideWidth = computed(() => isCollapse.value ? 64 : 200) // 侧边栏宽度

// 计算当前激活的菜单项
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/robots')) return '/robots'
  if (path.startsWith('/roles')) return '/roles'
  if (path.startsWith('/operation')) return '/operation'
  if (path.startsWith('/params')) return '/params'
  if (path.startsWith('/kb')) return '/kb'
  if (path.startsWith('/settings')) return '/settings'
  return path
})

// 切换侧边栏折叠状态
const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  width: 100%;
}

.layout-header {
  height: 60px !important;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
  color: white;
}

.logo-icon {
  font-size: 24px;
}

.layout-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: white;
}

.main-container {
  height: calc(100vh - 60px);
}

.layout-aside {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color);
  transition: width 0.3s;
  position: relative;
  display: flex;
  flex-direction: column;
}

.layout-aside.collapsed {
  overflow: hidden;
  overflow-x: hidden;
  scrollbar-width: none;
}

.el-menu-vertical {
  border: none;
  flex: 1;
}

.el-menu-vertical:not(.el-menu--collapse) {
  width: 100%;
}

.layout-aside.collapsed .el-menu-vertical {
  overflow: hidden;
  overflow-x: hidden;
  min-width: 0;
  scrollbar-width: none;
}

.layout-aside.collapsed .collapse-toggle {
  overflow: hidden;
}

.layout-aside.collapsed ::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}

.collapse-toggle {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-top: 1px solid var(--el-border-color);
  color: var(--el-text-color-regular);
  transition: all 0.3s;
}

.collapse-toggle:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.layout-main {
  background: var(--el-bg-color-page);
  padding: 0;
  overflow: auto;
}
</style>
