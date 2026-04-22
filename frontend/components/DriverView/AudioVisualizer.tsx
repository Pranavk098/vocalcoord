'use client'
import { useEffect, useRef } from 'react'

interface AudioVisualizerProps {
  active: boolean
  barCount?: number
}

export function AudioVisualizer({ active, barCount = 28 }: AudioVisualizerProps) {
  const barsRef = useRef<HTMLDivElement[]>([])
  const rafRef  = useRef<number | undefined>(undefined)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamRef   = useRef<MediaStream | null>(null)
  const ctxRef      = useRef<AudioContext | null>(null)

  // base heights — sine wave silhouette when idle
  const baseH = Array.from({ length: barCount }, (_, i) => 5 + Math.sin(i * 0.45) * 4)

  useEffect(() => {
    if (!active) {
      stop()
      return
    }

    let mounted = true

    async function setup() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        if (!mounted) { stream.getTracks().forEach(t => t.stop()); return }
        streamRef.current = stream

        const ctx = new AudioContext()
        ctxRef.current = ctx
        const analyser = ctx.createAnalyser()
        analyserRef.current = analyser
        analyser.fftSize = 64
        ctx.createMediaStreamSource(stream).connect(analyser)

        const data = new Uint8Array(analyser.frequencyBinCount)

        const draw = () => {
          rafRef.current = requestAnimationFrame(draw)
          analyser.getByteFrequencyData(data)
          barsRef.current.forEach((bar, i) => {
            if (!bar) return
            const v = data[Math.floor((i / barCount) * data.length)] / 255
            bar.style.height  = `${4 + v * 48}px`
            bar.style.opacity = `${0.3 + v * 0.7}`
          })
        }
        draw()
      } catch {
        // mic denied — use synthetic animation
        let t = 0
        const animate = () => {
          rafRef.current = requestAnimationFrame(animate)
          t += 0.07
          barsRef.current.forEach((bar, i) => {
            if (!bar) return
            const h = 4 + Math.abs(Math.sin(t + i * 0.42)) * 46
            bar.style.height  = `${h}px`
            bar.style.opacity = `${0.35 + Math.abs(Math.sin(t + i * 0.42)) * 0.65}`
          })
        }
        animate()
      }
    }

    setup()

    return () => {
      mounted = false
      stop()
    }
  }, [active, barCount])

  function stop() {
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = undefined }
    streamRef.current?.getTracks().forEach(t => t.stop())
    ctxRef.current?.close()
    streamRef.current = null
    ctxRef.current    = null
    analyserRef.current = null
    barsRef.current.forEach((bar, i) => {
      if (bar) { bar.style.height = `${baseH[i]}px`; bar.style.opacity = '0.3' }
    })
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'center',
      gap: '3px',
      height: '52px',
    }}>
      {Array.from({ length: barCount }).map((_, i) => (
        <div
          key={i}
          ref={el => { if (el) barsRef.current[i] = el }}
          style={{
            width: '4px',
            height: `${baseH[i]}px`,
            borderRadius: '2px',
            background: 'var(--amber)',
            opacity: 0.3,
          }}
        />
      ))}
    </div>
  )
}
