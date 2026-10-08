import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts, type ProductSummary } from '../api'
import ProductCard from '../components/ProductCard'
import GameCountdown from '../components/GameCountdown'

// Scrolling ribbon under the hero — the catalogue's own vocabulary, which is
// also a plain-language index of what the store actually covers.
const MARQUEE = [
  'Residential Colleges',
  'Varsity Sports',
  'Yale Mom',
  'The Game',
  'Graduate Schools',
  'Screen Printed In-House',
  'Yale Dad',
  'Since 1975',
]

const TILES = [
  {
    title: 'Layer Up',
    body: 'Crewnecks, hoodies and quarter-zips built for a New Haven winter.',
    to: '/products?category=Hoodies',
    cta: 'Shop warm layers',
  },
  {
    title: 'Show Your Colors',
    body: 'Tees and long sleeves carrying the Yale wordmark, from everyday to game day.',
    to: '/products?category=T-Shirts',
    cta: 'Shop tees',
  },
  {
    title: 'Family Pride',
    body: 'Yale Mom, Dad, Grandma, Grandpa and more — the gift that always fits the occasion.',
    to: '/products?search=mom',
    cta: 'Shop relatives',
  },
]

function Row({ title, blurb, link, products, loading }: {
  title: string
  blurb: string
  link: string
  products: ProductSummary[]
  loading: boolean
}) {
  return (
    <section className="section">
      <div className="shell">
        <div className="section-head">
          <div>
            <h2>{title}</h2>
            <p style={{ color: 'var(--muted)', margin: '8px 0 0', fontSize: 15 }}>{blurb}</p>
          </div>
          <Link to={link}>Shop all →</Link>
        </div>
        <div className="grid">
          {loading
            ? Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton" />)
            : products.map((p) => <ProductCard key={p.product_id} product={p} />)}
        </div>
      </div>
    </section>
  )
}

export default function Home() {
  const [hoodies, setHoodies] = useState<ProductSummary[]>([])
  const [tees, setTees] = useState<ProductSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetchProducts({ category: 'Hoodies' }),
      fetchProducts({ category: 'Crewnecks' }),
    ])
      .then(([h, c]) => {
        setHoodies(h.slice(0, 4))
        setTees(c.slice(0, 4))
      })
      .catch(() => {
        /* backend offline — the rows just stay empty */
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <section className="hero">
        {/* Oversized year set behind the headline — the shop's founding date as
            a piece of architecture rather than a footnote. */}
        <span className="hero-year" aria-hidden>
          1975
        </span>

        <div className="shell hero-content">
          <span className="eyebrow">Officially Licensed · New Haven, Connecticut</span>
          <h1 style={{ marginTop: 16 }}>
            Fifty years on the
            <br />
            same <em>corner.</em>
          </h1>
          <p>
            Campus Customs has outfitted students, parents and alumni from one storefront on
            Broadway since 1975. Printed and embroidered in our own shop next door — so the thing
            you order is made a few steps from where you&rsquo;ll wear it.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary" to="/products">
              Shop the collection
            </Link>
            <Link className="btn btn-ghost" to="/about">
              Our story
            </Link>
          </div>
        </div>

        <div className="marquee" aria-hidden>
          <div className="marquee-track">
            {Array.from({ length: 2 }, (_, copy) => (
              <span key={copy}>
                {MARQUEE.map((word) => (
                  <span key={word} className="marquee-item">
                    {word}
                    <i>◆</i>
                  </span>
                ))}
              </span>
            ))}
          </div>
        </div>
      </section>

      <GameCountdown />

      <div className="shell">
        <div className="tiles">
          {TILES.map((tile) => (
            <div key={tile.title} className="tile">
              <h3>{tile.title}</h3>
              <p>{tile.body}</p>
              <Link to={tile.to}>{tile.cta} →</Link>
            </div>
          ))}
        </div>
      </div>

      <Row
        title="Hoodies we live in"
        blurb="Heavyweight fleece, kangaroo pockets and a wordmark you can spot across the Green."
        link="/products?category=Hoodies"
        products={hoodies}
        loading={loading}
      />

      <div className="band">
        <Row
          title="Classic crewnecks"
          blurb="Casual comfort, classic Bulldog pride — the sweatshirt that outlasts four years."
          link="/products?category=Crewnecks"
          products={tees}
          loading={loading}
        />
      </div>

      <section className="section">
        <div className="shell" style={{ textAlign: 'center' }}>
          <span className="eyebrow">Come visit us</span>
          <h2 style={{ fontSize: 28, margin: '14px 0 12px' }}>57 Broadway, New Haven</h2>
          <p style={{ color: 'var(--muted)', maxWidth: '52ch', margin: '0 auto 24px', lineHeight: 1.7 }}>
            Our original storefront sits across from campus, with the print shop right next door.
            Stop in to see the fabrics in person, or browse the full catalogue online.
          </p>
          <Link className="btn btn-dark" to="/products">
            Browse all products
          </Link>
        </div>
      </section>
    </>
  )
}
