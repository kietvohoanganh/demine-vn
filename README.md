# Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn

Đây là phiên bản web trình diễn dùng dữ liệu thực của dự án tại Quảng Trị. Mục tiêu của hệ thống là **xếp hạng các ô không gian cần được xem xét trước** để hỗ trợ lập kế hoạch khảo sát và rà phá bom mìn.

## Hệ thống làm gì?

Hệ thống tổng hợp hồ sơ không kích THOR, dấu vết hố bom từ ảnh vệ tinh lịch sử KH-9 và các dữ liệu bối cảnh có sẵn. Mô hình học máy tạo một **chỉ số xếp hạng tương đối** cho từng ô 100 m, từ đó sinh danh mục khu vực ưu tiên và hiển thị trên bản đồ.

Chỉ số này **không phải xác suất còn vật nổ**, không xác nhận một vị trí an toàn và không thay thế khảo sát thực địa của đơn vị chuyên môn.

## Giao diện chính

Giao diện chỉ tập trung vào đầu ra phục vụ người dùng:

- bản đồ các khu vực được xếp hạng ưu tiên;
- danh sách các khu vực đứng đầu;
- tra cứu theo tọa độ;
- giải thích ngắn gọn vì sao một khu vực được xếp cao;
- chế độ bản đồ dự phòng khi nền bản đồ trực tuyến không tải được.

Các so sánh mô hình, kiểm chứng không gian và phân tích chuyên sâu vẫn nằm trong quy trình nghiên cứu, không đưa lên luồng demo chính.

## Chạy trên máy

Yêu cầu Node.js 22.

```bash
npm install
npm run dev
```

Mở `http://localhost:3000`.

Kiểm tra bản dựng sản xuất:

```bash
npm run build
npm run start
```

## Dữ liệu web bắt buộc

Frontend đọc các tệp sau:

```text
public/data/ai/summary.json
public/data/ai/priority.json
public/data/ai/lookup_grid.json
public/data/lookup_grid.json
src/data/results.json
src/data/priority.json
```

Không xóa hoặc đổi tên các tệp này nếu chưa cập nhật mã nguồn tương ứng.

## Triển khai lên Vercel

Dự án đã có `vercel.json` và cấu hình Next.js phù hợp. Cách triển khai khuyến nghị:

1. Đẩy mã nguồn lên GitHub.
2. Vào Vercel và chọn **Thêm dự án mới**.
3. Chọn kho GitHub của dự án.
4. Để Vercel tự nhận diện **Next.js**.
5. Không cần đặt biến môi trường cho bản demo hiện tại.
6. Nhấn **Triển khai**.

Xem hướng dẫn chi tiết tại `TRIEN_KHAI_VERCEL.md`.

## Lưu ý dữ liệu lớn

Không đưa các tệp dữ liệu nguồn dung lượng lớn như raster `.tif`, `.tiff`, `predictions.zip`, môi trường `.venv`, `node_modules` hoặc thư mục kết quả trung gian lên Vercel. Web chỉ cần các tệp JSON và mã nguồn được liệt kê ở trên.
