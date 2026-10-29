# Luồng demo Bảo hành, Sửa chữa và Đổi mới 1-1

Tài liệu hướng dẫn demo hai phần nghiệp vụ: **Châu — tiếp nhận, bảo hành và
sửa chữa**; **Như — đổi mới 1-1 và kết nối hậu mãi**. Các bước dưới đây dựa
trên luồng hiện được triển khai trong module `custom_warranty`.

> Nên demo trên database thử nghiệm riêng. Duyệt đổi sẽ thực hiện giao dịch
> kho thật trong database đó; không thử trên database đang dùng thật.

## 1. Chuẩn bị dữ liệu mẫu không cần nhập tay

### Cách khuyến nghị: cài module vào database demo mới

Addon đã có sẵn dữ liệu mẫu trong `custom_addons/custom_warranty/demo/warranty_demo.xml`.
Khi cài `custom_warranty` trên database mới và **không tắt demo data**, Odoo
tạo sẵn khách hàng, sản phẩm, serial, phiếu sửa chữa và phiếu đổi. Không cần
tạo từng bản ghi qua giao diện.

Từ PowerShell tại thư mục dự án, chạy lệnh sau để khởi tạo một database riêng
`erp_nhom5_demo` và cài module cùng các dependency:

```powershell
docker compose exec -T web sh -c 'odoo -d erp_nhom5_demo -i custom_warranty --stop-after-init --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"'
```

Sau khi lệnh hoàn tất, mở database `erp_nhom5_demo` trên Odoo. Nếu cần khởi
động lại dịch vụ web để database mới xuất hiện trong bộ chọn:

```powershell
docker compose restart web
```

Không thêm `--without-demo=all` vào lệnh cài. Nếu Odoo hỏi có nạp dữ liệu demo
trong giao diện quản lý database, hãy bật lựa chọn **Load demonstration data**.

**Lưu ý:** demo XML được nạp lúc cài module, không phải lúc nâng cấp. Nếu
`custom_warranty` đã được cài trên database nhưng lúc cài không bật demo, lệnh
`-u custom_warranty` sẽ không tự nạp lại các bản ghi demo. Không nên chạy XML
demo thủ công hoặc xóa module để nạp lại trên database đang sử dụng. Hãy tạo
database demo mới như hướng dẫn trên, hoặc dùng bản sao database thử nghiệm và
một script seed riêng đã được kiểm tra nếu cần đưa dữ liệu vào database đó.

### Bộ dữ liệu có sẵn

| Bản ghi / mục đích | Mã / thông tin mẫu | Dùng để |
|---|---|---|
| Khách hàng | Nguyễn Minh Anh, Trần Quốc Bình, Lê Ngọc Chi | Tra cứu khách hàng và lịch sử hậu mãi |
| Laptop | `DEMO-LAP-0001`, `DEMO-LAP-0002` | Minh họa sửa đang thực hiện và chờ linh kiện |
| Laptop | `DEMO-LAP-0003` | Phiếu mới tiếp nhận để demo toàn bộ luồng sửa chữa |
| Điện thoại | `DEMO-PHN-0001` | Phiếu sửa chữa đã hoàn tất |
| Máy cũ đổi | `DEMO-PHN-0002` | Serial thuộc khách hàng, có giao dịch tồn ở vị trí Khách hàng |
| Máy thay thế | `DEMO-PHN-0003` | Serial còn trong kho nội bộ, cùng sản phẩm với máy cũ |
| Phiếu sửa chữa | Mới nhận / đang sửa, chờ linh kiện, đã hoàn tất | Demo công việc Châu |
| Phiếu đổi | Phiếu đổi mới trạng thái mới, đủ checklist | Demo điều kiện và duyệt đổi của Như |

Các phiếu sẽ có mã `HM/...` do sequence cấp. Có thể tìm theo serial trong
menu hậu mãi hoặc tìm serial trong Inventory rồi mở các phiếu liên quan.

### Nếu cần thêm demo bán hàng/đơn hàng

README có hướng dẫn script tạo 10 đơn demo bán laptop `XPS15` tại mục **Tạo 10
giao dịch demo cho custom Bán hàng**. Script đó dành cho luồng bán hàng; nó
không thay thế bộ demo phiếu sửa chữa/đổi tại `custom_warranty/demo/`.
Kiểm tra kỹ database đích trước khi chạy bất kỳ seed nào.

## 2. Kịch bản demo Châu — tiếp nhận và sửa chữa

### 2.1 Tra cứu và nhận máy

1. Mở menu **Bảo Hành, Sửa Chữa & Đổi Mới 1-1**.
2. Tìm phiếu theo serial `DEMO-LAP-0001` hoặc mở phiếu sửa tương ứng.
3. Trình bày thông tin tự liên kết: sản phẩm, khách hàng, đơn bán nếu có,
   ngày mua, hạn bảo hành, số ngày còn lại và mô tả lỗi.
4. Nêu checklist tiếp nhận hiện có: ngoại quan, dấu hiệu vào nước, bảo mật,
   ghi chú tình trạng và mô tả lỗi. Hồ sơ ảnh/biên nhận, phân công kỹ thuật
   viên và SLA chưa được triển khai; không demo như tính năng đã hoàn tất.

### 2.2 Các bước sửa chữa

1. Mở phiếu serial `DEMO-LAP-0003` ở trạng thái **Mới tiếp nhận**; bấm
   **Bắt đầu sửa**. Phiếu sang **Đang sửa** và serial chuyển sang trạng thái
   đang bảo hành/sửa chữa.
