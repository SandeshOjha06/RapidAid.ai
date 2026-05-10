import Link from 'next/link';
import { Activity, Hospital, Navigation, LayoutDashboard } from 'lucide-react';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 sm:p-24 bg-gradient-to-br from-gray-900 to-black">
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm">
        <h1 className="text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-red-500 to-rose-400 mb-4 text-center">
          RapidAid.ai
        </h1>
        <p className="text-xl text-gray-400 text-center mb-16">
          Autonomous Emergency Dispatch Ecosystem
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 w-full max-w-4xl mx-auto">
          {/* Patient Portal */}
          <Link href="/patient" className="group rounded-2xl border border-gray-800 bg-gray-900/50 p-8 transition-all hover:bg-gray-800 hover:border-red-500/50 hover:shadow-[0_0_30px_-5px_rgba(239,68,68,0.3)]">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-500/10 text-red-500 group-hover:bg-red-500 group-hover:text-white transition-colors">
              <Activity size={24} />
            </div>
            <h2 className="mb-3 text-2xl font-semibold text-gray-100">Patient Portal</h2>
            <p className="text-gray-400">
              1-tap SOS, live ambulance tracking, and medical ride booking.
            </p>
          </Link>

          {/* Hospital Portal */}
          <Link href="/hospital" className="group rounded-2xl border border-gray-800 bg-gray-900/50 p-8 transition-all hover:bg-gray-800 hover:border-blue-500/50 hover:shadow-[0_0_30px_-5px_rgba(59,130,246,0.3)]">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/10 text-blue-500 group-hover:bg-blue-500 group-hover:text-white transition-colors">
              <Hospital size={24} />
            </div>
            <h2 className="mb-3 text-2xl font-semibold text-gray-100">Hospital Portal</h2>
            <p className="text-gray-400">
              ICU/ER capacity toggles and flashing incoming patient alerts.
            </p>
          </Link>

          {/* Driver Portal */}
          <Link href="/driver" className="group rounded-2xl border border-gray-800 bg-gray-900/50 p-8 transition-all hover:bg-gray-800 hover:border-amber-500/50 hover:shadow-[0_0_30px_-5px_rgba(245,158,11,0.3)]">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-500 group-hover:bg-amber-500 group-hover:text-white transition-colors">
              <Navigation size={24} />
            </div>
            <h2 className="mb-3 text-2xl font-semibold text-gray-100">Driver Portal</h2>
            <p className="text-gray-400">
              Autonomous assignments, turn-by-turn navigation, and GPS streaming.
            </p>
          </Link>

          {/* Admin Dashboard */}
          <Link href="/admin" className="group rounded-2xl border border-gray-800 bg-gray-900/50 p-8 transition-all hover:bg-gray-800 hover:border-emerald-500/50 hover:shadow-[0_0_30px_-5px_rgba(16,185,129,0.3)]">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500 group-hover:bg-emerald-500 group-hover:text-white transition-colors">
              <LayoutDashboard size={24} />
            </div>
            <h2 className="mb-3 text-2xl font-semibold text-gray-100">Command Center</h2>
            <p className="text-gray-400">
              Live statistics, global fleet map, and agent decision trail.
            </p>
          </Link>
        </div>
      </div>
    </main>
  );
}
