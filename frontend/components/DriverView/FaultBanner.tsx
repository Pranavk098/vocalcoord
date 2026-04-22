'use client'
import { FaultData } from '@/types/events'

interface FaultBannerProps {
  fault: FaultData | null
}

const SEV_CONFIG = {
  red:      { label: 'RED STOP',   color: 'var(--red)',   bg: 'var(--red-bg)',   borderColor: 'var(--red-border)' },
  yellow:   { label: 'CAUTION',    color: '#F59E0B',      bg: '#1a1200',         borderColor: '#78350f' },
  advisory: { label: 'ADVISORY',   color: 'var(--text-muted)', bg: 'var(--surface)', borderColor: 'var(--border)' },
}

export function FaultBanner({ fault }: FaultBannerProps) {
  if (!fault) return null

  const cfg = SEV_CONFIG[fault.severity]

  return (
    <div style={{
      border: `1px solid ${cfg.borderColor}`,
      background: cfg.bg,
      padding: '13px 15px',
      borderRadius: '2px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* animated top bar */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0,
        height: '2px',
        background: cfg.color,
        animation: fault.severity === 'red' ? 'fault-pulse 1.2s ease-in-out infinite' : 'none',
      }} />

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '9px',
        fontWeight: 700,
        letterSpacing: '0.18em',
        color: cfg.color,
        marginBottom: '5px',
      }}>
        {cfg.label}
      </div>

      <div style={{
        fontSize: '15px',
        fontWeight: 700,
        color: 'var(--text)',
        letterSpacing: '-0.01em',
        marginBottom: '3px',
        lineHeight: 1.2,
      }}>
        {fault.description}
      </div>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '11px',
        color: 'var(--text-muted)',
        letterSpacing: '0.06em',
      }}>
        {fault.code}
      </div>

      <style>{`
        @keyframes fault-pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.2; }
        }
      `}</style>
    </div>
  )
}
