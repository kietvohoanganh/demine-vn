"use client";

import { useEffect, useMemo, useState } from "react";
import MapPanel from "./MapPanel";
import { findNearestCell, parseCoordinates, type LookupGrid, type LookupResult } from "./lookup";
import type { AIResults, PriorityRow, Results } from "./types";

type Props = { results: Results; priority: PriorityRow[] };

function fmt(v: number | undefined | null, d = 0) {
  return Number.isFinite(v as number)
    ? Number(v).toLocaleString("vi-VN", { maximumFractionDigits: d })
    : "—";
}

export default function Dashboard({ results }: Props) {
  const [ai, setAI] = useState<AIResults | null>(null);
  const [rows, setRows] = useState<PriorityRow[]>([]);
  const [aiError, setAIError] = useState("");
  const [tableCount, setTableCount] = useState(20);
  const [lat, setLat] = useState("16.80");
  const [lon, setLon] = useState("106.95");
  const [lookup, setLookup] = useState<LookupResult | null>(null);
  const [lookupBusy, setLookupBusy] = useState(false);
  const [lookupError, setLookupError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function loadAI() {
      try {
        const responses = await Promise.all(
          ["summary.json", "priority.json"].map((file) =>
            fetch(`/data/ai/${file}`, { signal: controller.signal }),
          ),
        );
        if (responses.some((r) => !r.ok)) {
          throw new Error("Chưa có kết quả trí tuệ nhân tạo. Hãy chạy quy trình huấn luyện và đồng bộ dữ liệu web.");
        }

        const [summary, bundle] = (await Promise.all(responses.map((r) => r.json()))) as [
          AIResults,
          { model_sha256: string; rows: PriorityRow[] },
        ];

        if (summary.model_sha256 !== bundle.model_sha256) {
          throw new Error("Các tệp kết quả trí tuệ nhân tạo không cùng phiên bản.");
        }
        if (summary.base_lookup_sha256 !== results.lookup_sha256 || summary.cells !== results.cells) {
          throw new Error("Kết quả trí tuệ nhân tạo chưa khớp với lưới dữ liệu hiện tại.");
        }
        if (!Array.isArray(bundle.rows) || !bundle.rows.length) {
          throw new Error("Danh mục ưu tiên bằng trí tuệ nhân tạo đang trống.");
        }
        if (!bundle.rows.every((r) => r.is_probability === false)) {
          throw new Error("Kết quả không đạt ràng buộc an toàn: chỉ số không được biểu diễn như xác suất còn vật nổ.");
        }

        if (!controller.signal.aborted) {
          setAI(summary);
          setRows([...bundle.rows].sort((a, b) => a.rank - b.rank));
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setAIError(error instanceof Error ? error.message : "Không tải được kết quả trí tuệ nhân tạo.");
        }
      }
    }
    void loadAI();
    return () => controller.abort();
  }, [results.lookup_sha256, results.cells]);

  const topRows = useMemo(() => rows.slice(0, tableCount), [rows, tableCount]);
  const lookupRow = useMemo(() => lookup ? rows.find((r) => r.cell_id === lookup.cellId) ?? null : null, [lookup, rows]);

  async function doLookup() {
    setLookup(null);
    setLookupError("");

    let coordinates: { lat: number; lon: number };
    try {
      coordinates = parseCoordinates(lat, lon);
    } catch (error) {
      setLookupError((error as Error).message);
      return;
    }

    setLookupBusy(true);
    try {
      const res = await fetch("/data/ai/lookup_grid.json");
      if (!res.ok) throw new Error("Không tải được dữ liệu tra cứu trí tuệ nhân tạo.");
      const data: LookupGrid = await res.json();
      if (data.model_sha256 !== ai?.model_sha256) {
        throw new Error("Mô hình vừa được cập nhật. Hãy tải lại trang.");
      }
      setLookup(findNearestCell(data, coordinates.lat, coordinates.lon, results.grid_resolution_m));
    } catch (error) {
      setLookupError(error instanceof Error ? error.message : "Không thể tra cứu vị trí.");
    } finally {
      setLookupBusy(false);
    }
  }

  return (
    <main className="site-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">Ư</span>
          <div>
            <strong>Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn</strong>
            <small>Xếp hạng khu vực ưu tiên bằng trí tuệ nhân tạo</small>
          </div>
        </div>
        <div className="status-chip"><i /> Dữ liệu thực · Quảng Trị</div>
      </header>

      <section className="hero">
        <div className="hero-copy-wrap">
          <p className="eyebrow">HỆ THỐNG HỖ TRỢ XẾP HẠNG ƯU TIÊN</p>
          <h1>Xác định khu vực nào nên được ưu tiên xem xét trước.</h1>
          <p className="hero-copy">
            Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn kết hợp hồ sơ không kích THOR, dấu vết hố bom KH-9 và dữ liệu bối cảnh để
            xếp hạng các ô 100 m phục vụ lập kế hoạch khảo sát và rà phá.
          </p>
        </div>
        <div className="hero-badge">
          <span>Kết quả đầu ra</span>
          <strong>Danh mục ưu tiên</strong>
          <small>không phải xác suất còn vật nổ</small>
        </div>
      </section>

      <div className="safety-note" role="note">
        <span className="safety-icon">!</span>
        <div>
          <b>Hệ thống không xác nhận một vị trí có hoặc không có vật nổ.</b>
          <p>Trí tuệ nhân tạo chỉ hỗ trợ sắp xếp nơi cần được xem xét trước; quyết định thực địa thuộc đơn vị chuyên môn.</p>
        </div>
      </div>

      <section className="stats-row" aria-label="Tóm tắt dữ liệu">
        <div><span>Ô phân tích</span><strong>{fmt(results.cells)}</strong><small>{results.grid_resolution_m} m / ô</small></div>
        <div><span>Hồ sơ THOR</span><strong>{fmt(results.airstrike_records_in_aoi)}</strong><small>trong vùng nghiên cứu</small></div>
        <div><span>Dấu vết KH-9</span><strong>{fmt(results.craters_in_aoi)}</strong><small>dự đoán hố bom</small></div>
        <div><span>Mô hình</span><strong>{ai ? "Sẵn sàng" : "Đang tải"}</strong><small>{ai ? "xếp hạng bằng trí tuệ nhân tạo" : aiError || "kiểm tra dữ liệu"}</small></div>
      </section>

      {aiError && !ai && (
        <section className="error-card">
          <b>Chưa thể hiển thị kết quả xếp hạng</b>
          <p>{aiError}</p>
          <code>python scripts/train_real_ai.py</code>
        </section>
      )}

      {ai && rows.length > 0 && (
        <>
          <section className="workspace-section">
            <div className="section-heading">
              <div>
                <p className="section-kicker">BẢN ĐỒ ƯU TIÊN</p>
                <h2>Khu vực nào nên được xem xét trước?</h2>
                <p>Điểm có thứ hạng càng cao được mô hình đưa lên trước trong danh mục ưu tiên.</p>
              </div>
              <span className="ai-chip">Xếp hạng bằng trí tuệ nhân tạo</span>
            </div>

            <div className="lookup-card">
              <div className="lookup-copy">
                <b>Tra cứu một vị trí</b>
                <span>Nhập tọa độ để tìm ô được xếp hạng gần nhất.</span>
              </div>
              <form noValidate onSubmit={(e) => { e.preventDefault(); void doLookup(); }}>
                <label>Vĩ độ<input type="number" step="any" value={lat} disabled={lookupBusy} onChange={(e) => setLat(e.target.value)} /></label>
                <label>Kinh độ<input type="number" step="any" value={lon} disabled={lookupBusy} onChange={(e) => setLon(e.target.value)} /></label>
                <button type="submit" disabled={lookupBusy}>{lookupBusy ? "Đang tìm…" : "Tra cứu"}</button>
              </form>
              {lookupError && <p className="inline-error" role="alert">{lookupError}</p>}
              {lookup && (
                <div className="lookup-result">
                  <strong>{lookupRow ? `#${lookupRow.rank}` : lookup.level}</strong>
                  <div><b>{lookup.level}</b><span>Ô {lookup.cellId} · cách tọa độ nhập {lookup.distance.toFixed(2)} km</span></div>
                </div>
              )}
            </div>

            <MapPanel rows={rows} />
          </section>

          <section className="ranking-section">
            <div className="section-heading compact">
              <div>
                <p className="section-kicker">DANH MỤC ƯU TIÊN</p>
                <h2>Các khu vực được xếp hạng cao nhất</h2>
                <p>Danh sách này là đầu ra chính của hệ thống.</p>
              </div>
              <label className="count-select">Hiển thị <select value={tableCount} onChange={(e) => setTableCount(Number(e.target.value))}><option>10</option><option>20</option><option>50</option><option>100</option></select></label>
            </div>

            <div className="ranking-table-wrap">
              <table className="ranking-table">
                <thead><tr><th>Hạng</th><th>Mức ưu tiên</th><th>Tọa độ</th><th>Bằng chứng THOR</th><th>Dấu vết KH-9</th><th>Hố bom 300 m</th></tr></thead>
                <tbody>
                  {topRows.map((r) => (
                    <tr key={r.cell_id}>
                      <td><span className="rank-number">#{r.rank}</span></td>
                      <td><span className={`level-tag level-${r.priority_level.toLowerCase().replaceAll(" ", "-")}`}>{r.priority_level}</span></td>
                      <td>{r.latitude.toFixed(4)}, {r.longitude.toFixed(4)}</td>
                      <td>{evidenceText(r.airstrike_evidence_score)}</td>
                      <td>{evidenceText(r.crater_evidence_score)}</td>
                      <td>{fmt(r.craters_within_300m)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="explain-section">
            <div className="section-heading compact">
              <div>
                <p className="section-kicker">TRÍ TUỆ NHÂN TẠO ĐANG LÀM GÌ?</p>
                <h2>Ba bước để đọc kết quả</h2>
              </div>
            </div>
            <div className="explain-grid">
              <article><span>01</span><h3>Đọc bằng chứng</h3><p>Hệ thống đưa các nguồn THOR, KH-9 và dữ liệu bối cảnh về cùng lưới không gian.</p></article>
              <article><span>02</span><h3>Học cách xếp hạng</h3><p>Mô hình học từ các khu vực đã có ghi nhận trong dữ liệu thực địa công khai để tạo thứ hạng tương đối.</p></article>
              <article><span>03</span><h3>Đưa ra danh mục</h3><p>Mỗi ô nhận một thứ hạng. Hạng cao hơn nghĩa là nên được xem xét trước, không có nghĩa chắc chắn còn vật nổ.</p></article>
            </div>
            <details className="technical-details">
              <summary>Xem nguồn dữ liệu và giới hạn diễn giải</summary>
              <div className="technical-grid">
                <div><b>Nguồn dữ liệu</b>{results.sources.map((s) => <p key={s.technical}><strong>{s.label}</strong><span>{s.technical}</span></p>)}</div>
                <div><b>Giới hạn quan trọng</b><p><strong>Không phải xác suất còn vật nổ.</strong><span>Mô hình học xu hướng có ghi nhận trong dữ liệu công khai. Ô chưa ghi nhận không được coi là khu vực an toàn.</span></p><p><strong>Không thay thế khảo sát thực địa.</strong><span>Kết quả là công cụ hỗ trợ lập kế hoạch, không phải chứng nhận an toàn.</span></p></div>
              </div>
            </details>
          </section>
        </>
      )}

      <footer className="footer">
        <b>Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn</b><span>Bản thử nghiệm nghiên cứu · Quảng Trị · Xếp hạng ưu tiên, không phải xác suất còn vật nổ</span>
      </footer>
    </main>
  );
}

function evidenceText(value: number) {
  if (value >= 0.8) return "Rất cao";
  if (value >= 0.6) return "Cao";
  if (value >= 0.4) return "Trung bình";
  if (value >= 0.2) return "Thấp";
  return "Rất thấp";
}
