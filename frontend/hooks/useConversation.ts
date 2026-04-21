// frontend/hooks/useConversation.ts
'use client'
import { useConversation as useElevenLabs } from '@elevenlabs/react'
import { useCallback, useState } from 'react'

export type ConversationStatus = 'idle' | 'connecting' | 'connected' | 'error'

export function useConversation(onConversationId: (id: string) => void) {
  const [status, setStatus] = useState<ConversationStatus>('idle')
  const [isSpeaking, setIsSpeaking] = useState(false)

  const conversation = useElevenLabs({
    onConnect: (props: { conversationId?: string }) => {
      setStatus('connected')
      if (props.conversationId) {
        onConversationId(props.conversationId)
      }
    },
    onDisconnect: () => {
      setStatus('idle')
      setIsSpeaking(false)
    },
    onError: () => {
      setStatus('error')
    },
    // @ts-ignore
    onMessage: (msg: { type: string }) => {
      setIsSpeaking(msg.type === 'agent_response')
    },
  })

  const start = useCallback(async () => {
    setStatus('connecting')
    const agentId = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID
    if (!agentId) throw new Error('NEXT_PUBLIC_ELEVENLABS_AGENT_ID not set')
    await conversation.startSession({ agentId })
  }, [conversation])

  const stop = useCallback(async () => {
    await conversation.endSession()
    setStatus('idle')
  }, [conversation])

  return { status, isSpeaking, start, stop }
}
