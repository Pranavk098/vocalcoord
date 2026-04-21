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

    case 'dispatch_sent': {
      const entry = {
        id: _nextId++,
        timestamp: Date.now(),
        agent: 'dispatch_relay',
        message: `${event.data.load_number} notified — +${event.data.eta_delay} delay`
      }
      return { ...state, eventLog: [...state.eventLog, entry] }
    }

    default:
      return state
  }
}

export function useAgentEvents(conversationId: string | null) {
  const [state, dispatch] = useReducer(reducer, initialAgentState)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    dispatch({ type: 'RESET' })
    if (!conversationId) return

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000'
    const es = new EventSource(`${backendUrl}/events/${conversationId}`)
    esRef.current = es

    es.onmessage = (e) => {
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
