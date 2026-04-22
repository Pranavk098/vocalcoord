'use client'
import { useEffect, useRef } from 'react'
import { EventLogEntry } from '@/types/events'

interface EventLogProps {
  entries: EventLogEntry[]
}

const AGENT_PILL: Record<string, { label: string; bg: string; color: string }> = {
  shop_caller:      { label: 'SHOP',     bg: 'rgba(59,130,246,0.15)',  color: '#60a5fa' },
  warranty_scout:   { label: 'WARRANTY', bg: 'rgba(168,85,247,0.15)', color: '#c084fc' },
  dispatch_relay:   { label: 'DISPATCH', bg: 'rgba(245,158,11,0.15)', color: '#fbbf24' },
  wellness_copilot: { label: 'WELLNESS', bg: 'rgba(34,197,94,0.15)',  color: '#4ade80' },
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
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '2px',
      padding: '10px 12px',
      height: '120px',
      overflowY: 'auto',
      flexShrink: 0,
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '8.5px',
        letterSpacing: '0.18em',
        color: 'var(--text-dim)',
        marginBottom: '8px',
      }}>
        EVENT LOG
      </div>

      {entries.length === 0 ? (
        <p style={{ fontSize: '11px', color: 'var(--text-dim)', fontStyle: 'italic' }}>
          Awaiting activity...
        </p>
      ) : (
        entries.map((entry) => {
          const pill = AGENT_PILL[entry.agent]
          return (
            <div key={entry.id} style={{
              display: 'flex',
              gap: '8px',
              fontSize: '11px',
              marginBottom: '5px',
              alignItems: 'baseline',
            }}>
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: 'var(--text-dim)',
                flexShrink: 0,
                width: '60px',
              }}>
                {formatTime(entry.timestamp)}
              </span>

              {pill && (
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '8px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  padding: '1px 5px',
                  borderRadius: '2px',
                  flexShrink: 0,
                  background: pill.bg,
                  color: pill.color,
                }}>
                  {pill.label}
                </span>
              )}

              <span style={{ color: 'var(--text-muted)', lineHeight: 1.3 }}>
                {entry.message}
              </span>
            </div>
          )
        })
      )}
      <div ref={bottomRef} />
    </div>
  )
}
