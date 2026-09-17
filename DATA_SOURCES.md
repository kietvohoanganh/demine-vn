# Nguồn dữ liệu

Hệ thống sử dụng các nhóm dữ liệu có nguồn gốc được kiểm kê. Tên riêng của bộ dữ liệu được giữ nguyên để tránh nhầm lẫn nguồn.

| Nhóm thông tin | Nguồn | Vai trò |
|---|---|---|
| Hoạt động không kích lịch sử | THOR | Bằng chứng lịch sử về cường độ hoạt động không kích |
| Dấu vết hố bom | KH-9 HEXAGON | Dấu vết hố bom được phát hiện từ ảnh vệ tinh lịch sử |
| Dân số | WorldPop | Bối cảnh dân cư |
| Đường và thủy hệ | OpenStreetMap | Bối cảnh tiếp cận và không gian |
| Địa hình, lớp phủ, đất | các nguồn địa không gian tương ứng trong quy trình dữ liệu | Bổ sung bối cảnh cho mô hình và phân tích |

## Nguyên tắc diễn giải

Dữ liệu KH-9 là dấu vết hố bom, không phải nhãn xác nhận vật nổ còn sót lại. Các ô chưa có ghi nhận thực địa cũng không được coi là khu vực an toàn. Vì chưa có nhãn thực địa đầy đủ ở cấp ô, chỉ số đầu ra được dùng để **xếp hạng ưu tiên**, không được gọi là xác suất còn vật nổ.
