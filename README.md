# Đồ án ERP - Nhóm 5

Các module tùy chỉnh cho Odoo 18 nằm trong `custom_addons/`:

- `custom_warranty`: thêm thông tin khách hàng, trạng thái và ngày bảo hành cho
  serial; quản lý phiếu bảo hành/đổi trả với Kanban và phân quyền kho.
- `custom_sales`: hiển thị serial đã giao trên đơn bán hàng và ghi nhận chủ sở
  hữu, trạng thái cùng thời hạn bao test 30 ngày khi hoàn tất phiếu giao hàng.

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
3. Tạo phiếu trong menu **Bảo hành & Đổi trả**. Với nghiệp vụ đổi 1-1, chọn
   serial lỗi và serial thay thế cùng sản phẩm. Serial thay thế phải đang sẵn
   sàng; khi hoàn tất, serial cũ chuyển sang lỗi/chờ xử lý và serial mới được
   gán cho khách hàng.

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
