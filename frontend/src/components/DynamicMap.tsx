'use client';

import dynamic from 'next/dynamic';

const DynamicMap = dynamic(() => import('./Map'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-gray-900 animate-pulse rounded-xl flex items-center justify-center border border-gray-800">
      <p className="text-gray-500 font-mono">Loading map...</p>
    </div>
  ),
});

export default DynamicMap;
