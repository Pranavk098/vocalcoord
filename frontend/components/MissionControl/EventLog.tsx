'use client'
import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { EventLogEntry } from '@/types/events'

interface EventLogProps {
  entries: EventLogEntry[]
}

const AGENT_COLORS: Record<string, string> = {
  shop_caller:      'text-blue-400',
  warranty_scout:   'text-purple-400',
  wellness_copilot: 'text-green-400',
  dispatch_relay:   'text-orange-400',
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function EventLog({ entries }: EventLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-700 p-3 h-48 overflow-y-auto">
      <div className="text-xs font-bold tracking-widest text-zinc-500 mb-2">EVENT LOG</div>
      {entries.length === 0 && (
        <p className="text-xs text-zinc-600 italic">Awaiting activity...</p>
      )}
      <AnimatePresence initial={false}>
        {entries.map((entry) => (
          <motion.div
            key={entry.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex gap-2 text-xs mb-1"
          >
            <span className="text-zinc-600 shrink-0 font-mono">{formatTime(entry.timestamp)}</span>
            <span className={AGENT_COLORS[entry.agent] ?? 'text-zinc-400'}>✓</span>
            <span className="text-zinc-300">{entry.message}</span>
          </motion.div>
        ))}
      </AnimatePresence>
      <div ref={bottomRef} />
    </div>
  )
}
