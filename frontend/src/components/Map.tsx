'use client';

import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useEffect } from 'react';

// Fix for default marker icons in Next.js
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface MapProps {
  center: [number, number];
  zoom?: number;
  markers?: {
    id: string;
    position: [number, number];
    title: string;
    description?: string;
    color?: 'red' | 'blue' | 'green' | 'amber';
  }[];
  onMapClick?: (lat: number, lng: number) => void;
}

// A helper component to re-center the map when center changes
function Recenter({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

// A helper to capture clicks
function MapEvents({ onMapClick }: { onMapClick?: (lat: number, lng: number) => void }) {
  const map = useMap();
  useEffect(() => {
    if (!onMapClick) return;
    const onClick = (e: L.LeafletMouseEvent) => {
      onMapClick(e.latlng.lat, e.latlng.lng);
    };
    map.on('click', onClick);
    return () => {
      map.off('click', onClick);
    };
  }, [map, onMapClick]);
  return null;
}

export default function Map({ center, zoom = 14, markers = [], onMapClick }: MapProps) {
  // Custom icons based on color
  const getIcon = (color: string) => {
    let filter = '';
    if (color === 'red') filter = 'hue-rotate(150deg)'; // approximate
    if (color === 'green') filter = 'hue-rotate(250deg)';
    if (color === 'amber') filter = 'hue-rotate(190deg)';
    
    return L.divIcon({
      className: 'custom-marker',
      html: `<div style="width:24px;height:24px;background-color:${color};border-radius:50%;border:3px solid white;box-shadow:0 0 10px rgba(0,0,0,0.5);"></div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });
  };

  return (
    <div className="w-full h-full rounded-xl overflow-hidden border border-gray-800 shadow-2xl relative z-10">
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
      >
        <Recenter center={center} zoom={zoom} />
        <MapEvents onMapClick={onMapClick} />
        <TileLayer
          className="dark-map-tiles"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {markers.map((marker) => (
          <Marker
            key={marker.id}
            position={marker.position}
            icon={marker.color ? getIcon(marker.color) : new L.Icon.Default()}
          >
            <Popup>
              <div className="font-semibold">{marker.title}</div>
              {marker.description && <div className="text-sm text-gray-600">{marker.description}</div>}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
