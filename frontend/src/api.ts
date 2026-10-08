// Typed client for the Campus Customs FastAPI backend.

export interface ProductSummary {
  product_id: string
  name: string
  garment_type: string
  category: string
  colors: string[]
  price: number
  image_url: string
  /** Units on hand per size, XS→XXL. Drives the "your size" badges. */
  stock_by_size: Record<string, number>
}

export interface SizeStock {
  size: string
  quantity: number
  in_stock: boolean
}

export interface ProductDetail extends ProductSummary {
  description: string
  search_tags: string[]
  sizes: SizeStock[]
  total_quantity: number
  available_sizes: string[]
}

export interface CategoryCount {
  category: string
  count: number
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return (await res.json()) as T
}

export function fetchProducts(params: { search?: string; category?: string } = {}) {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.category && params.category !== 'All') query.set('category', params.category)
  const suffix = query.toString() ? `?${query}` : ''
  return getJSON<ProductSummary[]>(`/api/products${suffix}`)
}

export function fetchProduct(productId: string) {
  return getJSON<ProductDetail>(`/api/products/${productId}`)
}

export function fetchRelated(productId: string) {
  return getJSON<ProductSummary[]>(`/api/products/${productId}/related`)
}

export function fetchCategories() {
  return getJSON<CategoryCount[]>('/api/categories')
}

export const money = (value: number) =>
  value.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 })
