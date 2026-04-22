'use client'
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

  const borderColor =
    status === 'active'   ? 'var(--amber)' :
    status === 'complete' ? 'var(--green)'  :
    'var(--border)'

  const topBar =
    status === 'active'   ? 'var(--amber)' :
    status === 'complete' ? 'var(--green)'  :
    'var(--border)'

  const dotColor =
    status === 'active'   ? 'var(--amber)' :
    status === 'complete' ? 'var(--green)'  :
    'var(--text-dim)'

  return (
    <div style={{
      border: `1px solid ${borderColor}`,
      background: 'var(--surface)',
      padding: '12px 14px',
      minHeight: '88px',
      borderRadius: '2px',
      position: 'relative',
      overflow: 'hidden',
      opacity: status === 'standby' ? 0.4 : 1,
      transition: 'border-color 250ms, opacity 250ms',
    }}>
      {/* top accent line */}
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0,
        height: '1px',
        background: topBar,
        transition: 'background 250ms',
      }} />

      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '8.5px',
          fontWeight: 700,
          letterSpacing: '0.18em',
          color: 'var(--text-muted)',
        }}>
          {AGENT_LABELS[name]}
        </span>
        <div style={{
          width: '6px', height: '6px',
          borderRadius: '50%',
          background: dotColor,
          animation: status === 'active' ? 'elmeeda-pulse 0.9s ease-in-out infinite' : 'none',
        }} />
      </div>

      {/* active body */}
      {status === 'active' && (
        <div>
          {message && (
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '5px', lineHeight: 1.4 }}>
              {message}
            </p>
          )}
          {tool && (
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-dim)', marginBottom: '4px' }}>
              → {tool}()
            </p>
          )}
        </div>
      )}

      {/* complete body */}
      {status === 'complete' && (
        <div>
          {summary && (
            <p style={{ fontSize: '12px', color: 'var(--text)', fontWeight: 500, marginBottom: '3px', lineHeight: 1.3 }}>
              {summary}
            </p>
          )}
          {value && (
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--green)', fontWeight: 700 }}>
              {value}
            </p>
          )}
        </div>
      )}

      {/* scan bar — only when active */}
      {status === 'active' && (
        <div style={{
          position: 'absolute',
          bottom: 0, left: 0, right: 0,
          height: '1px',
          background: 'var(--border)',
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: '50%',
            background: 'var(--amber)',
            animation: 'elmeeda-scan 1.4s ease-in-out infinite',
          }} />
        </div>
      )}

      <style>{`
        @keyframes elmeeda-scan {
          0%   { transform: translateX(-120%); }
          100% { transform: translateX(260%); }
        }
      `}</style>
    </div>
  )
}
