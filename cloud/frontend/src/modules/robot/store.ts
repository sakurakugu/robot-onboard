// 机器人模块 - 状态管理

import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as robotApi from './api'
import type { Robot } from './types'

export const useRobotStore = defineStore('robot', () => {
  // 状态
  const robots = ref<Robot[]>([])
  const currentRobot = ref<Robot | null>(null)
  const loading = ref(false)
  const groups = ref<string[]>([])

  // 计算属性
  const onlineRobots = computed(() => 
    robots.value.filter(r => r.status === 'online')
  )

  const offlineRobots = computed(() => 
    robots.value.filter(r => r.status === 'offline')
  )

  const onlineCount = computed(() => onlineRobots.value.length)

  const totalCount = computed(() => robots.value.length)

  const robotsByGroup = computed(() => {
    const grouped: Record<string, Robot[]> = {}
    robots.value.forEach(robot => {
      const group = robot.group_name || '未分组'
      if (!grouped[group]) {
        grouped[group] = []
      }
      grouped[group].push(robot)
    })
    return grouped
  })

  // 方法
  async function fetchRobots() {
    loading.value = true
    try {
      const res = await robotApi.getRobotList()
      robots.value = res.data.robots
      return res.data
    } catch (error) {
      console.error('获取机器人列表失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchGroups() {
    try {
      const res = await robotApi.getRobotGroups()
      groups.value = res.data.groups
      return res.data.groups
    } catch (error) {
      console.error('获取分组失败:', error)
      throw error
    }
  }

  async function fetchRobotDetail(uuid: string) {
    loading.value = true
    try {
      const res = await robotApi.getRobotDetail(uuid)
      currentRobot.value = res.data
      
      // 更新列表中的机器人
      const index = robots.value.findIndex(r => r.uuid === uuid)
      if (index !== -1) {
        robots.value[index] = res.data
      }
      
      return res.data
    } catch (error) {
      console.error('获取机器人详情失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function createRobot(data: any) {
    loading.value = true
    try {
      const res = await robotApi.createRobot(data)
      robots.value.unshift(res.data)
      ElMessage.success('创建成功')
      return res.data
    } catch (error) {
      console.error('创建机器人失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateRobot(uuid: string, data: any) {
    loading.value = true
    try {
      const res = await robotApi.updateRobot(uuid, data)
      
      // 更新列表中的机器人
      const index = robots.value.findIndex(r => r.uuid === uuid)
      if (index !== -1) {
        robots.value[index] = res.data
      }
      
      // 更新当前机器人
      if (currentRobot.value?.uuid === uuid) {
        currentRobot.value = res.data
      }
      
      ElMessage.success('更新成功')
      return res.data
    } catch (error) {
      console.error('更新机器人失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function deleteRobot(uuid: string) {
    loading.value = true
    try {
      await robotApi.deleteRobot(uuid)
      
      // 从列表中移除
      const index = robots.value.findIndex(r => r.uuid === uuid)
      if (index !== -1) {
        robots.value.splice(index, 1)
      }
      
      // 清除当前机器人
      if (currentRobot.value?.uuid === uuid) {
        currentRobot.value = null
      }
      
      ElMessage.success('删除成功')
    } catch (error) {
      console.error('删除机器人失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function testConnection(uuid: string) {
    try {
      const res = await robotApi.testRobotConnection(uuid)
      if (res.connected) {
        ElMessage.success(res.message || '连接成功')
      } else {
        ElMessage.warning(res.message || '连接失败')
      }
      return res
    } catch (error) {
      console.error('测试连接失败:', error)
      throw error
    }
  }

  async function connectRobot(uuid: string) {
    loading.value = true
    try {
      const res = await robotApi.connectRobot(uuid)
      
      // 更新列表中的机器人状态
      const index = robots.value.findIndex(r => r.uuid === uuid)
      if (index !== -1) {
        robots.value[index] = res.data
      }
      
      ElMessage.success('连接成功')
      return res.data
    } catch (error) {
      console.error('连接机器人失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function updateFirmware(uuid: string) {
    loading.value = true
    try {
      const res = await robotApi.updateRobotFirmware(uuid)
      ElMessage.success('固件更新成功')
      return res
    } catch (error) {
      console.error('更新固件失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  function setCurrentRobot(robot: Robot | null) {
    currentRobot.value = robot
  }

  function getRobotById(uuid: string) {
    return robots.value.find(r => r.uuid === uuid)
  }

  function clearCurrentRobot() {
    currentRobot.value = null
  }

  return {
    // 状态
    robots,
    currentRobot,
    loading,
    groups,
    
    // 计算属性
    onlineRobots,
    offlineRobots,
    onlineCount,
    totalCount,
    robotsByGroup,
    
    // 方法
    fetchRobots,
    fetchGroups,
    fetchRobotDetail,
    createRobot,
    updateRobot,
    deleteRobot,
    testConnection,
    connectRobot,
    updateFirmware,
    setCurrentRobot,
    getRobotById,
    clearCurrentRobot,
  }
})
