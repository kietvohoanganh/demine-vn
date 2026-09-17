# Triển khai lên Vercel

## Cách khuyến nghị: GitHub → Vercel

### 1. Kiểm tra bản dựng trên máy

```bash
npm install
npm run build
```

Nếu không có lỗi, tiếp tục.

### 2. Đẩy lên GitHub

```bash
git add .
git commit -m "Hoan thien giao dien xep hang uu tien"
git push origin main
```

### 3. Tạo dự án trên Vercel

- Đăng nhập Vercel.
- Chọn **Add New → Project**.
- Chọn kho GitHub của dự án.
- Framework: **Next.js**.
- Root Directory: `./`.
- Build Command: để mặc định (`next build`).
- Không cần biến môi trường cho bản demo hiện tại.
- Chọn **Deploy**.

### 4. Kiểm tra sau triển khai

Mở các đường dẫn sau trên tên miền Vercel:

```text
/data/ai/summary.json
/data/ai/priority.json
/data/ai/lookup_grid.json
```

Sau đó kiểm tra:

- trang chính tải được;
- bản đồ có điểm ưu tiên;
- nhấn điểm mở được bảng giải thích;
- tra cứu tọa độ hoạt động;
- bản đồ tự chuyển sang nền dự phòng nếu nhà cung cấp bản đồ trực tuyến không phản hồi.

## Lưu ý

Không đưa `.venv`, `node_modules`, raster dung lượng lớn, tệp nén dữ liệu nguồn hoặc các thư mục đầu ra nghiên cứu lớn vào bản triển khai. Các tệp đó không cần thiết cho frontend.
