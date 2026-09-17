import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn",
  description: "Hỗ trợ xếp hạng các khu vực cần được xem xét trước trong công tác khảo sát và rà phá bom mìn tại Quảng Trị từ dữ liệu thực có kiểm kê nguồn gốc.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body>{children}</body></html>;
}
