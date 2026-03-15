'use client'

import Script from 'next/script'
import { usePathname } from 'next/navigation'
import { useEffect } from 'react'

export default function GoatCounter() {
  const pathname = usePathname()

  useEffect(() => {
    if (typeof window !== 'undefined' && window.goatcounter?.count) {
      window.goatcounter.count({
        path: pathname,
      })
    }
  }, [pathname])

  return (
    <Script
      data-goatcounter="https://mahousing.goatcounter.com/count"
      src="//gc.zgo.at/count.js"
      strategy="afterInteractive"
    />
  )
}
