import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Link from 'next/link'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'AlgoLens',
  description: 'A visual reasoning engine for Python',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <nav className="fixed top-0 w-full glass rounded-none z-50 px-6 py-4 flex justify-between items-center border-t-0 border-l-0 border-r-0 border-b-white/10">
          <Link href="/" className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400 tracking-tight">
            AlgoLens
          </Link>
          <div className="flex gap-6 text-sm font-medium">
            <Link href="/learn" className="text-slate-300 hover:text-white transition-colors">Learn Mode</Link>
            <Link href="/studio" className="text-slate-300 hover:text-white transition-colors">Visualization Studio</Link>
          </div>
        </nav>
        <main className="pt-20 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  )
}
