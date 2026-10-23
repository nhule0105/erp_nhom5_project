# Đồ án ERP - Nhóm 5

Các module tùy chỉnh cho Odoo 18 nằm trong `custom_addons/`:

- `custom_warranty`: thêm thông tin khách hàng, trạng thái và ngày bảo hành cho
  serial; quản lý phiếu sửa chữa/bảo hành và đổi mới 1-1 với Kanban, kiểm tra
  điều kiện tiếp nhận, luân chuyển tồn kho và phân quyền quản lý kho.
- `custom_sales`: hiển thị serial đã giao trên đơn bán hàng và ghi nhận chủ sở
  hữu, trạng thái, ngày bán và hạn bảo hành theo thời hạn cấu hình của sản phẩm
  khi hoàn tất phiếu giao hàng.

## Cài đặt

1. Cấu hình Odoo để nhận diện thư mục `custom_addons` (đã mount vào
   `/mnt/extra-addons` trong `docker-compose.yml`).
2. Khởi động Odoo và PostgreSQL.
3. Trong Odoo, bật chế độ nhà phát triển, cập nhật danh sách ứng dụng, sau đó
   cài **Tự động hóa Bán hàng & Serial Number**. Module này tự phụ thuộc vào
   **Quản lý Bảo hành & Đổi trả**, **Sales** và **Inventory**.

## Luồng sử dụng

1. Tạo sản phẩm có theo dõi tồn kho theo serial và nhập serial vào kho.
2. Tạo đơn bán, xác nhận, gán serial trên phiếu giao hàng theo luồng chuẩn của
   Odoo và hoàn tất phiếu. Serial được đánh dấu đã bán và liên kết với khách
   hàng; ngày kết thúc bao test được tính là ngày giao cộng 30 ngày.
3. Cấu hình thời hạn bảo hành và thời hạn đổi mới ở tab Kho của từng sản phẩm.
   Ngày hết hạn được ghi nhận khi giao hàng; thời hạn đổi mới mặc định là 30
   ngày nhưng có thể cấu hình theo sản phẩm.
4. Tạo phiếu trong menu **Hậu Mãi & Đổi Trả** bằng cách nhập serial hoặc số
   điện thoại khách hàng. Kỹ thuật viên theo dõi sửa chữa qua các giai đoạn
   **Mới tiếp nhận → Đang sửa → Chờ thay linh kiện → Đã xong**.
5. Quản lý kho có thể duyệt đổi mới 1-1 khi lỗi do nhà sản xuất, còn trong
   thời hạn đổi mới, đạt kiểm tra ngoại quan/bảo mật và serial thay thế cùng
   sản phẩm còn tồn kho nội bộ. Hệ thống ghi nhận các phiếu dịch chuyển kho,
   chuyển máy lỗi sang vị trí hàng lỗi, giao máy mới cho khách và giữ nguyên
   ngày bán/hạn bảo hành ban đầu.

## Cấu trúc chính

```text
custom_addons/
├── custom_sales/
│   ├── models/
│   └── views/
└── custom_warranty/
    ├── data/
    ├── models/
    ├── security/
    └── views/
```
