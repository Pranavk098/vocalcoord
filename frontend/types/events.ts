// frontend/types/events.ts

export type AgentName = 'shop_caller' | 'warranty_scout' | 'wellness_copilot' | 'dispatch_relay'
export type AgentStatus = 'standby' | 'active' | 'complete'
export type FaultSeverity = 'red' | 'yellow' | 'advisory'

export interface AgentCardState {
  status: AgentStatus
  message?: string
  tool?: string
  summary?: string
  value?: string
}

export interface FaultData {
  code: string
  severity: FaultSeverity
  description: string
}

export interface EventLogEntry {
  id: number
  timestamp: number
  agent: string
  message: string
}

export interface AgentState {
  fault: FaultData | null
  faultActive: boolean
  routingTo: AgentName[]
  agents: Record<AgentName, AgentCardState>
  eventLog: EventLogEntry[]
  voiceReply: string | null
}

export const initialAgentState: AgentState = {
  fault: null,
  faultActive: false,
  routingTo: [],
  agents: {
    shop_caller:      { status: 'standby' },
    warranty_scout:   { status: 'standby' },
    wellness_copilot: { status: 'standby' },
    dispatch_relay:   { status: 'standby' },
  },
  eventLog: [],
  voiceReply: null,
}

// SSE event union
export type AgentEvent =
  | { type: 'fault_detected';    data: FaultData }
  | { type: 'orchestrator';      data: { intent: string; routing_to: AgentName[] } }
  | { type: 'agent_start';       data: { agent: AgentName; message: string } }
  | { type: 'agent_tool_call';   data: { agent: AgentName; tool: string; args: Record<string, unknown> } }
  | { type: 'agent_result';      data: { agent: AgentName; summary: string; value?: string } }
  | { type: 'agent_complete';    data: { agent: AgentName } }
  | { type: 'voice_reply_ready'; data: { text: string } }
  | { type: 'dispatch_sent';     data: { load_number: string; eta_delay: string } }
  | { type: 'ping' }
