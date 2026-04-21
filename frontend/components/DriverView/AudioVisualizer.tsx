// frontend/components/DriverView/AudioVisualizer.tsx
'use client'
import { useEffect, useRef } from 'react'

interface AudioVisualizerProps {
  active: boolean
  barCount?: number
}

export function AudioVisualizer({ active, barCount = 24 }: AudioVisualizerProps) {
  const barsRef = useRef<HTMLDivElement[]>([])
  const animRef = useRef<number>(undefined)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    if (!active) {
      cancelAnimationFrame(animRef.current!)
      barsRef.current.forEach((bar, i) => {
        if (bar) {
          bar.style.height = `${8 + Math.sin(i * 0.4) * 4}px`
          bar.style.opacity = '0.3'
        }
      })
      return
    }

    let audioCtx: AudioContext
    let source: MediaStreamAudioSourceNode

    async function setup() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        streamRef.current = stream
        audioCtx = new AudioContext()
        analyserRef.current = audioCtx.createAnalyser()
        analyserRef.current.fftSize = 64
        source = audioCtx.createMediaStreamSource(stream)
        source.connect(analyserRef.current)

        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)

        const draw = () => {
          animRef.current = requestAnimationFrame(draw)
          analyserRef.current!.getByteFrequencyData(dataArray)

          barsRef.current.forEach((bar, i) => {
            if (!bar) return
            const idx = Math.floor((i / barCount) * dataArray.length)
            const value = dataArray[idx] / 255
            const height = 4 + value * 56
            bar.style.height = `${height}px`
            bar.style.opacity = `${0.4 + value * 0.6}`
          })
        }
        draw()
      } catch {
        const animate = () => {
          animRef.current = requestAnimationFrame(animate)
          barsRef.current.forEach((bar, i) => {
            if (!bar) return
            const t = Date.now() / 400
            const h = 8 + Math.sin(t + i * 0.5) * 20
            bar.style.height = `${h}px`
            bar.style.opacity = '0.6'
          })
        }
        animate()
      }
    }

    setup()

    return () => {
      cancelAnimationFrame(animRef.current!)
      streamRef.current?.getTracks().forEach(t => t.stop())
      audioCtx?.close()
    }
  }, [active, barCount])

  return (
    <div className="flex items-end justify-center gap-1 h-16">
      {Array.from({ length: barCount }).map((_, i) => (
        <div
          key={i}
          ref={el => { if (el) barsRef.current[i] = el }}
          className="w-1.5 rounded-full bg-amber-400 transition-none"
          style={{ height: '8px', opacity: 0.3 }}
        />
      ))}
    </div>
  )
}
