/**
 * Animated counter — smooth number transition using requestAnimationFrame.
 */
import { useEffect, useRef, useState } from 'react'

export function AnimatedCounter({ value, duration = 600, formatter, style = {} }) {
  const [display, setDisplay] = useState(value)
  const prevRef = useRef(value)
  const rafRef = useRef(null)

  useEffect(() => {
    if (value === prevRef.current) return

    const start = prevRef.current
    const end = value
    const startTime = performance.now()

    const animate = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      // Ease-out curve
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = start + (end - start) * eased

      setDisplay(formatter ? formatter(current) : current)

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate)
      } else {
        prevRef.current = value
      }
    }

    rafRef.current = requestAnimationFrame(animate)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [value, duration, formatter])

  return <span style={style}>{formatter ? formatter(display) : display}</span>
}

export default AnimatedCounter
