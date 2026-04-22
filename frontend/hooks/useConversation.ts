// frontend/hooks/useConversation.ts
'use client'
import { useConversation as useElevenLabs } from '@elevenlabs/react'
import { useCallback } from 'react'

// Map v1.1.1 status ('disconnected') to our UI type ('idle')
export type ConversationStatus = 'idle' | 'connecting' | 'connected' | 'error'

function mapStatus(raw: string): ConversationStatus {
  if (raw === 'disconnected') return 'idle'
  if (raw === 'connecting' || raw === 'connected' || raw === 'error') return raw
  return 'idle'
}

export function useConversation(onConversationId: (id: string) => void) {
  const { startSession, endSession, status: rawStatus, isSpeaking } = useElevenLabs({
    onConnect: (props: { conversationId?: string }) => {
      const id = props.conversationId
      if (id) {
        console.log('[ElevenLabs] conversationId from onConnect:', id)
        onConversationId(id)
        // Register with backend so webhook events route to this SSE stream
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000'
        fetch(`${backendUrl}/session/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ conversationId: id }),
        }).catch(console.error)
      }
    },
  })

  const status = mapStatus(rawStatus)

  const start = useCallback(async () => {
    const agentId = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID
    if (!agentId) throw new Error('NEXT_PUBLIC_ELEVENLABS_AGENT_ID not set')
    startSession({ agentId })
  }, [startSession])

  const stop = useCallback(async () => {
    endSession()
  }, [endSession])

  return { status, isSpeaking, start, stop }
}
