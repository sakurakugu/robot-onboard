// 系统相关路由

import type { RouteRecordRaw } from 'vue-router'

export const systemRoutes: RouteRecordRaw[] = [
  {
    path: '/params',
    name: 'Params',
    component: () => import('@/modules/settings/views/ParamsManage.vue'),
    meta: {
      title: '参数管理',
      icon: 'Setting',
    },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/modules/settings/views/Settings.vue'),
    meta: {
      title: '系统设置',
      icon: 'Tools',
    },
  },
]
