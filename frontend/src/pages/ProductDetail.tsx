import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  fetchProduct,
  fetchRelated,
  money,
  type ProductDetail as Detail,
  type ProductSummary,
} from '../api'
import ProductCard, { ProductImage, colorToHex } from '../components/ProductCard'
import { useSize } from '../size'

export default function ProductDetail() {
  const { productId = '' } = useParams()
  const { size: myProduct } = useSize()
  const [product, setProduct] = useState<Detail | null>(null)
  const [related, setRelated] = useState<ProductSummary[]>([])
  const [size, setSize] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setSize(null)
    window.scrollTo({ top: 0 })

    fetchProduct(productId)
      .then((data) => {
        setProduct(data)
        // Preselect the shopper's own size when it is available, otherwise the
        // first size that is — so the page opens on the thing they can buy.
        const mine = myProduct && data.available_sizes.includes(myProduct) ? myProduct : null
        setSize(mine ?? data.available_sizes[0] ?? null)
      })
      .catch(() => setError('We could not find that product.'))
      .finally(() => setLoading(false))

    fetchRelated(productId).then(setRelated).catch(() => setRelated([]))
  }, [productId, myProduct])

  if (loading) {
    return (
      <div className="page">
        <div className="shell state">Loading…</div>
      </div>
    )
  }

  if (error || !product) {
    return (
      <div className="page">
        <div className="shell state">
          <h3>Product not found</h3>
          <p>{error}</p>
          <Link className="btn btn-dark" to="/products" style={{ marginTop: 18 }}>
            Back to all products
          </Link>
        </div>
      </div>
    )
  }

  const selected = product.sizes.find((s) => s.size === size)

  return (
    <div className="page">
      <div className="shell">
        <div className="crumbs">
          <Link to="/products">Products</Link>
          <span>/</span>
          <Link to={`/products?category=${encodeURIComponent(product.category)}`}>
            {product.category}
          </Link>
          <span>/</span>
          {product.name}
        </div>

        <div className="detail">
          <div className="detail-media">
            <ProductImage src={product.image_url} alt={product.name} />
          </div>

          <div>
            <span className="eyebrow">{product.garment_type}</span>
            <h1>{product.name}</h1>
            <div className="detail-price">{money(product.price)}</div>
            <p className="detail-desc">{product.description}</p>

            <div className="colorline">
              <strong style={{ color: 'var(--ink)' }}>Colors:</strong>
              {product.colors.map((color) => (
                <span key={color} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span className="swatch" style={{ background: colorToHex(color) }} />
                  {color}
                </span>
              ))}
            </div>

            <div className="meta">
              <h4>Select a size</h4>
              <div className="sizes">
                {product.sizes.map((s) => (
                  <button
                    key={s.size}
                    className={
                      [
                        'size',
                        size === s.size ? 'on' : '',
                        s.size === myProduct ? 'mine' : '',
                      ]
                        .filter(Boolean)
                        .join(' ')
                    }
                    disabled={!s.in_stock}
                    title={s.in_stock ? `${s.quantity} in stock` : 'Sold out'}
                    onClick={() => setSize(s.size)}
                  >
                    {s.size}
                    {s.size === myProduct && <i className="size-mine" aria-label="your size" />}
                  </button>
                ))}
              </div>

              {selected ? (
                selected.quantity > 5 ? (
                  <p className="stock in">In stock — ready to ship in {selected.size}.</p>
                ) : (
                  <p className="stock low">
                    Only {selected.quantity} left in {selected.size}.
                  </p>
                )
              ) : (
                <p className="stock out">Select an available size to see stock.</p>
              )}

              <p className="count" style={{ marginTop: 10 }}>
                {product.total_quantity} units on hand across {product.available_sizes.length} of{' '}
                {product.sizes.length} sizes.
              </p>

              <button className="btn btn-dark btn-block" style={{ marginTop: 18 }} disabled={!selected}>
                {selected ? `Add ${selected.size} to bag` : 'Select a size'}
              </button>
            </div>

            <div className="meta">
              <h4>Tags</h4>
              <div className="tags">
                {product.search_tags.map((tag) => (
                  <Link key={tag} to={`/products?search=${encodeURIComponent(tag)}`} className="tag">
                    {tag}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>

        {related.length > 0 && (
          <section className="section" style={{ paddingBottom: 0 }}>
            <div className="section-head">
              <h2>You might also like</h2>
              <Link to={`/products?category=${encodeURIComponent(product.category)}`}>
                More {product.category.toLowerCase()} →
              </Link>
            </div>
            <div className="grid">
              {related.map((p) => (
                <ProductCard key={p.product_id} product={p} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
