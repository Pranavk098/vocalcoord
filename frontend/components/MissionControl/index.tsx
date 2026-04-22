'use client'
import { AgentPipeline } from './AgentPipeline'
import { EventLog } from './EventLog'
import { AgentState } from '@/types/events'

interface MissionControlProps {
  agentState: AgentState
}

export function MissionControl({ agentState }: MissionControlProps) {
  return (
    <>
      {/* Panel label */}
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '9px',
        letterSpacing: '0.2em',
        color: 'var(--text-dim)',
        textTransform: 'uppercase',
        flexShrink: 0,
      }}>
        Elmeeda Brain — Multi-Agent Pipeline
      </span>

      {/* Orchestrator strip */}
      {agentState.routingTo.length > 0 && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 10px',
          background: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderLeft: '2px solid var(--amber)',
          borderRadius: '2px',
          flexShrink: 0,
        }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            letterSpacing: '0.14em',
            color: 'var(--amber)',
          }}>
            ORCHESTRATOR
          </span>
          <span style={{ color: 'var(--text-dim)', fontSize: '10px' }}>→</span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            color: 'var(--text-muted)',
          }}>
            [{agentState.routingTo.join(', ')}]
          </span>
        </div>
      )}

      {/* Agent 2×2 grid */}
      <AgentPipeline agents={agentState.agents} />

      {/* Event log */}
      <EventLog entries={agentState.eventLog} />

      {/* Voice reply */}
      {agentState.voiceReply && (
        <div style={{
          border: '1px solid rgba(245,158,11,0.25)',
          borderLeft: '2px solid var(--amber)',
          background: 'rgba(245,158,11,0.04)',
          borderRadius: '2px',
          padding: '12px 14px',
          flexShrink: 0,
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '8.5px',
            letterSpacing: '0.18em',
            color: 'var(--amber)',
            marginBottom: '6px',
          }}>
            CO-PILOT RESPONSE
          </div>
          <p style={{
            fontSize: '12px',
            color: 'var(--text)',
            lineHeight: 1.65,
          }}>
            {agentState.voiceReply}
          </p>
        </div>
      )}
    </>
  )
}
