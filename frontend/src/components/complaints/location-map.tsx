"use client";

/**
 * Interactive map (Leaflet + OpenStreetMap tiles). Leaflet needs `window`, so never import
 * this file directly; use <LocationMap> from "./location-map-loader" instead.
 */

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";

export interface MapPoint {
  latitude: number;
  longitude: number;
}

export interface LocationMapProps {
  point: MapPoint | null;
  /** Omit to make the map read-only. */
  onPick?: (point: MapPoint) => void;
  className?: string;
}

// A CSS pin instead of Leaflet's default PNG icons, which break under bundlers.
const pinIcon = L.divIcon({
  className: "",
  html: '<span class="cp-map-pin" aria-hidden="true"></span>',
  iconSize: [30, 30],
  iconAnchor: [15, 30],
});

const WORLD_VIEW = { center: [20, 0] as L.LatLngTuple, zoom: 2 };
const PIN_ZOOM = 16;

function FollowPoint({ point }: { point: MapPoint | null }) {
  const map = useMap();
  useEffect(() => {
    if (point) {
      map.setView([point.latitude, point.longitude], Math.max(map.getZoom(), PIN_ZOOM));
    }
  }, [map, point]);
  return null;
}

function ClickToPick({ onPick }: { onPick: (point: MapPoint) => void }) {
  useMapEvents({
    click: (event) => onPick({ latitude: event.latlng.lat, longitude: event.latlng.lng }),
  });
  return null;
}

export default function LocationMap({ point, onPick, className }: LocationMapProps) {
  const editable = Boolean(onPick);
  return (
    <MapContainer
      center={point ? [point.latitude, point.longitude] : WORLD_VIEW.center}
      zoom={point ? PIN_ZOOM : WORLD_VIEW.zoom}
      scrollWheelZoom={false}
      className={className}
      aria-label={editable ? "Map. Click to place the pin." : "Map showing the reported location"}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {point && (
        <Marker
          position={[point.latitude, point.longitude]}
          icon={pinIcon}
          draggable={editable}
          keyboard={editable}
          eventHandlers={
            onPick
              ? {
                  dragend: (event) => {
                    const { lat, lng } = (event.target as L.Marker).getLatLng();
                    onPick({ latitude: lat, longitude: lng });
                  },
                }
              : undefined
          }
        />
      )}
      <FollowPoint point={point} />
      {onPick && <ClickToPick onPick={onPick} />}
    </MapContainer>
  );
}
