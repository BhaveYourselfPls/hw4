import { SIZES, useSize } from '../size'

/**
 * The size strip that sits under the nav.
 *
 * Unset, it is an invitation. Set, it becomes a quiet status line that explains
 * the badges appearing on every product card.
 */
export default function SizeBar() {
  const { size, setSize, asked, dismiss } = useSize()

  if (size) {
    return (
      <div className="sizebar set">
        <div className="shell sizebar-inner">
          <span className="sizebar-text">
            Showing availability in your size <strong>{size}</strong>
          </span>
          <div className="sizebar-actions">
            {SIZES.map((option) => (
              <button
                key={option}
                className={option === size ? 'sizepick on' : 'sizepick'}
                onClick={() => setSize(option)}
                aria-pressed={option === size}
              >
                {option}
              </button>
            ))}
            <button className="sizebar-link" onClick={() => setSize(null)}>
              Clear
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (asked) return null

  return (
    <div className="sizebar">
      <div className="shell sizebar-inner">
        <span className="sizebar-text">
          <strong>What size do you wear?</strong> We&rsquo;ll show you what&rsquo;s actually in
          stock for you.
        </span>
        <div className="sizebar-actions">
          {SIZES.map((option) => (
            <button key={option} className="sizepick" onClick={() => setSize(option)}>
              {option}
            </button>
          ))}
          <button className="sizebar-link" onClick={dismiss}>
            Not now
          </button>
        </div>
      </div>
    </div>
  )
}
