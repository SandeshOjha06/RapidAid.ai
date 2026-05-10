'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import DynamicMap from '@/components/DynamicMap';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/lib/api';
import { AlertCircle, Phone, Navigation, Clock, Activity } from 'lucide-react';

export default function PatientPortal() {
  const [gps, setGps] = useState<[number, number]>([27.7172, 85.3240]); // Default Kathmandu
  const [emergencyId, setEmergencyId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('IDLE');
  const [ambulanceMarker, setAmbulanceMarker] = useState<[number, number] | null>(null);
  const [eta, setEta] = useState<number | null>(null);
  const [hospitalInfo, setHospitalInfo] = useState<any>(null);
  
  // Modals/Forms
  const [showSosForm, setShowSosForm] = useState(false);
  const [description, setDescription] = useState('');
  const [emergencyType, setEmergencyType] = useState('CRITICAL_SOS');

  // WebSocket hook
  const { lastMessage } = useWebSocket(emergencyId ? `/ws/patient/${emergencyId}` : null);

  useEffect(() => {
    // Attempt to get actual GPS
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition((pos) => {
        setGps([pos.coords.latitude, pos.coords.longitude]);
      }, (err) => console.log('GPS error, using default', err));
    }
  }, []);

  useEffect(() => {
    if (lastMessage) {
      console.log("WS Event:", lastMessage);
      if (lastMessage.event === 'VEHICLE_LOCATION') {
        setAmbulanceMarker([lastMessage.vehicle_lat, lastMessage.vehicle_lng]);
        if (lastMessage.eta_minutes) setEta(lastMessage.eta_minutes);
      } else if (lastMessage.event === 'STATUS_UPDATE') {
        setStatus(lastMessage.status);
      }
    }
  }, [lastMessage]);

  const handleSosTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    setShowSosForm(false);
    setStatus('PENDING');

    try {
      const res = await api.post('/emergency/sos', {
        patient_lat: gps[0],
        patient_lng: gps[1],
        description: description || undefined,
        emergency_type: emergencyType
      });

      const data = res.data;
      setEmergencyId(data.id);
      setStatus(data.status); // DISPATCHED
      setEta(data.estimated_eta_mins);
      
      if (data.hospital_name) {
        setHospitalInfo({
          name: data.hospital_name,
          address: data.hospital_address,
          phone: data.hospital_phone
        });
      }
      
    } catch (err) {
      console.error(err);
      setStatus('ERROR');
      alert("Failed to request emergency service.");
    }
  };

  const markers = [
    { id: 'patient', position: gps, title: 'You', color: 'blue' as any }
  ];
  if (ambulanceMarker) {
    markers.push({ id: 'ambulance', position: ambulanceMarker, title: 'Ambulance', color: 'amber' as any });
  }

  return (
    <div className="relative w-full h-screen bg-black text-white overflow-hidden">
      {/* Map Background */}
      <div className="absolute inset-0 z-0">
        <DynamicMap center={gps} zoom={15} markers={markers} onMapClick={(lat, lng) => status === 'IDLE' && setGps([lat, lng])} />
      </div>

      {/* Header Overlay */}
      <div className="absolute top-0 left-0 w-full p-4 z-20 bg-gradient-to-b from-black/80 to-transparent">
        <div className="flex items-center gap-2">
          <Activity className="text-red-500" />
          <h1 className="font-bold text-xl">Patient Portal</h1>
        </div>
      </div>

      {/* Main SOS Button (IDLE State) */}
      <AnimatePresence>
        {status === 'IDLE' && !showSosForm && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.5 }}
            className="absolute bottom-10 left-0 w-full flex justify-center z-20"
          >
            <button
              onClick={() => setShowSosForm(true)}
              className="relative group flex items-center justify-center w-32 h-32 bg-red-600 rounded-full shadow-[0_0_50px_rgba(220,38,38,0.6)] hover:bg-red-500 hover:shadow-[0_0_80px_rgba(220,38,38,0.8)] transition-all"
            >
              <div className="absolute inset-0 rounded-full animate-ping bg-red-500 opacity-20"></div>
              <span className="text-3xl font-bold tracking-widest text-white relative z-10">SOS</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* SOS Form Modal */}
      <AnimatePresence>
        {showSosForm && (
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            className="absolute bottom-0 left-0 w-full bg-gray-900 border-t border-gray-800 rounded-t-3xl p-6 z-30"
          >
            <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
              <AlertCircle className="text-red-500" /> Request Dispatch
            </h2>
            <form onSubmit={handleSosTrigger} className="flex flex-col gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Emergency Type</label>
                <select 
                  value={emergencyType} 
                  onChange={(e) => setEmergencyType(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded p-3 text-white"
                >
                  <option value="CRITICAL_SOS">Critical Emergency</option>
                  <option value="MEDICAL_RIDE">Non-Emergency Medical Ride</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm text-gray-400 mb-1">Details (Optional)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="E.g. heart attack, pregnant, etc."
                  className="w-full bg-gray-800 border border-gray-700 rounded p-3 text-white h-24"
                ></textarea>
              </div>

              <div className="flex gap-4 mt-2">
                <button type="button" onClick={() => setShowSosForm(false)} className="flex-1 py-3 bg-gray-800 rounded font-semibold text-gray-300">
                  Cancel
                </button>
                <button type="submit" className="flex-1 py-3 bg-red-600 rounded font-bold hover:bg-red-500">
                  CONFIRM SOS
                </button>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Active Tracking Status */}
      <AnimatePresence>
        {status !== 'IDLE' && status !== 'ERROR' && (
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            className="absolute bottom-0 left-0 w-full bg-gray-900/95 backdrop-blur-md border-t border-gray-800 rounded-t-3xl p-6 z-30 flex flex-col gap-4 shadow-[0_-20px_50px_rgba(0,0,0,0.5)]"
          >
            <div className="flex justify-between items-center pb-4 border-b border-gray-800">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Navigation className="text-amber-500" size={20} />
                  Status: {status}
                </h3>
                {eta && (
                  <p className="text-2xl font-bold text-amber-500 mt-1 flex items-center gap-2">
                    <Clock size={24} /> Arriving in {eta} min
                  </p>
                )}
              </div>
            </div>

            {hospitalInfo && (
              <div className="pt-2">
                <p className="text-sm text-gray-400 uppercase tracking-wider mb-2">Destination Hospital</p>
                <div className="bg-gray-800 rounded p-4 border border-gray-700">
                  <h4 className="font-bold text-lg text-white mb-1">{hospitalInfo.name}</h4>
                  <p className="text-sm text-gray-400 mb-2">{hospitalInfo.address}</p>
                  <a href={`tel:${hospitalInfo.phone}`} className="inline-flex items-center gap-2 text-blue-400 text-sm font-semibold">
                    <Phone size={16} /> {hospitalInfo.phone}
                  </a>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