2. Bấm **Chờ linh kiện** để chuyển sang trạng thái chờ.
3. Khi có linh kiện, bấm **Tiếp tục sửa**.
4. Nhập kết quả vào **Kết quả sửa chữa** rồi bấm **Hoàn tất sửa chữa**.
   Không thể hoàn tất nếu chưa có kết quả; serial trở lại trạng thái đã bán.
5. Để minh họa nhiều trạng thái cùng lúc, mở thêm phiếu `DEMO-LAP-0001`
   (đang sửa), `DEMO-LAP-0002` (chờ linh kiện) và `DEMO-PHN-0001`
   (đã hoàn tất).

**Lưu ý demo:** thao tác trên các phiếu mẫu sẽ thay đổi trạng thái của chúng.
Nếu muốn chạy lại đúng từ đầu, tạo database demo mới hoặc khôi phục bản sao
được tạo trước buổi trình bày.

## 3. Kịch bản demo Như — đổi mới 1-1

### 3.1 Kiểm tra điều kiện đổi

1. Mở phiếu đổi có serial cũ `DEMO-PHN-0002`, serial thay thế
   `DEMO-PHN-0003`.
2. Trình bày khách hàng, sản phẩm, ngày mua, hạn bảo hành và đơn bán nếu đã
   được liên kết.
3. Xác nhận các điều kiện được kiểm tra ở backend:
   - Serial cũ đang thuộc khách hàng, có khách hàng và ngày mua.
   - Nguyên nhân là **lỗi nhà sản xuất**.
   - Đạt checklist ngoại quan, không vào nước/chập cháy và bảo mật.
   - Còn thời hạn đổi cấu hình cho sản phẩm/danh mục.
   - Serial thay thế cùng sản phẩm và còn sẵn sàng.
4. Nút **Duyệt đổi mới 1-1** chỉ dành cho thành viên nhóm **Inventory /
   Administrator** (`stock.group_stock_manager`). Nhân viên thường gọi action
   từ backend cũng sẽ bị từ chối.

### 3.2 Hoàn tất đổi

1. Trước khi duyệt, chỉ trình bày các điều kiện và checklist; thao tác duyệt
   không thể dùng lại trên cùng phiếu.
2. Đăng nhập bằng tài khoản quản lý kho và bấm **Duyệt đổi mới 1-1**.
3. Mở tab **Giao dịch kho** để thấy:
   - Serial cũ được chuyển từ vị trí Khách hàng sang vị trí hàng lỗi/điều
     chỉnh.
   - Serial thay thế được xuất từ kho nội bộ đến vị trí Khách hàng.
4. Mở serial thay thế và trình bày chuỗi liên kết máy cũ → máy mới, khách
   hàng, thông tin bán hàng và quyền lợi bảo hành được giữ từ serial cũ.
5. Tạo phiếu sửa chữa hậu mãi cho serial mới để minh họa tra cứu tiếp theo.

> Chỉ duyệt khi sẵn sàng hoàn tất giao dịch trong database demo. Hệ thống ghi
> nhận tồn kho thật trong database; không dùng bản ghi đã duyệt để trình bày
> lại luồng “trước khi duyệt”.

### 3.3 Luồng chờ serial và chuyển sang sửa chữa

- **Chờ serial thay thế:** trên phiếu đổi mới đủ điều kiện nhưng chưa có serial
  trong kho, dùng **Chờ serial thay thế**; khi có hàng, chọn serial mới rồi
  quản lý kho duyệt. Hệ thống hiện chưa tự tạo đơn mua/backorder.
- **Chuyển sang sửa chữa:** với phiếu đổi chưa duyệt, nhập lý do chuyển rồi
  bấm **Chuyển sang sửa chữa**. Phiếu lưu lý do/ngày chuyển và tiếp tục ở
  trạng thái mới tiếp nhận của luồng sửa chữa. Đây là điểm bàn giao từ phần
  Như sang quy trình Châu.

Hai nhánh này chưa có bản ghi riêng trong bộ XML demo hiện tại. Muốn demo các
nhánh đó, hãy dùng database demo mới và tạo phiếu thử qua giao diện; hoặc bổ
sung chúng vào script seed tự động sau khi thống nhất bộ dữ liệu demo. Không
thực hiện trên database đang dùng thật.

## 4. Báo cáo hậu mãi dùng chung

1. Mở menu **Báo cáo Hậu mãi**.
2. Dùng bộ lọc theo loại phiếu, trạng thái và nguyên nhân.
3. Chuyển giữa biểu đồ và pivot để xem số phiếu sửa chữa/đổi mới theo thời
   gian.
4. Nêu rõ báo cáo hiện tổng hợp số lượng phiếu; chỉ số SLA/thời gian xử lý
   chưa có vì chưa được triển khai.

## 5. Danh sách kiểm tra trước buổi demo

- [ ] Đã đăng nhập vào database thử nghiệm, không phải database đang dùng thật.
- [ ] Đã bật/có dữ liệu demo: tìm thấy serial `DEMO-LAP-0003` và
  `DEMO-PHN-0002`.
- [ ] Tài khoản quản lý kho thuộc nhóm `stock.group_stock_manager`.
- [ ] Chưa duyệt phiếu đổi nếu cần trình bày bước kiểm tra điều kiện.
- [ ] Đã tạo bản sao database hoặc sẵn sàng tạo database demo mới nếu cần chạy
  lại từ đầu.
- [ ] Không giới thiệu các hạng mục chưa làm (SLA, ảnh/biên nhận, tự tạo đơn
  mua, xử lý phụ kiện thiếu) như thể chúng đã có trong hệ thống.
