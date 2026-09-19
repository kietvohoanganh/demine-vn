# Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn

Ứng dụng web hỗ trợ xếp hạng các ô không gian cần được xem xét trước trong quá trình lập kế hoạch khảo sát và rà phá bom mìn tại Quảng Trị.

Hệ thống tổng hợp hồ sơ không kích THOR, dấu vết hố bom từ ảnh vệ tinh lịch sử KH-9 và dữ liệu bối cảnh để tạo chỉ số xếp hạng tương đối cho từng ô 100 m. Kết quả được trình bày qua bản đồ, danh sách khu vực ưu tiên, tra cứu tọa độ và phần giải thích ngắn cho từng khu vực.

> Chỉ số xếp hạng không phải xác suất còn vật nổ, không xác nhận một vị trí an toàn và không thay thế khảo sát thực địa của đơn vị chuyên môn.

## Tính năng

- Hiển thị bản đồ và danh sách khu vực ưu tiên.
- Tra cứu kết quả theo tọa độ.
- Giải thích các thành phần tạo nên điểm xếp hạng.
- Tự chuyển sang nền bản đồ dự phòng khi dịch vụ bản đồ trực tuyến không khả dụng.

## Công nghệ

- Next.js 15, React 19 và TypeScript cho ứng dụng web.
- Python và scikit-learn cho quy trình chuẩn bị dữ liệu, huấn luyện và đánh giá mô hình.
- Leaflet cho bản đồ tương tác.

## Chạy ứng dụng

Yêu cầu Node.js 22.

```bash
npm install
npm run dev
```

Mở `http://localhost:3000` trên trình duyệt.

Để kiểm tra bản dựng sản xuất:

```bash
npm run build
npm run start
```

## Chạy quy trình Python

Cài các thư viện cần thiết:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Các chương trình chuẩn bị dữ liệu, huấn luyện, đồng bộ kết quả và kiểm tra nằm trong `scripts/`. Các kiểm thử nằm trong `tests/`.

## Nguồn dữ liệu

| Nhóm thông tin | Nguồn | Vai trò |
|---|---|---|
| Hoạt động không kích lịch sử | THOR | Bằng chứng lịch sử về cường độ hoạt động không kích |
| Dấu vết hố bom | KH-9 HEXAGON | Dấu vết hố bom phát hiện từ ảnh vệ tinh lịch sử |
| Dân số | WorldPop | Bối cảnh dân cư |
| Đường và thủy hệ | OpenStreetMap | Bối cảnh tiếp cận và không gian |

Dữ liệu KH-9 là dấu vết hố bom, không phải nhãn xác nhận vật nổ còn sót lại. Các ô chưa có ghi nhận thực địa cũng không được coi là khu vực an toàn.

## Cấu trúc chính

```text
app/          Trang và bố cục Next.js
components/   Thành phần giao diện và bản đồ
public/       Dữ liệu và hình ảnh phục vụ trực tiếp cho web
src/          Mã nguồn Python và dữ liệu kết quả dùng trong ứng dụng
scripts/      Quy trình dữ liệu, huấn luyện và kiểm tra
tests/        Kiểm thử TypeScript và Python
data/real/    Ảnh chụp dữ liệu nguồn có thể tái lập
```

Không xóa hoặc đổi tên các tệp trong `public/data`, `public/figures` và `src/data` nếu chưa cập nhật mã nguồn tương ứng.
