// Axios 请求封装

import { API_BASE_URL, REQUEST_TIMEOUT } from '@/constants'
import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

// 创建 axios 实例
const request: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    // 可以在这里添加 token 等认证信息
    // const token = storage.get(STORAGE_KEYS.TOKEN)
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error: AxiosError) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse) => {
    const { data } = response

    // 如果返回的数据包含 success 字段
    if (data && typeof data.success === 'boolean') {
      if (!data.success) {
        const errorMsg = data.error || data.message || '请求失败'
        ElMessage.error(errorMsg)
        return Promise.reject(new Error(errorMsg))
      }
    }

    return response
  },
  (error: AxiosError) => {
    console.error('响应错误:', error)

    // 处理不同的错误状态码
    if (error.response) {
      const { status, data } = error.response
      let message = '请求失败'

      switch (status) {
        case 400:
          message = (data as any)?.error || '请求参数错误'
          break
        case 401:
          message = '未授权，请登录'
          // 可以在这里处理登录跳转
          break
        case 403:
          message = '拒绝访问'
          break
        case 404:
          message = '请求的资源不存在'
          break
        case 500:
          message = (data as any)?.error || '服务器内部错误'
          break
        case 502:
          message = '网关错误'
          break
        case 503:
          message = '服务不可用'
          break
        case 504:
          message = '网关超时'
          break
        default:
          message = (data as any)?.error || `请求失败 (${status})`
      }

      ElMessage.error(message)
      return Promise.reject(error)
    } else if (error.request) {
      // 请求已发送但没有收到响应
      ElMessage.error('网络错误，请检查您的网络连接')
      return Promise.reject(new Error('Network Error'))
    } else {
      // 请求配置出错
      ElMessage.error('请求配置错误')
      return Promise.reject(error)
    }
  }
)

// 封装请求方法
export const http = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return request.get(url, config).then((res) => res.data)
  },

  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return request.post(url, data, config).then((res) => res.data)
  },

  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return request.put(url, data, config).then((res) => res.data)
  },

  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return request.delete(url, config).then((res) => res.data)
  },

  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return request.patch(url, data, config).then((res) => res.data)
  },
}

export default request
