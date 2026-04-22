'use client'
import { AgentCard } from './AgentCard'
import { AgentState, AgentName } from '@/types/events'

const AGENT_ORDER: AgentName[] = ['shop_caller', 'warranty_scout', 'wellness_copilot', 'dispatch_relay']

interface AgentPipelineProps {
  agents: AgentState['agents']
}

export function AgentPipeline({ agents }: AgentPipelineProps) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: '8px',
      flexShrink: 0,
    }}>
      {AGENT_ORDER.map((name) => (
        <AgentCard key={name} name={name} state={agents[name]} />
      ))}
    </div>
  )
}
