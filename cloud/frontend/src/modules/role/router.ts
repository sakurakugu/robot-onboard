// 角色相关路由

import type { RouteRecordRaw } from 'vue-router'

export const roleRoutes: RouteRecordRaw[] = [
  {
    path: '/roles',
    name: 'RoleManage',
    component: () => import('@/modules/role/views/RoleManage.vue'),
    meta: {
      title: '角色管理',
      icon: 'UserFilled',
    },
  },
]
