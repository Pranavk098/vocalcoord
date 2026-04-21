'use client'
import { AgentPipeline } from './AgentPipeline'
import { EventLog } from './EventLog'
import { AgentState } from '@/types/events'

interface MissionControlProps {
  agentState: AgentState
}

export function MissionControl({ agentState }: MissionControlProps) {
  return (
    <div className="flex flex-col gap-4 h-full">
      <div>
        <div className="text-xs font-bold tracking-widest text-zinc-500 mb-3">
          ELMEEDA BRAIN — MULTI-AGENT PIPELINE
        </div>
        {agentState.routingTo.length > 0 && (
          <div className="text-xs text-amber-400 font-mono mb-3">
            ORCHESTRATOR → [{agentState.routingTo.join(', ')}]
          </div>
        )}
        <AgentPipeline agents={agentState.agents} />
      </div>
      <EventLog entries={agentState.eventLog} />
    </div>
  )
}
