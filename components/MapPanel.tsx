"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PriorityRow } from "./types";

const COLORS = ["#e8edf1", "#c7d7df", "#8fb6c5", "#e7aa57", "#c85b4f"];
const AOI: [[number, number], [number, number]] = [[16.720, 106.850], [16.881878, 107.056585]];

function hexToRgb(hex: string) {
  const n = hex.replace("#", "");
  return { r: parseInt(n.slice(0, 2), 16), g: parseInt(n.slice(2, 4), 16), b: parseInt(n.slice(4, 6), 16) };
}
function rgbToHex(r: number, g: number, b: number) {
  return `#${[r, g, b].map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("")}`;
}
function colorFor(value: number, min: number, max: number) {
  const t = max > min ? Math.max(0, Math.min(1, (value - min) / (max - min))) : 1;
  const p = t * (COLORS.length - 1);
  const l = Math.floor(p);
  const r = Math.min(COLORS.length - 1, l + 1);
  const q = p - l;
  const a = hexToRgb(COLORS[l]);
  const b = hexToRgb(COLORS[r]);
  return rgbToHex(a.r + (b.r - a.r) * q, a.g + (b.g - a.g) * q, a.b + (b.b - a.b) * q);
}
function fmt(v: number | null | undefined, d = 0) {
  return Number.isFinite(v as number) ? Number(v).toLocaleString("vi-VN", { maximumFractionDigits: d }) : "—";
}
function evidenceLevel(value: number) {
  if (value >= 0.8) return "Rất cao";
  if (value >= 0.6) return "Cao";
  if (value >= 0.4) return "Trung bình";
  if (value >= 0.2) return "Thấp";
  return "Rất thấp";
}
function evidenceClass(value: number) {
  if (value >= 0.8) return "very-high";
  if (value >= 0.6) return "high";
  if (value >= 0.4) return "medium";
  return "low";
}

/**
 * Always-on local fallback. It is intentionally schematic: no fake roads,
 * settlements or administrative boundaries are invented. It provides an AOI,
 * coordinate grid and context so the xếp hạng bằng trí tuệ nhân tạo still works fully offline.
 */
function addOfflineReference(L: typeof import("leaflet"), map: import("leaflet").Map) {
  const bounds = L.latLngBounds(AOI);
  if (!map.getPane("offlinePane")) {
    const pane = map.createPane("offlinePane");
    pane.style.zIndex = "150";
    pane.style.pointerEvents = "none";
  }
  if (!map.getPane("offlineLabelPane")) {
    const pane = map.createPane("offlineLabelPane");
    pane.style.zIndex = "151";
    pane.style.pointerEvents = "none";
  }
  const fallback = L.layerGroup();

  L.rectangle(bounds, {
    pane: "offlinePane",
    color: "#91a7b5",
    weight: 1,
    fillColor: "#edf2f4",
    fillOpacity: 1,
    interactive: false,
  }).addTo(fallback);

  const south = AOI[0][0];
  const west = AOI[0][1];
  const north = AOI[1][0];
  const east = AOI[1][1];
  const latStep = (north - south) / 5;
  const lonStep = (east - west) / 6;

  for (let i = 1; i < 5; i++) {
    const lat = south + latStep * i;
    L.polyline([[lat, west], [lat, east]], {
      pane: "offlinePane", color: "#c8d4db", weight: 1, opacity: .7, dashArray: "4 6", interactive: false,
    }).addTo(fallback);
  }
  for (let i = 1; i < 6; i++) {
    const lon = west + lonStep * i;
    L.polyline([[south, lon], [north, lon]], {
      pane: "offlinePane", color: "#c8d4db", weight: 1, opacity: .7, dashArray: "4 6", interactive: false,
    }).addTo(fallback);
  }

  L.marker(bounds.getNorthWest(), {
    pane: "offlineLabelPane",
    interactive: false,
    icon: L.divIcon({
      className: "offline-map-label",
      html: "<span>Vùng nghiên cứu · Quảng Trị</span>",
      iconAnchor: [-8, -8],
    }),
  }).addTo(fallback);

  fallback.addTo(map);
  return fallback;
}

