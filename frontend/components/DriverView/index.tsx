// frontend/components/DriverView/index.tsx
'use client'
import { motion } from 'framer-motion'
import { Mic, MicOff, Radio } from 'lucide-react'
import { AudioVisualizer } from './AudioVisualizer'
import { FaultBanner } from './FaultBanner'
import { ConversationStatus } from '@/hooks/useConversation'
import { FaultData } from '@/types/events'
import { cn } from '@/lib/utils'

interface DriverViewProps {
  status: ConversationStatus
  isSpeaking: boolean
  fault: FaultData | null
  onStart: () => void
  onStop: () => void
}

const STATUS_LABEL: Record<ConversationStatus, string> = {
  idle:       'CO-PILOT STANDING BY',
  connecting: 'CONNECTING...',
  connected:  'CO-PILOT ACTIVE',
  error:      'CONNECTION ERROR',
}

export function DriverView({ status, isSpeaking, fault, onStart, onStop }: DriverViewProps) {
  const isActive = status === 'connected'

  return (
    <div className="flex flex-col h-full">
      <div className="text-xs font-bold tracking-widest text-zinc-500 mb-3">
        THE CAB — DRIVER REALITY
      </div>

      <FaultBanner fault={fault} />

      <div className="flex-1 flex flex-col items-center justify-center gap-6">
        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <motion.div
            className={cn(
              'w-3 h-3 rounded-full',
              status === 'idle'       && 'bg-zinc-600',
              status === 'connecting' && 'bg-yellow-400',
              status === 'connected'  && 'bg-emerald-400',
              status === 'error'      && 'bg-red-500',
            )}
            animate={status === 'connected' ? { scale: [1, 1.2, 1] } : {}}
            transition={{ repeat: Infinity, duration: 2 }}
          />
          <span className="text-xs font-mono tracking-widest text-zinc-400">
            {STATUS_LABEL[status]}
          </span>
        </div>

        {/* Audio visualizer */}
        <AudioVisualizer active={isActive} />

        {/* Speaking indicator */}
        {isActive && (
          <div className="flex items-center gap-2">
            <Radio className={cn('w-4 h-4', isSpeaking ? 'text-amber-400 animate-pulse' : 'text-zinc-600')} />
            <span className="text-xs font-mono text-zinc-500">
              {isSpeaking ? 'CO-PILOT SPEAKING' : 'LISTENING...'}
            </span>
          </div>
        )}

        {/* Start / Stop button */}
        {status === 'idle' || status === 'error' ? (
          <button
            onClick={onStart}
            className="flex items-center gap-2 px-6 py-3 rounded-lg bg-amber-400 text-zinc-950 font-bold text-sm tracking-wider hover:bg-amber-300 transition-colors"
          >
            <Mic className="w-4 h-4" />
            START CO-PILOT
          </button>
        ) : (
          <button
            onClick={onStop}
            disabled={status === 'connecting'}
            className="flex items-center gap-2 px-6 py-3 rounded-lg border border-zinc-600 text-zinc-400 text-sm tracking-wider hover:border-zinc-400 transition-colors disabled:opacity-40"
          >
            <MicOff className="w-4 h-4" />
            END SESSION
          </button>
        )}
      </div>
    </div>
  )
}
