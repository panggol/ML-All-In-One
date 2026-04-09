import { clsx } from 'clsx'
import type { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  hover?: boolean
}

export default function Card({ children, hover = true, className, ...props }: CardProps) {
  return (
    <div
      className={clsx(
        'bg-white rounded-xl shadow-card p-6 transition-all duration-200',
        hover && 'hover:shadow-soft',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
