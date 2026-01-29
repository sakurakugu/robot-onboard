// 路由配置

import { conversationRoutes } from '@/modules/conversation/router'
import { knowledgeBase } from '@/modules/knowledge/router'
import MainLayout from '@/modules/layouts/views/MainLayout.vue'
import { robotRoutes } from '@/modules/robot/router'
import { roleRoutes } from '@/modules/role/router'
import { systemRoutes } from '@/modules/settings/router'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/robots',
    children: [
      ...robotRoutes,
      ...roleRoutes,
      ...conversationRoutes,
      ...systemRoutes,
      ...knowledgeBase,
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: '/robots',
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 机器狗对话系统`
  }
  
  next()
})

export default router
