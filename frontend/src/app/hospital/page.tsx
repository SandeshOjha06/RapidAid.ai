'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/lib/api';
import { AlertTriangle, CheckCircle, Clock, Activity, Settings2 } from 'lucide-react';

export default function HospitalPortal() {
  // Use TUTH as the default hospital id for the demo
  const [hospitalId, setHospitalId] = useState<string>(''); 
  const [hospitalData, setHospitalData] = useState<any>(null);
  
  const [queue, setQueue] = useState<any[]>([]);
  const [flashAlert, setFlashAlert] = useState<any>(null);
  
  const { lastMessage } = useWebSocket(hospitalId ? `/ws/hospital/${hospitalId}` : null);

  // Fetch hospitals on mount to get the TUTH ID
  useEffect(() => {
    api.get('/hospitals/').then(res => {
      const hospitals = res.data;
      const tuth = hospitals.find((h: any) => h.name.includes("Teaching Hospital") || h.name.includes("TUTH"));
      if (tuth) {
        setHospitalId(tuth.id);
        setHospitalData(tuth);
      } else if (hospitals.length > 0) {
        setHospitalId(hospitals[0].id);
        setHospitalData(hospitals[0]);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (lastMessage && lastMessage.event === 'INCOMING_PATIENT') {
      const alertAudio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
      alertAudio.play().catch(() => {}); // Play sound if allowed
      
      setFlashAlert(lastMessage);
      setQueue(prev => [lastMessage, ...prev]);

      // Auto dismiss flash after 10s
      setTimeout(() => {
        setFlashAlert(null);
      }, 10000);
    }
  }, [lastMessage]);

  const toggleStatus = async (field: 'icu_status' | 'er_status') => {
    if (!hospitalData) return;
    const current = hospitalData[field];
    const nextStatus = current === 'OPEN' ? 'FULL' : 'OPEN';
    
    try {
      await api.patch(`/hospitals/${hospitalId}/status`, {
        [field]: nextStatus
      });
      setHospitalData({ ...hospitalData, [field]: nextStatus });
    } catch (err) {
      console.error(err);
      alert("Failed to update status");
    }
  };

  if (!hospitalData) {
    return <div className="min-h-screen bg-black text-white flex items-center justify-center">Loading Hospital Data...</div>;
  }

  return (
    <div className="relative min-h-screen bg-black text-white">
      
      {/* Flashing Alert Overlay */}
      <AnimatePresence>
        {flashAlert && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-red-900/90 backdrop-blur-sm"
          >
            <motion.div 
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ repeat: Infinity, duration: 1 }}
              className="bg-black border-4 border-red-500 rounded-3xl p-10 max-w-2xl w-full text-center"
            >
              <AlertTriangle size={80} className="mx-auto text-red-500 mb-6 animate-pulse" />
              <h1 className="text-5xl font-black text-white mb-4 uppercase">Incoming Patient</h1>
              <div className="bg-gray-900 rounded-xl p-6 text-left mb-8 border border-red-500/30">
                <p className="text-2xl font-bold text-red-400 mb-2">Severity: {flashAlert.severity}</p>
                <p className="text-xl text-gray-300 mb-2">Category: {flashAlert.medical_category}</p>
                <p className="text-xl text-gray-300">ID: {flashAlert.short_id}</p>
                <p className="text-3xl font-black text-amber-500 mt-4 flex items-center gap-3">
                  <Clock size={32} /> ETA: {flashAlert.eta_minutes} mins
                </p>
              </div>
              <button 
                onClick={() => setFlashAlert(null)}
                className="bg-red-600 hover:bg-red-500 text-white font-bold py-4 px-12 rounded-xl text-xl w-full"
              >
                ACKNOWLEDGE
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="max-w-6xl mx-auto p-6 pt-10">
        <header className="flex justify-between items-center mb-10 pb-6 border-b border-gray-800">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <Activity className="text-blue-500" /> {hospitalData.name}
            </h1>
            <p className="text-gray-400 mt-1">Command Center & Capacity Management</p>
          </div>
          <div className="flex items-center gap-2 bg-gray-900 px-4 py-2 rounded-lg border border-gray-800">
            <Settings2 className="text-gray-400" size={20} />
            <span className="font-mono text-sm text-gray-400">ID: {hospitalId.split('-')[0]}...</span>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
          {/* ICU Toggle */}
          <button 
            onClick={() => toggleStatus('icu_status')}
            className={`relative overflow-hidden p-8 rounded-3xl border-2 transition-all text-left ${
              hospitalData.icu_status === 'OPEN' 
                ? 'bg-blue-900/20 border-blue-500/50 hover:bg-blue-900/40' 
                : 'bg-red-900/20 border-red-500/50 hover:bg-red-900/40'
            }`}
          >
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm uppercase tracking-widest text-gray-400 mb-1">ICU Capacity</p>
                <h2 className="text-4xl font-black mb-2">
                  {hospitalData.icu_status === 'OPEN' ? 'ACCEPTING' : 'FULL'}
                </h2>
                <p className="text-gray-400">Click to toggle status instantly.</p>
              </div>
              {hospitalData.icu_status === 'OPEN' ? (
                <CheckCircle size={48} className="text-blue-500" />
              ) : (
                <AlertTriangle size={48} className="text-red-500" />
              )}
            </div>
          </button>

          {/* ER Toggle */}
          <button 
            onClick={() => toggleStatus('er_status')}
            className={`relative overflow-hidden p-8 rounded-3xl border-2 transition-all text-left ${
              hospitalData.er_status === 'OPEN' 
                ? 'bg-emerald-900/20 border-emerald-500/50 hover:bg-emerald-900/40' 
                : 'bg-red-900/20 border-red-500/50 hover:bg-red-900/40'
            }`}
          >
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm uppercase tracking-widest text-gray-400 mb-1">Emergency Room</p>
                <h2 className="text-4xl font-black mb-2">
                  {hospitalData.er_status === 'OPEN' ? 'OPEN' : 'FULL'}
                </h2>
                <p className="text-gray-400">Click to toggle status instantly.</p>
              </div>
              {hospitalData.er_status === 'OPEN' ? (
                <CheckCircle size={48} className="text-emerald-500" />
              ) : (
                <AlertTriangle size={48} className="text-red-500" />
              )}
            </div>
          </button>
        </div>

        <div>
          <h3 className="text-xl font-bold mb-6 flex items-center gap-2 border-b border-gray-800 pb-2 inline-flex">
            <Activity className="text-gray-400" /> Active Incoming Queue
          </h3>
          
          {queue.length === 0 ? (
            <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-12 text-center text-gray-500">
              No active incoming patients at the moment.
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {queue.map((q, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col md:flex-row justify-between items-center gap-4 hover:border-gray-700 transition-colors">
                  <div className="flex items-center gap-6">
                    <div className="bg-red-900/30 text-red-500 font-bold px-4 py-2 rounded-lg border border-red-500/30">
                      {q.severity}
                    </div>
                    <div>
                      <p className="font-bold text-lg">{q.medical_category}</p>
                      <p className="text-gray-400 text-sm">ID: {q.short_id}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-400">Estimated Arrival</p>
                    <p className="font-black text-2xl text-amber-500">{q.eta_minutes} mins</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
