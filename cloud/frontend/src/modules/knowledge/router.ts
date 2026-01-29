// 知识库相关路由

import type { RouteRecordRaw } from 'vue-router'

export const knowledgeBase: RouteRecordRaw[] = [
  {
    path: '/kb',
    name: 'KnowledgeBase',
    component: () => import('@/modules/knowledge/views/KnowledgeBase.vue'),
    meta: {
      title: '知识库',
      icon: 'Document',
    },
  },
]
