'use client'
import { AudioVisualizer } from './AudioVisualizer'
import { FaultBanner } from './FaultBanner'
import { ConversationStatus } from '@/hooks/useConversation'
import { FaultData } from '@/types/events'

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

const ORB_COLOR: Record<ConversationStatus, string> = {
  idle:       '#4B5563',
  connecting: 'var(--amber)',
  connected:  'var(--green)',
  error:      'var(--red)',
}

export function DriverView({ status, isSpeaking, fault, onStart, onStop }: DriverViewProps) {
  const isActive = status === 'connected'

  return (
    <>
      {/* Panel label */}
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '9px',
        letterSpacing: '0.2em',
        color: 'var(--text-dim)',
        textTransform: 'uppercase',
      }}>
        The Cab — Driver Reality
      </span>

      {/* Fault banner */}
      <FaultBanner fault={fault} />

      {/* Center cluster */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '22px',
      }}>

        {/* Status orb + label */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '11px', height: '11px',
            borderRadius: '50%',
            background: ORB_COLOR[status],
            animation: isActive ? 'elmeeda-pulse 2s ease-in-out infinite' : 'none',
            flexShrink: 0,
          }} />
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            letterSpacing: '0.16em',
            color: 'var(--text-muted)',
          }}>
            {STATUS_LABEL[status]}
          </span>
        </div>

        {/* Audio visualizer */}
        <AudioVisualizer active={isActive} />

        {/* Listening / speaking indicator */}
        {isActive && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: '6px', height: '6px',
              borderRadius: '50%',
              background: 'var(--amber)',
              animation: 'elmeeda-pulse 1s ease-in-out infinite',
            }} />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              letterSpacing: '0.12em',
              color: 'var(--text-muted)',
            }}>
              {isSpeaking ? 'CO-PILOT SPEAKING' : 'LISTENING...'}
            </span>
          </div>
        )}

        {/* Action button */}
        {status === 'idle' || status === 'error' ? (
          <button
            onClick={onStart}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '12px 28px',
              background: 'var(--amber)',
              color: '#0f0f0f',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.14em',
              border: 'none',
              borderRadius: '2px',
              cursor: 'pointer',
            }}
          >
            <MicIcon />
            START CO-PILOT
          </button>
        ) : (
          <button
            onClick={onStop}
            disabled={status === 'connecting'}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '12px 28px',
              background: 'transparent',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.14em',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              cursor: 'pointer',
              opacity: status === 'connecting' ? 0.4 : 1,
            }}
          >
            <MicOffIcon />
            END SESSION
          </button>
        )}

      </div>
    </>
  )
}

function MicIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="22"/>
    </svg>
  )
}

function MicOffIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="1" y1="1" x2="23" y2="23"/>
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/>
      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/>
      <line x1="12" y1="19" x2="12" y2="22"/>
    </svg>
  )
}
