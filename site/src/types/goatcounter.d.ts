export {}

declare global {
  interface Window {
    goatcounter?: {
      count: (opts: { path: string }) => void
    }
  }
}
