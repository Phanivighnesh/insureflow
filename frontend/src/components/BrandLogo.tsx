interface BrandLogoProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizes: Record<NonNullable<BrandLogoProps['size']>, string> = {
  sm: 'h-5 w-5',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
}

/**
 * Canonical InsureFlow brand mark.
 * Uses the official shield SVG from /favicon.svg so both portals share one asset.
 * Keep the img src as an absolute public path so it works in all route depths.
 */
export function BrandLogo({ size = 'md', className = '' }: BrandLogoProps) {
  return (
    <img
      src="/favicon.svg"
      alt="InsureFlow"
      aria-label="InsureFlow"
      className={`${sizes[size]} shrink-0 ${className}`.trim()}
    />
  )
}
