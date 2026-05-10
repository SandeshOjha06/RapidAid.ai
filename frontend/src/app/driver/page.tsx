'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import DynamicMap from '@/components/DynamicMap';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/lib/api';
import { Navigation, Car, AlertTriangle, CheckCircle, MapPin } from 'lucide-react';

export default function DriverPortal() {
  const [vehicleId, setVehicleId] = useState<string>('');
  const [vehicleData, setVehicleData] = useState<any>(null);
  
  const [assignment, setAssignment] = useState<any>(null);
  const [currentStatus, setCurrentStatus] = useState<string>('IDLE');
  const [gps, setGps] = useState<[number, number]>([27.7172, 85.3240]);
  
  const { lastMessage, sendMessage, isConnected } = useWebSocket(vehicleId ? `/ws/driver/${vehicleId}` : null);

  // Fetch TIER_1 vehicle on mount for demo purposes
  useEffect(() => {
    api.get('/vehicles/').then(async res => {
      const vehicles = res.data;
      if (vehicles.length > 0) {
        const vid = vehicles[0].id;
        setVehicleId(vid);
        setVehicleData(vehicles[0]);
        if (vehicles[0].current_lat && vehicles[0].current_lng) {
          setGps([vehicles[0].current_lat, vehicles[0].current_lng]);
        }
        
        // Check if there is an active assignment already (in case they missed the WS event)
        try {
          const assignmentRes = await api.get(`/vehicles/${vid}/assignment`);
          if (assignmentRes.data) {
            setAssignment(assignmentRes.data);
            setCurrentStatus(assignmentRes.data.status);
          }
        } catch (e) {
          console.error("Failed to fetch assignment", e);
        }
      }
    }).catch(console.error);
  }, []);

  // Listen to WS
  useEffect(() => {
    if (lastMessage && lastMessage.event === 'ASSIGNMENT') {
      const alertAudio = new Audio('https://actions.google.com/sounds/v1/alarms/digital_watch_alarm_long.ogg');
      alertAudio.play().catch(() => {});
      
      setAssignment(lastMessage);
      setCurrentStatus('DISPATCHED');
    }
  }, [lastMessage]);

  // Simulate periodic GPS Pings via HTTP
  useEffect(() => {
    if (!isConnected || !vehicleId) return;
    
    const interval = setInterval(() => {
      // Send HTTP Patch because backend WS router ignores GPS updates directly
      api.patch(`/vehicles/${vehicleId}/location`, {
        lat: gps[0],
        lng: gps[1]
      }).catch(err => console.error("GPS Update Failed", err));
    }, 5000);
    
    return () => clearInterval(interval);
  }, [isConnected, vehicleId, gps]);

  const updateEmergencyStatus = async (status: string) => {
    if (!assignment?.emergency_id) return;
    try {
      await api.patch(`/emergency/${assignment.emergency_id}/status?status=${status}`);
      setCurrentStatus(status);
      if (status === 'ARRIVED' || status === 'CLOSED') {
        setAssignment(null);
        setCurrentStatus('IDLE');
      }
    } catch (err) {
      console.error(err);
      alert("Failed to update status");
    }
  };

  const getActionButtons = () => {
    switch (currentStatus) {
      case 'DISPATCHED':
        return (
          <button onClick={() => updateEmergencyStatus('EN_ROUTE')} className="w-full py-4 bg-amber-500 hover:bg-amber-400 text-black font-bold rounded-xl text-lg flex items-center justify-center gap-2">
            <Car /> Start Route
          </button>
        );
      case 'EN_ROUTE':
        return (
          <button onClick={() => updateEmergencyStatus('ON_SCENE')} className="w-full py-4 bg-blue-500 hover:bg-blue-400 text-white font-bold rounded-xl text-lg flex items-center justify-center gap-2">
            <MapPin /> Arrived at Scene
          </button>
        );
      case 'ON_SCENE':
        return (
          <button onClick={() => updateEmergencyStatus('TRANSPORTING')} className="w-full py-4 bg-purple-500 hover:bg-purple-400 text-white font-bold rounded-xl text-lg flex items-center justify-center gap-2">
            <Car /> Transporting Patient
          </button>
        );
      case 'TRANSPORTING':
        return (
          <button onClick={() => updateEmergencyStatus('ARRIVED')} className="w-full py-4 bg-emerald-500 hover:bg-emerald-400 text-white font-bold rounded-xl text-lg flex items-center justify-center gap-2">
            <CheckCircle /> Arrived at Hospital
          </button>
        );
      default:
        return null;
    }
  };

  if (!vehicleData) {
    return <div className="min-h-screen bg-black text-white flex items-center justify-center">Loading Driver Profile...</div>;
  }

  const markers: any[] = [{ id: 'driver', position: gps, title: 'You', color: 'blue' as any }];
  if (assignment) {
    markers.push({
      id: 'patient',
      position: [assignment.patient_lat, assignment.patient_lng],
      title: 'Patient Location',
      description: assignment.patient_address,
      color: 'red' as any
    });
  }

  return (
    <div className="relative w-full h-screen bg-black text-white overflow-hidden flex flex-col">
      
      {/* Header Overlay */}
      <div className="absolute top-0 left-0 w-full p-4 z-20 bg-gradient-to-b from-black/80 to-transparent">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Navigation className="text-amber-500" />
            <h1 className="font-bold text-xl">{vehicleData.registration}</h1>
          </div>
          <div className={`px-3 py-1 rounded-full text-xs font-bold ${isConnected ? 'bg-emerald-500/20 text-emerald-500' : 'bg-red-500/20 text-red-500'}`}>
            {isConnected ? 'ONLINE' : 'OFFLINE'}
          </div>
        </div>
      </div>

      {/* Map Area */}
      <div className="flex-1 relative z-0">
        <DynamicMap center={gps} zoom={15} markers={markers} onMapClick={(lat, lng) => currentStatus === 'IDLE' && setGps([lat, lng])} />
      </div>

      {/* Assignment Modal (Pops up when assigned) */}
      <AnimatePresence>
        {assignment && currentStatus === 'DISPATCHED' && (
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            className="absolute inset-0 z-50 flex items-end bg-black/60 backdrop-blur-sm"
          >
            <div className="bg-gray-900 w-full rounded-t-3xl p-6 border-t border-red-500/50 shadow-[0_-20px_50px_rgba(220,38,38,0.2)]">
              <div className="flex items-center justify-center w-16 h-16 bg-red-500/20 rounded-full mx-auto mb-4 border border-red-500">
                <AlertTriangle className="text-red-500" size={32} />
              </div>
              <h2 className="text-3xl font-black text-center mb-2 uppercase text-white">New Assignment</h2>
              
              <div className="bg-black rounded-xl p-4 my-6 border border-gray-800">
                <p className="text-red-500 font-bold mb-1">Severity: {assignment.severity}</p>
                <p className="text-gray-300">ID: {assignment.short_id}</p>
                <p className="text-gray-300 mt-2 line-clamp-2">Loc: {assignment.patient_address || 'Unknown'}</p>
              </div>

              {getActionButtons()}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Persistent Bottom Bar (when active) */}
      <AnimatePresence>
        {assignment && currentStatus !== 'DISPATCHED' && (
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            className="absolute bottom-0 left-0 w-full z-30 p-4"
          >
            <div className="bg-gray-900/95 backdrop-blur-md rounded-2xl p-4 border border-gray-800 shadow-2xl">
              <div className="flex justify-between items-center mb-4">
                <div>
                  <p className="text-sm text-gray-400">Current Task</p>
                  <p className="font-bold text-amber-500 text-lg">{currentStatus.replace('_', ' ')}</p>
                </div>
                <div className="bg-red-500/20 px-3 py-1 rounded text-red-500 font-bold border border-red-500/20">
                  {assignment.severity}
                </div>
              </div>
              
              {getActionButtons()}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Idle State Banner */}
      <AnimatePresence>
        {!assignment && (
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            className="absolute bottom-0 left-0 w-full z-30 p-4"
          >
            <div className="bg-gray-900 rounded-2xl p-6 text-center border border-gray-800">
              <Car className="mx-auto text-gray-500 mb-2" size={32} />
              <h3 className="font-bold text-xl text-white">Idle & Available</h3>
              <p className="text-gray-400 text-sm mt-1">Waiting for autonomous dispatch...</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
