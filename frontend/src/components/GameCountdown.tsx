import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

/**
 * Countdown to The Game — Harvard–Yale, played the Saturday before
 * Thanksgiving.
 *
 * A storefront with no calendar gives nobody a reason to come back on any
 * particular day. This gives the homepage a clock that is always different,
 * tied to the one date every Yale shopper already has an opinion about.
 */

/** Thanksgiving is the fourth Thursday in November; The Game is the Saturday
 *  before it. Computed rather than hardcoded so it never goes stale. */
function gameDate(year: number): Date {
  const november = new Date(Date.UTC(year, 10, 1))
  const firstThursday = 1 + ((4 - november.getUTCDay() + 7) % 7)
  const thanksgiving = firstThursday + 21
  return new Date(Date.UTC(year, 10, thanksgiving - 5, 17, 0, 0)) // noon ET kickoff
}

function nextGame(now: Date): Date {
  const thisYear = gameDate(now.getUTCFullYear())
  return now < thisYear ? thisYear : gameDate(now.getUTCFullYear() + 1)
}

export default function GameCountdown() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const { parts, dateLabel } = useMemo(() => {
    const target = nextGame(now)
    const ms = Math.max(0, target.getTime() - now.getTime())
    const days = Math.floor(ms / 86_400_000)
    const hours = Math.floor((ms % 86_400_000) / 3_600_000)
    const minutes = Math.floor((ms % 3_600_000) / 60_000)
    const seconds = Math.floor((ms % 60_000) / 1000)
    return {
      parts: [
        { value: days, label: days === 1 ? 'Day' : 'Days' },
        { value: hours, label: 'Hrs' },
        { value: minutes, label: 'Min' },
        { value: seconds, label: 'Sec' },
      ],
      dateLabel: target.toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        timeZone: 'UTC',
      }),
    }
  }, [now])

  return (
    <section className="countdown">
      <div className="shell countdown-inner">
        <div className="countdown-copy">
          <span className="eyebrow">The Game · {dateLabel}</span>
          <h2>Dress for the rivalry.</h2>
          <p>
            One Saturday a year, the whole campus wears the same two colors. Get there in
            something that fits.
          </p>
          <Link className="btn btn-primary" to="/products?search=harvard">
            Shop The Game →
          </Link>
        </div>

        <div className="countdown-clock" role="timer" aria-label={`Countdown to The Game on ${dateLabel}`}>
          {parts.map((part) => (
            <div key={part.label} className="tick">
              <span className="tick-value">{String(part.value).padStart(2, '0')}</span>
              <span className="tick-label">{part.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
