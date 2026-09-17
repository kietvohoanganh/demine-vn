export type LookupGrid = {
  model_sha256?: string;
  schema: string[];
  class_labels: string[];
  rows: number[][];
  cell_ids?: string[];
};

export type LookupResult = {
  cellId: string; lon: number; lat: number; priority: number; level: string;
  airstrike: number; crater: number; records: number; craters: number;
  craters300: number; distance: number;
};

export function parseCoordinates(latText: string, lonText: string) {
  const lat = Number(latText), lon = Number(lonText);
  if (!latText.trim() || !lonText.trim() || !Number.isFinite(lat) || !Number.isFinite(lon)) {
    throw new Error("Vui lòng nhập đầy đủ vĩ độ và kinh độ hợp lệ.");
  }
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    throw new Error("Vĩ độ phải từ −90 đến 90; kinh độ từ −180 đến 180.");
  }
  return { lat, lon };
}

function haversineKm(lat: number, lon: number, otherLat: number, otherLon: number) {
  const rad = (x: number) => x * Math.PI / 180;
  const q = Math.sin(rad(otherLat - lat) / 2) ** 2
    + Math.cos(rad(lat)) * Math.cos(rad(otherLat)) * Math.sin(rad(otherLon - lon) / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(Math.max(0, Math.min(1, q))));
}

export function findNearestCell(data: LookupGrid, lat: number, lon: number, cellSizeM = 100): LookupResult {
  const required = ["lon", "lat", "priority", "class", "airstrike_score", "crater_score", "airstrike_records", "craters", "craters_300m"];
  if (!Array.isArray(data.rows) || !data.rows.length || required.some((key, i) => data.schema?.[i] !== key)) {
    throw new Error("Dữ liệu tra cứu không hợp lệ hoặc chưa có ô phân tích.");
  }
  let bestIndex = -1, distance = Infinity;
  data.rows.forEach((row, i) => {
    if (row.length < required.length || !row.slice(0, required.length).every(Number.isFinite)) return;
    const d = haversineKm(lat, lon, row[1], row[0]);
    if (d < distance) { distance = d; bestIndex = i; }
  });
  if (bestIndex < 0) throw new Error("Dữ liệu tra cứu không có tọa độ hợp lệ.");
  // Half a cell diagonal, with 2 m tolerance for coordinate rounding/projection.
  if (distance * 1000 > cellSizeM / Math.sqrt(2) + 2) {
    throw new Error("Tọa độ nằm ngoài vùng phân tích. Vui lòng chọn vị trí trong vùng nghiên cứu tại Quảng Trị.");
  }
  const r = data.rows[bestIndex];
  const legacyId = data.schema[9] === "e" && data.schema[10] === "n"
    && Number.isInteger(r[9]) && Number.isInteger(r[10]) ? `U48N_100_E${r[9]}_N${r[10]}` : null;
  const cellId = data.cell_ids?.[bestIndex] ?? legacyId;
  const level = data.class_labels[r[3]];
  if (!cellId || !level) throw new Error("Dữ liệu tra cứu thiếu mã ô hoặc mức ưu tiên.");
  return { cellId, lon: r[0], lat: r[1], priority: r[2], level,
    airstrike: r[4], crater: r[5], records: r[6], craters: r[7], craters300: r[8], distance };
}
