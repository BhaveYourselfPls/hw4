import { useState } from 'react'
import { Link } from 'react-router-dom'
import { money, type ProductSummary } from '../api'
import { fitFor, useSize } from '../size'

/** Catalogue colors are free text and inconsistent ("navy" vs "navy blue"), so
 *  match on substrings rather than exact keys. */
export function colorToHex(name: string): string {
  const c = name.toLowerCase()
  if (c.includes('navy')) return '#0f2340'
  if (c.includes('heather') && c.includes('gray')) return '#b9bcc2'
  if (c.includes('charcoal')) return '#45484e'
  if (c.includes('gray') || c.includes('grey')) return '#9ba0a8'
  if (c.includes('white') || c.includes('cream') || c.includes('ivory')) return '#f4f4f5'
  if (c.includes('black')) return '#15161a'
  if (c.includes('royal')) return '#1d4ed8'
  if (c.includes('light blue') || c.includes('sky')) return '#8fc0e8'
  if (c.includes('blue')) return '#286dc0'
  if (c.includes('red') || c.includes('crimson')) return '#b4252b'
  if (c.includes('green')) return '#2b6a4a'
  if (c.includes('pink')) return '#e6a0b8'
  if (c.includes('gold') || c.includes('yellow')) return '#d7a93d'
  if (c.includes('orange')) return '#d2762c'
  if (c.includes('purple')) return '#5b4a95'
  if (c.includes('brown') || c.includes('tan') || c.includes('khaki')) return '#9c7a53'
  return '#d4d7dd'
}

/** One of the 102 catalogue rows has no .jpg on disk, so every image needs a
 *  graceful fallback rather than a broken-image icon. */
export function ProductImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return <div className="card-fallback">Photo<br />coming soon</div>
  }
  return <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />
}

export default function ProductCard({ product }: { product: ProductSummary }) {
  const { size } = useSize()
  const fit = fitFor(product, size)

  return (
    <Link
      to={`/products/${product.product_id}`}
      className={fit.state === 'sold-out' ? 'card is-unavailable' : 'card'}
    >
      <div className="card-media">
        <ProductImage src={product.image_url} alt={product.name} />
        {/* Availability in the shopper's own size, read straight from
            inventory. Without a saved size, nothing shows. */}
        {fit.state !== 'none' && <span className={`fit fit-${fit.state}`}>{fit.label}</span>}
      </div>
      <div className="card-body">
        <div className="card-cat">{product.category}</div>
        <div className="card-name">{product.name}</div>
        <div className="card-price">{money(product.price)}</div>
        <div className="swatches">
          {product.colors.slice(0, 5).map((color) => (
            <span
              key={color}
              className="swatch"
              title={color}
              style={{ background: colorToHex(color) }}
            />
          ))}
        </div>
      </div>
    </Link>
  )
}
