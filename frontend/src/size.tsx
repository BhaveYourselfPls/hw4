import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { ProductSummary } from './api'

/**
 * "Your size" — the one preference that changes everything on this store.
 *
 * Stock in this catalogue exists only per size, and roughly a quarter of all
 * size rows are at zero. So a shopper browsing without a size is reading a
 * catalogue where a lot of what they see is not actually buyable *for them*.
 * Saving a size once turns every card from "this exists" into "this fits you,
 * and there are two left."
 *
 * Kept in localStorage rather than the database so it works for guests too, and
 * survives a return visit without an account.
 */

export const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL'] as const
export type Size = (typeof SIZES)[number]

const KEY = 'cc_size'

interface SizeContextValue {
  size: Size | null
  setSize: (size: Size | null) => void
  /** True once the shopper has been offered the choice, so we stop nudging. */
  asked: boolean
  dismiss: () => void
}

const SizeContext = createContext<SizeContextValue | null>(null)

export function SizeProvider({ children }: { children: ReactNode }) {
  const [size, setSizeState] = useState<Size | null>(null)
  const [asked, setAsked] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem(KEY)
    if (stored && (SIZES as readonly string[]).includes(stored)) {
      setSizeState(stored as Size)
      setAsked(true)
    } else {
      setAsked(localStorage.getItem(`${KEY}_asked`) === '1')
    }
  }, [])

  const value = useMemo<SizeContextValue>(
    () => ({
      size,
      asked,
      setSize(next) {
        setSizeState(next)
        setAsked(true)
        localStorage.setItem(`${KEY}_asked`, '1')
        if (next) localStorage.setItem(KEY, next)
        else localStorage.removeItem(KEY)
      },
      dismiss() {
        setAsked(true)
        localStorage.setItem(`${KEY}_asked`, '1')
      },
    }),
    [size, asked],
  )

  return <SizeContext.Provider value={value}>{children}</SizeContext.Provider>
}

export function useSize() {
  const context = useContext(SizeContext)
  if (!context) throw new Error('useSize must be used inside <SizeProvider>')
  return context
}

export type FitState = 'none' | 'in-stock' | 'low' | 'sold-out'

export interface Fit {
  state: FitState
  label: string
  quantity: number
}

/** How a product stands relative to the shopper's saved size. */
export function fitFor(product: ProductSummary, size: Size | null): Fit {
  if (!size || !product.stock_by_size || !(size in product.stock_by_size)) {
    return { state: 'none', label: '', quantity: 0 }
  }
  const quantity = product.stock_by_size[size]
  if (quantity === 0) return { state: 'sold-out', label: `Sold out in ${size}`, quantity }
  if (quantity <= 5) return { state: 'low', label: `Only ${quantity} left in ${size}`, quantity }
  return { state: 'in-stock', label: `In stock in ${size}`, quantity }
}