export default function MapPanel({ rows }: { rows: PriorityRow[] }) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstance = useRef<import("leaflet").Map | null>(null);
  const layerGroup = useRef<import("leaflet").LayerGroup | null>(null);
  const tileLayerRef = useRef<import("leaflet").TileLayer | null>(null);
  const [count, setCount] = useState(Math.min(300, rows.length));
  const [selected, setSelected] = useState<PriorityRow | null>(rows[0] ?? null);
  const [mapStatus, setMapStatus] = useState<"loading" | "online" | "offline">("loading");
  const [retryKey, setRetryKey] = useState(0);
  const [mapReady, setMapReady] = useState(false);

  const sorted = useMemo(() => [...rows].sort((a, b) => a.rank - b.rank), [rows]);
  const visible = useMemo(() => sorted.slice(0, Math.max(1, Math.min(count, sorted.length))), [sorted, count]);
  const scoreRange = useMemo(() => {
    const values = visible.map((r) => r.priority_score).filter(Number.isFinite);
    return { min: values.length ? Math.min(...values) : 0, max: values.length ? Math.max(...values) : 1 };
  }, [visible]);

  useEffect(() => {
    setSelected(rows[0] ?? null);
    setCount(Math.min(300, rows.length));
  }, [rows]);

  useEffect(() => {
    let cancelled = false;
    let ro: ResizeObserver | null = null;
    let providerTimer: ReturnType<typeof setTimeout> | null = null;
    let activeTiles: import("leaflet").TileLayer | null = null;

    async function init() {
      const L = await import("leaflet");
      if (cancelled || !mapRef.current || mapInstance.current || !rows.length) return;

      const bounds = L.latLngBounds(AOI);
      const map = L.map(mapRef.current, {
        zoomControl: true,
        attributionControl: true,
        preferCanvas: true,
        maxBounds: bounds.pad(.18),
        maxBoundsViscosity: .92,
        minZoom: 10,
        maxZoom: 18,
      });

      // Always keep a truthful local reference layer below the online basemap.
      addOfflineReference(L, map);

      // Try more than one real basemap provider. This avoids the demo failing
      // just because one tile domain is blocked or slow on a given network.
      const providers = [
        {
          name: "OpenStreetMap",
          url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
          options: { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' },
        },
        {
          name: "Esri",
          url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
          options: { maxZoom: 19, attribution: 'Tiles &copy; Esri; data &copy; OpenStreetMap contributors' },
        },
        {
          name: "Carto",
          url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
          options: { maxZoom: 20, subdomains: "abcd", attribution: '&copy; OpenStreetMap contributors &copy; CARTO' },
        },
      ];

      const tryProvider = (index: number) => {
        if (cancelled) return;
        if (providerTimer) clearTimeout(providerTimer);
        if (activeTiles && map.hasLayer(activeTiles)) map.removeLayer(activeTiles);

        if (index >= providers.length) {
          tileLayerRef.current = null;
          setMapStatus("offline");
          return;
        }

        setMapStatus("loading");
        const provider = providers[index];
        let loaded = 0;
        let errors = 0;
        let settled = false;

        // Deliberately do not set crossOrigin here. The map never reads tile
        // pixels into a canvas, and omitting it avoids unnecessary CORS failures.
        const layer = L.tileLayer(provider.url, provider.options);
        activeTiles = layer;
        tileLayerRef.current = layer;

        const succeed = () => {
          if (settled || cancelled) return;
          settled = true;
          if (providerTimer) clearTimeout(providerTimer);
          setMapStatus("online");
        };

        const fail = () => {
          if (settled || cancelled) return;
          settled = true;
          if (providerTimer) clearTimeout(providerTimer);
          if (map.hasLayer(layer)) map.removeLayer(layer);
          tryProvider(index + 1);
        };

        layer.on("tileload", () => {
          loaded += 1;
          // One successfully decoded tile is enough to prove the provider works.
          if (loaded >= 1) succeed();
        });
        layer.on("tileerror", () => {
          errors += 1;
          if (loaded === 0 && errors >= 4) fail();
        });

        layer.addTo(map);
        // Give each provider enough time on slower Wi-Fi before trying the next.
        providerTimer = setTimeout(() => {
          if (loaded === 0) fail();
          else succeed();
        }, 8000);
      };

      tryProvider(0);
      map.fitBounds(bounds, { padding: [12, 12] });
      layerGroup.current = L.layerGroup().addTo(map);
      mapInstance.current = map;
      setMapReady(true);

      ro = new ResizeObserver(() => requestAnimationFrame(() => map.invalidateSize(false)));
      ro.observe(mapRef.current);
      requestAnimationFrame(() => map.invalidateSize(false));
    }

    void init();
    return () => {
      cancelled = true;
      if (providerTimer) clearTimeout(providerTimer);
      ro?.disconnect();
      tileLayerRef.current = null;
      setMapReady(false);
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
        layerGroup.current = null;
      }
    };
  }, [rows, retryKey]);

  useEffect(() => {
    async function render() {
      const L = await import("leaflet");
      const group = layerGroup.current;
      if (!group) return;
      group.clearLayers();
      visible.forEach((r) => {
        const marker = L.circleMarker([r.latitude, r.longitude], {
          radius: r.rank <= 20 ? 7 : 5.5,
          color: "#ffffff",
          weight: 1.5,
          fillColor: colorFor(r.priority_score, scoreRange.min, scoreRange.max),
          fillOpacity: .96,
        });
        marker.bindTooltip(`<b>Ưu tiên #${r.rank}</b><br/>${r.priority_level}`, { direction: "top", opacity: .96, sticky: true });
        marker.on("click", () => {
          setSelected(r);
          mapInstance.current?.flyTo([r.latitude, r.longitude], Math.max(mapInstance.current.getZoom(), 13), { duration: .35 });
        });
        marker.addTo(group);
      });
    }
    void render();
  }, [visible, scoreRange, mapReady]);

  function resetView() {
    const map = mapInstance.current;
    if (!map) return;
    import("leaflet").then((L) => map.fitBounds(L.latLngBounds(AOI), { padding: [12, 12] }));
  }

  function retryOnlineMap() {
    if (mapInstance.current) {
      mapInstance.current.remove();
      mapInstance.current = null;
      layerGroup.current = null;
      tileLayerRef.current = null;
    }
    setMapReady(false);
    setMapStatus("loading");
    setRetryKey((v) => v + 1);
  }

  if (!rows.length) return <div className="empty-state">Chưa có dữ liệu xếp hạng ưu tiên để hiển thị.</div>;

  return (
    <div className="map-shell">
      <div className="map-toolbar">
        <div className="display-control">
          <span>Hiển thị trên bản đồ</span>
          <div>{[100, 300, 500].map((n) => <button key={n} className={Math.min(count, rows.length) === Math.min(n, rows.length) ? "active" : ""} onClick={() => setCount(Math.min(n, rows.length))}>Nhóm đầu {Math.min(n, rows.length)}</button>)}</div>
        </div>
        <div className="map-toolbar-right">
          <button className="map-utility" type="button" onClick={resetView}>Toàn vùng</button>
          <span className={`map-source-status ${mapStatus}`}>
            <i />
            {mapStatus === "online" ? "Nền bản đồ trực tuyến" : mapStatus === "offline" ? "Nền ngoại tuyến" : "Đang tải nền"}
          </span>
          <div className="legend"><span>Ưu tiên thấp</span><i /><span>cao</span></div>
        </div>
      </div>

      {mapStatus === "offline" && (
        <div className="map-alert offline-alert">
          <div><b>Đang dùng chế độ ngoại tuyến.</b><span>Nền bản đồ trực tuyến không khả dụng, nhưng vị trí và thứ hạng vẫn hiển thị đầy đủ trên lưới tọa độ.</span></div>
          <button type="button" onClick={retryOnlineMap}>Thử tải lại nền</button>
        </div>
      )}

      <div className="map-layout">
        <div className="map-frame"><div ref={mapRef} className="map-canvas" /></div>
        <aside className="location-card">
          {selected ? (
            <>
              <div className="location-header">
                <div><span>KHU VỰC ĐANG CHỌN</span><h3>Ưu tiên #{selected.rank}</h3></div>
                <b className="priority-badge">{selected.priority_level}</b>
              </div>

              <div className="priority-summary">
                <span>Ý nghĩa</span>
                <p>Mô hình đưa khu vực này vào <strong>nhóm cần được xem xét sớm</strong> so với các ô còn lại trong vùng nghiên cứu.</p>
              </div>

              <div className="reason-title">Vì sao khu vực này được xếp hạng cao?</div>
              <div className="reason-list">
                <div><span className={`signal-dot ${evidenceClass(selected.airstrike_evidence_score)}`} /><div><b>Không kích lịch sử</b><small>THOR</small></div><strong>{evidenceLevel(selected.airstrike_evidence_score)}</strong></div>
                <div><span className={`signal-dot ${evidenceClass(selected.crater_evidence_score)}`} /><div><b>Dấu vết hố bom</b><small>KH-9</small></div><strong>{evidenceLevel(selected.crater_evidence_score)}</strong></div>
                {selected.population_count != null && <div><span className="signal-dot context" /><div><b>Bối cảnh dân cư</b><small>WorldPop</small></div><strong>{fmt(selected.population_count)}</strong></div>}
              </div>

              <div className="evidence-details">
                <div><span>Hồ sơ THOR trong ô</span><b>{fmt(selected.airstrike_records)}</b></div>
                <div><span>Hố bom trong 300 m</span><b>{fmt(selected.craters_within_300m)}</b></div>
                <div><span>Hố bom trong ô</span><b>{fmt(selected.craters_in_cell)}</b></div>
              </div>

              <details className="score-details">
                <summary>Xem chỉ số kỹ thuật</summary>
                <div><span>Điểm xếp hạng của mô hình</span><b>{selected.priority_score.toFixed(3)}</b></div>
                <div><span>Điểm THOR chuẩn hóa</span><b>{selected.airstrike_evidence_score.toFixed(3)}</b></div>
                <div><span>Điểm KH-9 chuẩn hóa</span><b>{selected.crater_evidence_score.toFixed(3)}</b></div>
              </details>

              <div className="location-footer">
                <span>{selected.latitude.toFixed(5)}°N · {selected.longitude.toFixed(5)}°E</span>
                <small>Không phải xác suất còn vật nổ.</small>
              </div>
            </>
          ) : <p>Chọn một điểm trên bản đồ để xem chi tiết.</p>}
        </aside>
      </div>
    </div>
  );
}
