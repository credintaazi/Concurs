import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export function useEditionSocket(editionId: number, enabled = true) {
  const client = useQueryClient()
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  useEffect(() => {
    if (!enabled) { setConnection('disconnected'); return }
    let socket: WebSocket | undefined
    let stopped = false
    let attempt = 0
    let latestRevision = -1
    let reconnect: ReturnType<typeof setTimeout>
    let heartbeat: ReturnType<typeof setInterval>
    let pongDeadline: ReturnType<typeof setTimeout>
    const connect = () => {
      if (stopped) return
      clearTimeout(reconnect)
      if (!navigator.onLine) { setConnection('disconnected'); return }
      setConnection('connecting')
      const path = editionId === 0 ? '/ws/catalog' : `/ws/editions/${editionId}`
      const active = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${path}`)
      socket = active
      active.onopen = () => {
        if (stopped || socket !== active) { active.close(); return }
        attempt = 0
        latestRevision = -1
        setConnection('connected')
        heartbeat = setInterval(() => {
          if (active.readyState === WebSocket.OPEN) {
            active.send('ping')
            pongDeadline = setTimeout(() => active.close(), 10000)
          }
        }, 20000)
      }
      active.onmessage = (message) => {
        if (stopped || socket !== active) return
        try {
          const event = JSON.parse(message.data)
          if (event.event === 'PONG') { clearTimeout(pongDeadline); return }
          if (editionId === 0) {
            void client.invalidateQueries({ queryKey: ['public-editions'] })
            void client.invalidateQueries({ queryKey: ['public-edition'] })
            void client.invalidateQueries({ queryKey: ['participations'] })
            void client.invalidateQueries({ queryKey: ['competitions'] })
            void client.invalidateQueries({ queryKey: ['overview'] })
            return
          }
          if (event.edition_id !== editionId) return
          if (event.event !== 'SYNC' && event.revision <= latestRevision) return
          latestRevision = event.revision ?? latestRevision
          void client.invalidateQueries({ queryKey: ['edition', editionId] })
          void client.invalidateQueries({ queryKey: ['public-edition', editionId] })
        } catch { active.close() }
      }
      active.onerror = () => active.close()
      active.onclose = () => {
        if (socket !== active) return
        clearInterval(heartbeat)
        clearTimeout(pongDeadline)
        if (!stopped) {
          setConnection('disconnected')
          if (navigator.onLine) reconnect = setTimeout(connect, Math.min(1000 * 2 ** attempt++, 15000))
        }
      }
    }
    const offline = () => {
      clearTimeout(reconnect)
      clearInterval(heartbeat)
      clearTimeout(pongDeadline)
      setConnection('disconnected')
      socket?.close()
    }
    const online = () => {
      if (!socket || socket.readyState !== WebSocket.OPEN) connect()
    }
    window.addEventListener('offline', offline)
    window.addEventListener('online', online)
    connect()
    return () => {
      stopped = true
      window.removeEventListener('offline', offline)
      window.removeEventListener('online', online)
      clearTimeout(reconnect)
      clearTimeout(pongDeadline)
      clearInterval(heartbeat)
      socket?.close()
    }
  }, [editionId, client, enabled])
  return connection
}
