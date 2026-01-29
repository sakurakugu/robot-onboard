// 机器人相关路由

import type { RouteRecordRaw } from 'vue-router'

export const robotRoutes: RouteRecordRaw[] = [
  {
    path: '/robots',
    name: 'RobotList',
    component: () => import('@/modules/robot/views/RobotManage.vue'),
    meta: {
      title: '机器人管理',
      icon: 'Robot',
    },
  },
  {
    path: '/robots/:uuid',
    name: 'RobotDetail',
    component: () => import('@/modules/robot/views/RobotSettings.vue'),
    meta: {
      title: '机器人详情',
      hidden: true,
    },
  },
  {
    path: '/robots/:uuid/settings',
    name: 'RobotSettings',
    component: () => import('@/modules/robot/views/RobotSettings.vue'),
    meta: {
      title: '机器人设置',
      hidden: true,
    },
  },
  {
    path: '/operation',
    name: 'Operation',
    component: () => import('@/modules/robot/views/RobotOperation.vue'),
    meta: {
      title: '机器人操作',
      icon: 'Operation',
    },
  },
  {
    path: '/operation/edit',
    name: 'OperationEdit',
    component: () => import('@/modules/robot/views/RobotOperationEdit.vue'),
    meta: {
      title: '机器人操作编辑',
      hidden: true,
    },
  },
]
