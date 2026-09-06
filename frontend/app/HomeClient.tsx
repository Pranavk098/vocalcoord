'use client'
import { useState, useEffect, useRef } from 'react'
import { ConversationProvider } from '@elevenlabs/react'
import { DriverView } from '@/components/DriverView'
import { MissionControl } from '@/components/MissionControl'
import { useConversation } from '@/hooks/useConversation'
import { useAgentEvents } from '@/hooks/useAgentEvents'

function HomeClientInner() {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const agentState = useAgentEvents(conversationId)

  const handleNewSession = (id: string) => {
    setConversationId(null)
    setTimeout(() => setConversationId(id), 0)
  }

  const { status, isSpeaking, start, stop } = useConversation(handleNewSession)

  // Auto-end session once the voice reply has finished playing.
  // Multi-turn: the fault reply ends with a nav yes/no question answered via
  // the confirm_nav_yes_no tool as a real second turn — do NOT end while that
  // answer is still pending (navConfirmed === null and reply is a question).
  // End after the nav turn lands and its speech finishes.
  const spokenRef = useRef(false)
  const awaitingNav = agentState.voiceReply != null
    && agentState.navConfirmed === null
    && agentState.voiceReply.includes('set nav')
    && agentState.voiceReply.trim().endsWith('?')
  useEffect(() => {
    if (!agentState.voiceReply) {
      spokenRef.current = false
      return
    }
    if (isSpeaking) {
      spokenRef.current = true
      return
    }
    if (!spokenRef.current) return  // reply set but ElevenLabs hasn't started speaking yet
    if (awaitingNav) return  // driver owes a yes/no — keep the session open
    // Finished speaking — give a 2.5 s grace period then end cleanly
    const timer = setTimeout(() => stop(), 2500)
    return () => clearTimeout(timer)
  }, [isSpeaking, agentState.voiceReply, awaitingNav, stop])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

      {/* ── HEADER ── */}
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        height: '44px',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '8px', height: '8px',
            borderRadius: '50%',
            background: 'var(--amber)',
          }} />
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.18em',
            color: 'var(--text)',
          }}>
            ELMEEDA VOCALCOORD
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '7px', height: '7px',
            borderRadius: '50%',
            background: status === 'connected' ? 'var(--green)' : 'var(--text-dim)',
            animation: status === 'connected' ? 'elmeeda-pulse 2s ease-in-out infinite' : 'none',
          }} />
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '10px',
            letterSpacing: '0.12em',
            color: 'var(--text-muted)',
          }}>
            {status.toUpperCase()}
          </span>
        </div>
      </header>

      {/* ── SPLIT BODY ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left — 38% */}
        <div style={{
          width: '38%',
          height: '100%',
          borderRight: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          padding: '18px 20px',
          gap: '14px',
          flexShrink: 0,
          overflow: 'hidden',
        }}>
          <DriverView
            status={status}
            isSpeaking={isSpeaking}
            fault={agentState.fault}
            onStart={start}
            onStop={stop}
          />
        </div>

        {/* Right — remaining */}
        <div style={{
          flex: 1,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          padding: '18px 20px',
          gap: '12px',
          overflowY: 'auto',
          minWidth: 0,
        }}>
          <MissionControl agentState={agentState} />
        </div>
      </div>

      <style>{`
        @keyframes elmeeda-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.45; transform: scale(0.8); }
        }
      `}</style>
    </div>
  )
}

export function HomeClient() {
  return (
    <ConversationProvider>
      <HomeClientInner />
    </ConversationProvider>
  )
}
