'use client';

import { useState, useEffect } from 'react';
import DynamicMap from '@/components/DynamicMap';
import { api } from '@/lib/api';
import { Activity, LayoutDashboard, Ambulance, Hospital as HospitalIcon, Clock, HeartPulse } from 'lucide-react';

export default function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [hospitals, setHospitals] = useState<any[]>([]);

  // Fetch data periodically
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, vehiclesRes, hospitalsRes] = await Promise.all([
          api.get('/dashboard/stats'),
          api.get('/vehicles/'),
          api.get('/hospitals/')
        ]);
        
        setStats(statsRes.data);
        setVehicles(vehiclesRes.data);
        setHospitals(hospitalsRes.data);
      } catch (err) {
        console.error("Failed to fetch dashboard data", err);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Polling every 5s for demo
    return () => clearInterval(interval);
  }, []);

  const mapMarkers = [
    // Vehicle markers
    ...vehicles.filter(v => v.current_lat && v.current_lng).map(v => ({
      id: `vehicle-${v.id}`,
      position: [v.current_lat, v.current_lng] as [number, number],
      title: v.registration,
      description: `Status: ${v.is_available ? 'Available' : 'Dispatched'}\nDriver: ${v.driver_name}`,
      color: v.is_available ? 'green' : 'red' as any
    })),
    // Hospital markers
    ...hospitals.map(h => ({
      id: `hospital-${h.id}`,
      position: [h.lat, h.lng] as [number, number],
      title: h.name,
      description: `ICU: ${h.icu_status} | ER: ${h.er_status}`,
      color: 'blue' as any
    }))
  ];

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <header className="flex items-center gap-3 mb-8 pb-4 border-b border-gray-800">
        <LayoutDashboard className="text-emerald-500" size={32} />
        <h1 className="text-3xl font-bold">Command Center</h1>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 flex items-center gap-4">
          <div className="p-4 rounded-full bg-red-500/20 text-red-500">
            <Activity size={24} />
          </div>
          <div>
            <p className="text-gray-400 text-sm">Active Emergencies</p>
            <p className="text-3xl font-bold">{stats?.active_emergencies ?? '-'}</p>
          </div>
        </div>
        
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 flex items-center gap-4">
          <div className="p-4 rounded-full bg-emerald-500/20 text-emerald-500">
            <Ambulance size={24} />
          </div>
          <div>
            <p className="text-gray-400 text-sm">Available Vehicles</p>
            <p className="text-3xl font-bold">{stats?.available_vehicles ?? '-'}</p>
          </div>
        </div>
        
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 flex items-center gap-4">
          <div className="p-4 rounded-full bg-blue-500/20 text-blue-500">
            <Clock size={24} />
          </div>
          <div>
            <p className="text-gray-400 text-sm">Avg Response Time</p>
            <p className="text-3xl font-bold">{stats?.avg_response_time_mins ? `${stats.avg_response_time_mins.toFixed(1)}m` : '-'}</p>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 flex items-center gap-4">
          <div className="p-4 rounded-full bg-amber-500/20 text-amber-500">
            <HospitalIcon size={24} />
          </div>
          <div>
            <p className="text-gray-400 text-sm">Hospitals at Capacity</p>
            <p className="text-3xl font-bold">{stats?.hospitals_at_capacity ?? '-'}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Map */}
        <div className="lg:col-span-2 h-[600px] bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden">
          <DynamicMap center={[27.7172, 85.3240]} zoom={13} markers={mapMarkers} />
        </div>

        {/* Hospital Status Sidebar */}
        <div className="flex flex-col gap-4 overflow-y-auto h-[600px] pr-2">
          <h2 className="text-xl font-bold flex items-center gap-2 mb-2">
            <HeartPulse className="text-red-500" /> Hospital Network
          </h2>
          
          {hospitals.map(h => (
            <div key={h.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h3 className="font-bold text-lg mb-3 leading-tight">{h.name}</h3>
              <div className="flex justify-between text-sm">
                <div className="flex flex-col">
                  <span className="text-gray-400">ICU</span>
                  <span className={`font-bold ${h.icu_status === 'OPEN' ? 'text-emerald-500' : 'text-red-500'}`}>
                    {h.icu_status}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-gray-400">ER</span>
                  <span className={`font-bold ${h.er_status === 'OPEN' ? 'text-emerald-500' : 'text-red-500'}`}>
                    {h.er_status}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
