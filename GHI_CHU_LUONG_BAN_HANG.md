# Ghi chú ôn tập: Luồng bán hàng

## Tóm tắt để trình bày

Đây là module tùy chỉnh cho Odoo Sales, không xây lại đơn bán từ đầu. Module
kế thừa các model chuẩn như `sale.order`, `sale.order.line` và `stock.picking`
để bổ sung kiểm tra tồn kho, chọn/gán Serial, khuyến mãi combo và ghi nhận bảo
hành. Luồng chính là:

**Tạo báo giá → chọn sản phẩm/Serial (không bắt buộc) → xác nhận đơn → kiểm
tra tồn và thêm quà combo → Odoo tạo phiếu giao → gán Serial → xác nhận giao
hàng → ghi nhận Serial đã bán và thời hạn bảo hành.**

## Diễn giải từng bước

### 1. Khai báo module

Trong `custom_sales/__manifest__.py`, module khai báo phụ thuộc vào Sales,
Inventory và các module CRM/bảo hành liên quan. Manifest cũng nạp các view,
báo cáo, quyền truy cập và JavaScript/XML cho giao diện chọn Serial.

### 2. Tạo báo giá và chọn sản phẩm

- Màn hình đơn bán được kế thừa trong `views/sale_order_views.xml`; view thêm
  mã khách hàng, thông tin sản phẩm, Serial, khuyến mãi và tab Serial đã giao.
- `sale.order.line` tính thông tin cấu hình sản phẩm và số lượng tồn khả dụng
  theo kho xuất của đơn.
- Widget OWL trong `static/src/js/product_serial_picker.js` gọi hàm Python
  `get_serial_picker_data` để mở hộp thoại tra cứu Serial. Chỉ Serial có trạng
  thái nghiệp vụ và vòng đời là `available`, đồng thời còn hàng chưa giữ chỗ,
  mới chọn được.
- Khi chọn một sản phẩm từ hộp thoại tìm kiếm, widget chuyển danh sách Serial
  đã chọn về trường `x_selected_serial_lot_ids` của dòng đơn. Có thể bỏ qua
  việc chọn trước; khi đó hệ thống tự gán Serial lúc xác nhận đơn.

### 3. Xác nhận đơn bán

`SaleOrder.action_confirm()` bổ sung các bước trước và sau hàm chuẩn Odoo:

1. Tìm combo khuyến mãi phù hợp với tổng tiền đơn; tạo các dòng quà còn thiếu
   với giá 0 và lưu rule combo áp dụng.
2. `_check_sale_stock_availability()` kiểm tra kho xuất, cộng số lượng theo
   sản phẩm, đổi đơn vị tính khi cần, rồi so sánh với tồn khả dụng.
3. Với hàng theo Serial, kiểm tra số lượng phải là số nguyên, có đủ Serial
   khả dụng và Serial chọn trước phải đúng sản phẩm, chưa bị dùng trùng, còn
   hàng và chưa bán/đang sửa chữa.
4. Gọi `super().action_confirm()` để Odoo thực hiện xác nhận đơn chuẩn và tạo
   phiếu giao hàng.
5. Gọi `_auto_assign_delivery_serials()` trên phiếu giao: ưu tiên Serial khách
   đã chọn, rồi trộn ngẫu nhiên các Serial còn khả dụng để điền phần còn thiếu.
   Nếu không đủ Serial thì báo lỗi thay vì giao thiếu.

### 4. Xác nhận phiếu giao hàng

- `button_validate()` kiểm tra và bổ sung Serial trước khi gọi xác nhận chuẩn
  của Odoo.
- `_validate_sale_delivery_serials()` yêu cầu đủ số lượng giao; mỗi món theo
  Serial phải có đúng một Serial, thuộc đúng sản phẩm, không trùng, còn trạng
  thái khả dụng và vẫn có số lượng tại kho xuất.
- Trong `_action_done()`, sau khi Odoo hoàn tất giao hàng, code cập nhật từng
  Serial: khách mua, đơn/dòng đơn bán, phiếu giao, ngày bán, trạng thái `sold`,
  ngày bắt đầu bảo hành và ngày hết hạn bảo hành. Thời hạn lấy từ cấu hình sản
  phẩm và được cộng theo tháng.

### 5. Tra cứu sau bán

`serial_lot_ids` trên đơn bán được tính từ các dòng hàng của phiếu giao. Vì
vậy tab “Serial bán hàng” phản ánh Serial trên phiếu giao, không chỉ Serial
được chọn trước ở báo giá. Model khách hàng cũng có lịch sử các đơn đã xác
nhận/hoàn tất.

## Các file nên mở khi thuyết trình

- `custom_addons/custom_sales/__manifest__.py`: module phụ thuộc và cách nạp
  giao diện.
- `custom_addons/custom_sales/views/sale_order_views.xml`: các trường hiển thị
  trên báo giá/đơn bán.
- `custom_addons/custom_sales/static/src/js/product_serial_picker.js` và
  `custom_addons/custom_sales/static/src/xml/product_serial_picker.xml`: hộp
  thoại chọn Serial phía giao diện.
- `custom_addons/custom_sales/models/product_serial_picker.py`: dữ liệu Serial
  trả về cho giao diện và kiểm tra ràng buộc trên dòng đơn.
- `custom_addons/custom_sales/models/sale_order_custom.py`: logic chính của
  xác nhận đơn, tồn kho, combo, gán Serial và cập nhật bảo hành khi giao xong.
- `custom_addons/custom_warranty/models/sale_order_line.py`: quan hệ Serial đã
  giao với dòng đơn bán để truy xuất hậu mãi.
- `custom_addons/custom_sales/tests/test_sales_custom.py`: các kiểm thử nghiệp
  vụ về Serial, tồn kho, combo và bảo hành.

## Câu hỏi thầy có thể hỏi

**Vì sao dùng `_inherit`?**  
Để mở rộng model chuẩn Odoo và giữ lại quy trình Sales/Inventory có sẵn, thay
vì tạo một hệ thống đơn hàng riêng.

**Khác nhau giữa xác nhận đơn và hoàn tất giao hàng là gì?**  
Xác nhận đơn chốt bán hàng và tạo phiếu giao. Hoàn tất phiếu giao mới xác nhận
hàng thực sự rời kho; code chỉ cập nhật Serial thành `sold` và bắt đầu bảo
hành ở bước hoàn tất này.

**Vì sao kiểm tra tồn hai lần?**  
Khi xác nhận đơn, kiểm tra tổng tồn để không nhận đơn vượt quá khả năng kho.
Khi giao, kiểm tra lại Serial cụ thể vì hàng có thể bị giữ chỗ, thay đổi hoặc
được giao bởi một thao tác khác sau lúc lập đơn.

**Nếu nhân viên không chọn Serial trước thì sao?**  
Khi xác nhận đơn, hệ thống chọn các Serial khả dụng cho phiếu giao; nếu số
lượng cần giao lớn hơn số Serial còn dùng được thì báo lỗi.

**Serial được xem là đã bán từ lúc nào?**  
Sau khi phiếu giao hàng hoàn tất, không phải ngay khi báo giá được tạo hay đơn
bán vừa được xác nhận.

**Kiểm thử nào chứng minh luồng này?**  
Các test trong `test_sales_custom.py` kiểm tra Serial không khả dụng bị vô hiệu,
gán Serial khi xác nhận, từ chối thiếu tồn và lưu khách hàng/ngày bán/hạn bảo
hành sau khi giao.
