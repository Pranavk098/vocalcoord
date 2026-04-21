// frontend/app/page.tsx
// Server component — sets dynamic rendering to avoid SSR issues with ElevenLabs hooks
export const dynamic = 'force-dynamic'

import { HomeClient } from './HomeClient'

export default function Page() {
  return <HomeClient />
}
