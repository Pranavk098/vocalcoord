// frontend/components/DriverView/FaultBanner.tsx
'use client'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, AlertCircle, Info } from 'lucide-react'
import { FaultData } from '@/types/events'
import { cn } from '@/lib/utils'

interface FaultBannerProps {
  fault: FaultData | null
}

const SEVERITY_CONFIG = {
  red:      { bg: 'bg-red-950 border-red-500',    text: 'text-red-400',    icon: AlertTriangle, label: 'RED STOP' },
  yellow:   { bg: 'bg-yellow-950 border-yellow-500', text: 'text-yellow-400', icon: AlertCircle,  label: 'CAUTION' },
  advisory: { bg: 'bg-zinc-900 border-zinc-600',  text: 'text-zinc-400',   icon: Info,           label: 'ADVISORY' },
}

export function FaultBanner({ fault }: FaultBannerProps) {
  const config = fault ? SEVERITY_CONFIG[fault.severity] : null

  return (
    <AnimatePresence>
      {fault && config && (
        <motion.div
          initial={{ y: -80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -80, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className={cn(
            'w-full rounded-lg border px-4 py-3 mb-4',
            config.bg
          )}
        >
          <div className="flex items-center gap-3">
            <config.icon className={cn('w-5 h-5 shrink-0', config.text)} />
            <div>
              <div className={cn('text-xs font-bold tracking-widest', config.text)}>
                {config.label}
              </div>
              <div className="text-sm text-zinc-100 font-medium">{fault.description}</div>
              <div className="text-xs text-zinc-400 font-mono">{fault.code}</div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
