// 存储工具

/**
 * 本地存储封装
 */
export const storage = {
  /**
   * 设置存储项
   */
  set(key: string, value: any): void {
    try {
      const stringValue = typeof value === 'string' ? value : JSON.stringify(value)
      localStorage.setItem(key, stringValue)
    } catch (error) {
      console.error('Storage set error:', error)
    }
  },

  /**
   * 获取存储项
   */
  get<T = any>(key: string, defaultValue?: T): T | null {
    try {
      const value = localStorage.getItem(key)
      if (value === null) return defaultValue ?? null
      
      try {
        return JSON.parse(value)
      } catch {
        return value as T
      }
    } catch (error) {
      console.error('Storage get error:', error)
      return defaultValue ?? null
    }
  },

  /**
   * 移除存储项
   */
  remove(key: string): void {
    try {
      localStorage.removeItem(key)
    } catch (error) {
      console.error('Storage remove error:', error)
    }
  },

  /**
   * 清空所有存储
   */
  clear(): void {
    try {
      localStorage.clear()
    } catch (error) {
      console.error('Storage clear error:', error)
    }
  },

  /**
   * 检查键是否存在
   */
  has(key: string): boolean {
    return localStorage.getItem(key) !== null
  },
}

/**
 * 会话存储封装
 */
export const sessionStorage = {
  set(key: string, value: any): void {
    try {
      const stringValue = typeof value === 'string' ? value : JSON.stringify(value)
      window.sessionStorage.setItem(key, stringValue)
    } catch (error) {
      console.error('SessionStorage set error:', error)
    }
  },

  get<T = any>(key: string, defaultValue?: T): T | null {
    try {
      const value = window.sessionStorage.getItem(key)
      if (value === null) return defaultValue ?? null
      
      try {
        return JSON.parse(value)
      } catch {
        return value as T
      }
    } catch (error) {
      console.error('SessionStorage get error:', error)
      return defaultValue ?? null
    }
  },

  remove(key: string): void {
    try {
      window.sessionStorage.removeItem(key)
    } catch (error) {
      console.error('SessionStorage remove error:', error)
    }
  },

  clear(): void {
    try {
      window.sessionStorage.clear()
    } catch (error) {
      console.error('SessionStorage clear error:', error)
    }
  },

  has(key: string): boolean {
    return window.sessionStorage.getItem(key) !== null
  },
}
