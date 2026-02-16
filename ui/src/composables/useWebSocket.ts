/**
 * WebSocket 连接管理 Composable
 */
import { ref, onMounted, onUnmounted } from 'vue'
import type { BusEvent } from '@/types/event'

export function useWebSocket(url: string = 'ws://localhost:8000/ws/events') {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const lastEvent = ref<BusEvent | null>(null)
  const eventHandlers = new Map<string, Array<(payload: any) => void>>()

  /**
   * 连接 WebSocket
   */
  function connect() {
    try {
      ws.value = new WebSocket(url)

      ws.value.onopen = () => {
        console.log('[WebSocket] 已连接')
        isConnected.value = true
        startHeartbeat()
      }

      ws.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          // 处理 pong 响应
          if (data.type === 'pong') {
            return
          }

          // 处理业务事件
          if (data.event_type) {
            lastEvent.value = data as BusEvent
            handleEvent(data as BusEvent)
          }
        } catch (error) {
          console.error('[WebSocket] 解析消息失败:', error)
        }
      }

      ws.value.onerror = (error) => {
        console.error('[WebSocket] 连接错误:', error)
        isConnected.value = false
      }

      ws.value.onclose = () => {
        console.log('[WebSocket] 连接已关闭')
        isConnected.value = false
        stopHeartbeat()
        
        // 5秒后尝试重连
        setTimeout(() => {
          if (!isConnected.value) {
            console.log('[WebSocket] 尝试重连...')
            connect()
          }
        }, 5000)
      }
    } catch (error) {
      console.error('[WebSocket] 连接失败:', error)
    }
  }

  /**
   * 断开连接
   */
  function disconnect() {
    stopHeartbeat()
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    isConnected.value = false
  }

  /**
   * 发送消息
   */
  function send(data: any) {
    if (ws.value && isConnected.value) {
      ws.value.send(JSON.stringify(data))
    } else {
      console.warn('[WebSocket] 连接未建立，无法发送消息')
    }
  }

  /**
   * 订阅事件
   */
  function on(eventType: string, handler: (payload: any) => void) {
    if (!eventHandlers.has(eventType)) {
      eventHandlers.set(eventType, [])
    }
    eventHandlers.get(eventType)!.push(handler)
  }

  /**
   * 取消订阅
   */
  function off(eventType: string, handler?: (payload: any) => void) {
    if (!handler) {
      eventHandlers.delete(eventType)
      return
    }
    
    const handlers = eventHandlers.get(eventType)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index !== -1) {
        handlers.splice(index, 1)
      }
    }
  }

  /**
   * 处理接收到的事件
   */
  function handleEvent(event: BusEvent) {
    const handlers = eventHandlers.get(event.event_type)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(event.payload)
        } catch (error) {
          console.error(`[WebSocket] 事件处理器执行失败 (${event.event_type}):`, error)
        }
      })
    }
  }

  // 心跳机制
  let heartbeatTimer: number | null = null

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = window.setInterval(() => {
      send({ type: 'ping' })
    }, 30000) // 每30秒发送一次心跳
  }

  function stopHeartbeat() {
    if (heartbeatTimer !== null) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  // 生命周期管理
  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    lastEvent,
    connect,
    disconnect,
    send,
    on,
    off
  }
}
