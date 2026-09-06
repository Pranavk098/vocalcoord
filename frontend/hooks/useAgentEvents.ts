// frontend/hooks/useAgentEvents.ts
'use client'
import { useEffect, useReducer, useRef } from 'react'
import {
  AgentEvent, AgentState, AgentName, initialAgentState
} from '@/types/events'

let _nextId = 0

type Action = { type: 'EVENT'; payload: AgentEvent } | { type: 'RESET' }

function reducer(state: AgentState, action: Action): AgentState {
  if (action.type === 'RESET') return initialAgentState

  const event = action.payload
  if (event.type === 'ping') return state

  switch (event.type) {
    case 'fault_detected':
      return { ...state, fault: event.data, faultActive: true }

    case 'orchestrator':
      return { ...state, routingTo: event.data.routing_to }

    case 'agent_start':
      return {
        ...state,
        agents: {
          ...state.agents,
          [event.data.agent]: { status: 'active', message: event.data.message }
        }
      }

    case 'agent_tool_call':
      return {
        ...state,
        agents: {
          ...state.agents,
          [event.data.agent]: {
            ...state.agents[event.data.agent as AgentName],
            tool: event.data.tool
          }
        }
      }

    case 'agent_result': {
      const entry = {
        id: _nextId++,
        timestamp: Date.now(),
        agent: event.data.agent,
        message: event.data.summary + (event.data.value ? ` — ${event.data.value}` : '')
      }
      return {
        ...state,
        agents: {
          ...state.agents,
          [event.data.agent]: {
            status: 'complete',
            summary: event.data.summary,
            value: event.data.value
          }
        },
        eventLog: [...state.eventLog, entry]
      }
    }

    case 'voice_reply_ready':
      return { ...state, voiceReply: event.data.text }

    case 'nav_confirmed':
      return { ...state, navConfirmed: event.data.confirmed ?? null }

    default:
      return state
  }
}

export function useAgentEvents(conversationId: string | null) {
  const [state, dispatch] = useReducer(reducer, initialAgentState)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    dispatch({ type: 'RESET' })
    if (!conversationId) {
      console.log('[SSE] No conversationId yet — not connecting')
      return
    }

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000'
    const url = `${backendUrl}/events/${conversationId}`
    console.log('[SSE] Connecting to', url)
    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => console.log('[SSE] Connected for', conversationId)
    es.onerror = (e) => console.error('[SSE] Error', e)

    es.onmessage = (e) => {
      console.log('[SSE] Event received:', e.data)
      try {
        const event = JSON.parse(e.data) as AgentEvent
        dispatch({ type: 'EVENT', payload: event })
      } catch {
        // malformed event, ignore
      }
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, [conversationId])

  return state
}
