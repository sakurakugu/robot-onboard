// 对话相关路由

import type { RouteRecordRaw } from 'vue-router'

export const conversationRoutes: RouteRecordRaw[] = [
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/modules/conversation/views/ChatView.vue'),
    meta: {
      title: '对话',
      icon: 'ChatDotRound',
    },
  },
  {
    path: '/chat/:uuid',
    name: 'ChatWithRobot',
    component: () => import('@/modules/conversation/views/ChatView.vue'),
    meta: {
      title: '对话',
      hidden: true,
    },
  },
]
