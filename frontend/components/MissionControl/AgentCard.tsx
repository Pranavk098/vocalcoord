'use client'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { AgentCardState, AgentName } from '@/types/events'

const AGENT_LABELS: Record<AgentName, string> = {
  shop_caller:      'SHOP CALLER',
  warranty_scout:   'WARRANTY SCOUT',
  wellness_copilot: 'WELLNESS CO-PILOT',
  dispatch_relay:   'DISPATCH RELAY',
}

interface AgentCardProps {
  name: AgentName
  state: AgentCardState
}

export function AgentCard({ name, state }: AgentCardProps) {
  const { status, message, tool, summary, value } = state

  return (
    <motion.div
      layout
      className={cn(
        'rounded-lg border p-4 min-h-[100px] transition-colors duration-300',
        status === 'standby' && 'border-zinc-700 opacity-40',
        status === 'active'  && 'border-amber-400 shadow-lg shadow-amber-400/10',
        status === 'complete'&& 'border-emerald-400 shadow-md shadow-emerald-400/10',
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-bold tracking-widest text-zinc-400">
          {AGENT_LABELS[name]}
        </span>
        <div>
          {status === 'active' && (
            <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-ping" />
          )}
          {status === 'complete' && (
            <span className="text-emerald-400 text-sm font-bold">✓</span>
          )}
        </div>
      </div>

      {status === 'active' && (
        <div className="space-y-1">
          {message && <p className="text-xs text-zinc-300">{message}</p>}
          {tool && (
            <p className="text-xs text-zinc-500 font-mono">→ {tool}()</p>
          )}
          <div className="mt-2 h-1 w-full bg-zinc-800 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-amber-400 rounded-full"
              initial={{ width: '0%' }}
              animate={{ width: '85%' }}
              transition={{ duration: 2, ease: 'easeOut' }}
            />
          </div>
        </div>
      )}

      {status === 'complete' && (
        <div className="space-y-1">
          {summary && <p className="text-xs text-zinc-200">{summary}</p>}
          {value && <p className="text-xs text-emerald-400 font-mono">{value}</p>}
        </div>
      )}
    </motion.div>
  )
}
