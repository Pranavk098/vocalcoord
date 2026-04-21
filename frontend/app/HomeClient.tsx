// frontend/app/HomeClient.tsx
'use client'
import { useState } from 'react'
import { DriverView } from '@/components/DriverView'
import { MissionControl } from '@/components/MissionControl'
import { useConversation } from '@/hooks/useConversation'
import { useAgentEvents } from '@/hooks/useAgentEvents'

export function HomeClient() {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const agentState = useAgentEvents(conversationId)
  const { status, isSpeaking, start, stop } = useConversation(setConversationId)

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-amber-400" />
          <span className="text-sm font-bold tracking-widest text-zinc-200">ELMEEDA VOCALCOORD</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${status === 'connected' ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'}`} />
          <span className="text-xs font-mono text-zinc-500">{status.toUpperCase()}</span>
        </div>
      </header>

      {/* Split screen */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Driver Reality */}
        <div className="w-2/5 border-r border-zinc-800 p-6">
          <DriverView
            status={status}
            isSpeaking={isSpeaking}
            fault={agentState.fault}
            onStart={start}
            onStop={stop}
          />
        </div>

        {/* Right: Elmeeda Brain */}
        <div className="w-3/5 p-6 overflow-y-auto">
          <MissionControl agentState={agentState} />
        </div>
      </div>
    </div>
  )
}
