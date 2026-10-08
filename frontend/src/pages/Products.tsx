import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchCategories, fetchProducts, type CategoryCount, type ProductSummary } from '../api'
import ProductCard from '../components/ProductCard'
import { useMatches } from '../matches'
import { fitFor, useSize } from '../size'
import { renderInline } from '../markdown'

export default function Products() {
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? 'All'
  const search = params.get('search') ?? ''

  const { matches, query: matchQuery, clear: clearMatches } = useMatches()
  const { size: mySize } = useSize()
  const onlyMySize = params.get('fits') === '1'

  const [draft, setDraft] = useState(search)
  const [products, setProducts] = useState<ProductSummary[]>([])
  const [categories, setCategories] = useState<CategoryCount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => setCategories([]))
  }, [])

  // Keep the box in sync when the URL changes from elsewhere (e.g. a footer link).
  useEffect(() => setDraft(search), [search])

  // Live search: results update as the shopper types, 250ms after they pause.
  // Previously nothing happened until Enter was pressed, which left people
  // typing a term and staring at unchanged results.
  useEffect(() => {
    if (draft === search) return
    const timer = setTimeout(() => update({ search: draft }), 250)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft])

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchProducts({ category, search })
      .then(setProducts)
      .catch(() => setError('Could not reach the product catalogue. Is the backend running?'))
      .finally(() => setLoading(false))
  }, [category, search])

  function update(next: { category?: string; search?: string }) {
    const merged = new URLSearchParams(params)
    const cat = next.category ?? category
    const term = next.search ?? search
    cat && cat !== 'All' ? merged.set('category', cat) : merged.delete('category')
    term ? merged.set('search', term) : merged.delete('search')
    setParams(merged)
  }

  // "In my size" filters against real inventory rather than just hiding things.
  const visible = useMemo(
    () =>
      onlyMySize && mySize
        ? products.filter((p) => fitFor(p, mySize).state !== 'sold-out' && fitFor(p, mySize).state !== 'none')
        : products,
    [products, onlyMySize, mySize],
  )

  const total = useMemo(
    () => categories.reduce((sum, c) => sum + c.count, 0),
    [categories],
  )

  return (
    <div className="page">
      <div className="shell">
        <div className="page-head">
          <span className="eyebrow">The Collection</span>
          <h1 style={{ marginTop: 12 }}>Yale Apparel</h1>
          <p>
            Every piece in the Campus Customs catalogue, from $32 tees to $98 jackets. Pick a
            category or search by color, sport, school or style.
          </p>
        </div>

        {matches.length > 0 && (
          <section className="match-band">
            <div className="section-head">
              <div>
                <span className="eyebrow">From your chat</span>
                <h2 style={{ fontSize: 21, marginTop: 8 }}>
                  {matchQuery ? `“${matchQuery}”` : 'What the assistant found'}
                </h2>
                <p className="count" style={{ marginTop: 6 }}>
                  {matches.length} {matches.length === 1 ? 'match' : 'matches'} from the merch
                  assistant.
                </p>
              </div>
              <button className="chip" onClick={clearMatches}>
                Clear
              </button>
            </div>

            <div className="grid">
              {matches.map((product) => (
                <div key={product.product_id} className="match-cell">
                  <ProductCard product={product} />
                  {product.note && <p className="match-note">{renderInline(product.note)}</p>}
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="toolbar">
          <div className="chips">
            <button
              className={category === 'All' ? 'chip on' : 'chip'}
              onClick={() => update({ category: 'All' })}
            >
              All{total ? ` (${total})` : ''}
            </button>
            {categories.map((c) => (
              <button
                key={c.category}
                className={category === c.category ? 'chip on' : 'chip'}
                onClick={() => update({ category: c.category })}
              >
                {c.category} ({c.count})
              </button>
            ))}

            {mySize && (
              <button
                className={onlyMySize ? 'chip fits on' : 'chip fits'}
                onClick={() => {
                  const next = new URLSearchParams(params)
                  onlyMySize ? next.delete('fits') : next.set('fits', '1')
                  setParams(next)
                }}
                aria-pressed={onlyMySize}
              >
                ✦ In my size ({mySize})
              </button>
            )}
          </div>

          <form
            className="search-wrap"
            onSubmit={(e) => {
              e.preventDefault()
              update({ search: draft })
            }}
          >
            <input
              className="search"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Search navy, hockey, grandma, quarter-zip…"
              aria-label="Search products"
            />
            {draft && (
              <button
                type="button"
                className="search-clear"
                onClick={() => setDraft('')}
                aria-label="Clear search"
              >
                ×
              </button>
            )}
          </form>
        </div>

        {/* Active filters, always visible and individually removable, so it is
            never a mystery why the grid is showing what it is showing. */}
        {(category !== 'All' || search) && (
          <div className="active-filters">
            <span className="active-filters-label">Filtering by</span>
            {category !== 'All' && (
              <button className="filter-pill" onClick={() => update({ category: 'All' })}>
                {category} <span aria-hidden>×</span>
              </button>
            )}
            {search && (
              <button className="filter-pill" onClick={() => update({ search: '' })}>
                “{search}” <span aria-hidden>×</span>
              </button>
            )}
            <button
              className="filter-reset"
              onClick={() => update({ category: 'All', search: '' })}
            >
              Clear all
            </button>
          </div>
        )}

        {!loading && !error && (
          <p className="count" style={{ marginBottom: 20 }} aria-live="polite">
            {visible.length} {visible.length === 1 ? 'product' : 'products'}
            {category !== 'All' && ` in ${category}`}
            {search && ` matching “${search}”`}
          </p>
        )}

        {error ? (
          <div className="state">
            <h3>Catalogue unavailable</h3>
            <p>{error}</p>
          </div>
        ) : loading ? (
          <div className="grid">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="skeleton" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <div className="state">
            <h3>Nothing matched that</h3>
            <p>Try a broader term, or clear your filters to see all {total} products.</p>
          </div>
        ) : (
          <div className="grid">
            {visible.map((p) => (
              <ProductCard key={p.product_id} product={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
