import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'AlgoLens',
  description: 'A visual reasoning engine for Python',
}

import { SettingsProvider } from '@/contexts/SettingsContext'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} custom-scrollbar`}>
        <SettingsProvider>
          {children}
        </SettingsProvider>
      </body>
    </html>
  )
}
