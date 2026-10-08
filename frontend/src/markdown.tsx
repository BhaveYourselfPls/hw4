import type { ReactNode } from 'react'

/**
 * Inline **bold**, the only markup the assistant is asked to produce in a
 * short label. Shared by the chat bubbles, the chat card notes and the match
 * notes on the Products page, so none of them ever show raw asterisks.
 */
export function renderInline(text: string): ReactNode[] {
  return text
    .split(/\*\*(.+?)\*\*/g)
    .map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part))
}
