# Chạy bản trình diễn cuối

## 1. Cài thư viện

```bash
npm install
```

## 2. Chạy phát triển

```bash
npm run dev
```

Mở `http://localhost:3000`.

## 3. Kiểm tra dữ liệu

Các địa chỉ sau phải mở được và trả về JSON:

```text
http://localhost:3000/data/ai/summary.json
http://localhost:3000/data/ai/priority.json
http://localhost:3000/data/ai/lookup_grid.json
```

## 4. Kiểm tra bản dựng sản xuất

```bash
npm run build
npm run start
```

Nếu bước `npm run build` thành công thì dự án đã sẵn sàng để đẩy lên Vercel.

## 5. Nội dung demo

Giao diện chính chỉ hiển thị kết quả xếp hạng bằng trí tuệ nhân tạo: bản đồ, danh mục ưu tiên, tra cứu tọa độ và giải thích cho khu vực đang chọn. Chỉ số xếp hạng không phải xác suất còn vật nổ và không phải chứng nhận an toàn.
