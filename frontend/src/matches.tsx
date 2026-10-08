import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { ProductSummary } from './api'

/**
 * The products the agent matched on its most recent reply.
 *
 * Lifted out of the chat panel so the page itself can react: ask "what hoodies
 * do you have?" and the Products grid updates underneath the conversation.
 * Matches carry the full ProductSummary shape, so they render through the same
 * ProductCard component as the rest of the site.
 */

export interface MatchedProduct extends ProductSummary {
  note: string
}

interface MatchesContextValue {
  matches: MatchedProduct[]
  /** The shopper's message that produced these matches. */
  query: string
  setMatches: (matches: MatchedProduct[], query: string) => void
  clear: () => void
}

const MatchesContext = createContext<MatchesContextValue | null>(null)

export function MatchesProvider({ children }: { children: ReactNode }) {
  const [matches, setMatchList] = useState<MatchedProduct[]>([])
  const [query, setQuery] = useState('')

  const value = useMemo<MatchesContextValue>(
    () => ({
      matches,
      query,
      setMatches(next, nextQuery) {
        // Only replace the displayed set when the agent actually matched
        // something — a follow-up like "thanks" should not blank the grid.
        if (next.length === 0) return
        setMatchList(next)
        setQuery(nextQuery)
      },
      clear() {
        setMatchList([])
        setQuery('')
      },
    }),
    [matches, query],
  )

  return <MatchesContext.Provider value={value}>{children}</MatchesContext.Provider>
}

export function useMatches() {
  const context = useContext(MatchesContext)
  if (!context) throw new Error('useMatches must be used inside <MatchesProvider>')
  return context
}
