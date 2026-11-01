# Luồng demo Bảo hành, Sửa chữa và Đổi mới 1-1

Tài liệu hướng dẫn demo theo hai vai trò nghiệp vụ thống nhất: **Nhân viên**
(tra cứu, tiếp nhận, ghi checklist, theo dõi/sửa chữa và lập yêu cầu đổi) và
**Chủ cửa hàng (quản lý/thủ kho)** (xét duyệt đổi, điều phối serial và kho).
Phân công nội bộ: Châu phụ trách nghiệp vụ sửa chữa/bảo hành; Như phụ trách
đổi mới 1-1 và kết nối hậu mãi. Các bước ghi rõ phần code đã hỗ trợ và phần
cần thao tác/xác nhận thủ công.

> Nên demo trên database thử nghiệm riêng. Duyệt đổi sẽ thực hiện giao dịch
> kho thật trong database đó; không thử trên database đang dùng thật.

PDF biên nhận dùng logo, tên và địa chỉ lấy từ hồ sơ công ty đang chọn trong
Odoo. Trước khi in demo, vào **Thiết lập → Người dùng & Công ty → Công ty** để
cấu hình thông tin công ty thật; không dùng nội dung mẫu “Your logo” hoặc địa
chỉ San Francisco trên chứng từ gửi khách.

## 1. Chuẩn bị dữ liệu mẫu không cần nhập tay

### Cách khuyến nghị: cài module vào database demo mới

Addon có dữ liệu mẫu trong `custom_addons/custom_warranty/demo/warranty_demo.xml`.
Khi cài `custom_sales` trên database mới và **không tắt demo data**, Odoo cài
các dependency `custom_crm`, `custom_warranty` và tạo sẵn dữ liệu nhóm cùng
khách hàng, sản phẩm, serial, phiếu sửa chữa và phiếu đổi.

Từ PowerShell tại thư mục dự án, chạy lệnh sau để khởi tạo một database riêng
`erp_nhom5_demo` và cài module cùng các dependency:

```powershell
docker compose exec -T web sh -c 'odoo -d erp_nhom5_demo -i custom_sales --stop-after-init --http-port=8070 --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"'
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

Trước khi demo đổi trên hàng hóa của cửa hàng, kiểm tra trường **Nhóm chính
sách đổi** ở sản phẩm hoặc danh mục. Thiết bị mới/đã qua sử dụng áp dụng tối đa
30 ngày; phụ kiện phải có thời hạn theo hãng (tối đa 365 ngày). Sản phẩm chưa
được phân nhóm sẽ không đủ điều kiện đổi. Hai sản phẩm laptop/điện thoại trong
bộ dữ liệu demo đã được phân nhóm `Thiết bị mới`.

### Tạo mới / khôi phục dữ liệu demo sau khi đổi trạng thái

Bộ dữ liệu mới có 3-5 phiếu trong từng cột Kanban:

| Trạng thái | Số phiếu |
|---|---:|
| Mới tiếp nhận | 4 |
| Chờ serial thay thế | 3 |
| Đang sửa | 4 |
| Chờ thay linh kiện | 3 |
| Đã xong | 4 |

Phiếu sửa chữa mẫu được chuyển sang các trạng thái qua thao tác nghiệp vụ của
module; các phiếu đổi chờ serial vẫn chưa ghi giao dịch kho. Sau khi đã thử
chuyển trạng thái, duyệt đổi hoặc hoàn tất phiếu, cách khôi phục đầy đủ nhất
là tạo lại **database demo**. Chạy các lệnh sau trong **PowerShell tại thư mục
dự án**:

```powershell
docker compose exec -T db psql -U odoo -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='erp_nhom5_demo' AND pid <> pg_backend_pid();"
if ($LASTEXITCODE -ne 0) { throw "Không thể ngắt kết nối database demo." }

docker compose exec -T db dropdb -U odoo erp_nhom5_demo
if ($LASTEXITCODE -ne 0) { throw "Không thể xóa database demo." }

docker compose exec -T web sh -c 'odoo -d erp_nhom5_demo -i custom_sales --stop-after-init --http-port=8070 --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"'
if ($LASTEXITCODE -ne 0) { throw "Cài module hoặc nạp demo thất bại; xem lỗi Odoo phía trên." }

docker compose restart web
if ($LASTEXITCODE -ne 0) { throw "Không thể khởi động lại dịch vụ Odoo web." }
```

Với database chưa tồn tại, chỉ cần chạy lệnh cài module ở bước trên; Odoo sẽ
tạo database và nạp demo. Với database đã có, dùng đầy đủ lệnh khôi phục ở
trên. **Không dùng `-u custom_warranty` để khôi phục trạng thái**, vì Odoo
không nạp lại XML demo khi nâng cấp module.

**Cảnh báo:** `dropdb` xóa toàn bộ database `erp_nhom5_demo`, bao gồm các bản
ghi thử khác bạn thêm vào đó. Chỉ tiếp tục nếu chấp nhận xóa database demo và
hãy sao lưu dữ liệu cần giữ trước. Lệnh chỉ tác động `erp_nhom5_demo`, không
xóa `erp_nhom5`. Sau khi hoàn tất, mở lại database demo và tải trang bằng
Ctrl+F5.

### Bộ dữ liệu có sẵn

| Bản ghi / mục đích | Mã / thông tin mẫu | Dùng để |
|---|---|---|
| Khách hàng | Nguyễn Minh Anh, Trần Quốc Bình, Lê Ngọc Chi | Tra cứu khách hàng và lịch sử hậu mãi |
| Laptop | `DEMO-LAP-0001`–`DEMO-LAP-0010` | Phiếu sửa mới, đang sửa và chờ linh kiện |
| Điện thoại | `DEMO-PHN-0001`, `DEMO-PHN-0004`–`DEMO-PHN-0006` | Phiếu sửa chữa đã hoàn tất |
| Máy cũ đổi | `DEMO-PHN-0002` | Serial thuộc khách hàng, có giao dịch tồn ở vị trí Khách hàng |
| Máy thay thế | `DEMO-PHN-0003` | Serial còn trong kho nội bộ, cùng sản phẩm với máy cũ |
| Phiếu đổi chờ serial | `DEMO-PHN-0007`–`DEMO-PHN-0009` | Minh họa đủ điều kiện đổi nhưng đang chờ hàng |
| Phiếu sửa chữa | 3 mới, 4 đang sửa, 3 chờ linh kiện, 4 đã xong | Mỗi cột có dữ liệu để demo và xem Kanban |
| Phiếu đổi | 1 mới tiếp nhận, 3 chờ serial | Minh họa tiếp nhận đổi và chờ serial thay thế |

Các phiếu sẽ có mã `HM/...` do sequence cấp. Có thể tìm theo serial trong
menu hậu mãi hoặc tìm serial trong Inventory rồi mở các phiếu liên quan.

### Nếu cần thêm demo bán hàng/đơn hàng

README có hướng dẫn script tạo 10 đơn demo bán laptop `XPS15` tại mục **Tạo 10
giao dịch demo cho custom Bán hàng**. Script đó dành cho luồng bán hàng; nó
không thay thế bộ demo phiếu sửa chữa/đổi tại `custom_warranty/demo/`.
Kiểm tra kỹ database đích trước khi chạy bất kỳ seed nào.

## 2. Kịch bản demo — Nhân viên tiếp nhận và sửa chữa

### 2.1 Tra cứu và nhận máy

1. Mở menu **Bảo Hành, Sửa Chữa & Đổi Mới 1-1**.
2. Tìm phiếu theo serial `DEMO-LAP-0001` hoặc mở phiếu sửa tương ứng.
3. Trình bày thông tin tự liên kết: sản phẩm, khách hàng, đơn bán nếu có,
   ngày mua, hạn bảo hành, số ngày còn lại và mô tả lỗi.
4. Trình bày checklist tiếp nhận: chọn nhanh biểu hiện lỗi và đánh dấu các
   mục tình trạng đạt; chỉ nhập mô tả/ghi chú thêm khi có chi tiết khác thường.
   Có thể đính kèm ảnh và mở biên nhận PDF, thông
   tin kỹ thuật viên và SLA/ngày hẹn. Chữ ký trên biên nhận là khu vực ký tay,
   chưa phải chữ ký điện tử. Lưu ý chỉ demo các trường có dữ liệu thực trên
   phiếu; việc tính phí/miễn phí không tự tạo hóa đơn hoặc thanh toán.
   Phiếu sửa chữa và phiếu đổi có các bước trạng thái riêng; ngày hẹn tự tính
   theo ngày tiếp nhận và số ngày SLA.
   Khi tạo phiếu, dùng nút **Lưu** chuẩn của Odoo trên thanh công cụ; phiếu
   sửa chữa thông thường có thể tiếp tục xử lý sau khi lưu.

### 2.2 Các bước sửa chữa

1. Mở phiếu serial `DEMO-LAP-0003` ở trạng thái **Mới tiếp nhận**; bấm
   **Bắt đầu sửa**. Phiếu sang **Đang sửa** và serial chuyển sang trạng thái
   đang bảo hành/sửa chữa.
2. Bấm **Chờ linh kiện** để chuyển sang trạng thái chờ.
3. Khi có linh kiện, bấm **Tiếp tục sửa**.
4. Nhập kết quả vào **Kết quả sửa chữa**. Khi đã xác định nguyên nhân và hạn
   bảo hành, nhân viên chọn đề xuất Miễn phí/Tính phí, rồi bấm **Gửi duyệt**.
   Nút này lưu thay đổi và chuyển đề xuất cho Chủ cửa hàng. Chủ cửa hàng kiểm
   tra rồi bấm **Xác nhận quyết định bảo hành**; nhân viên không có quyền xác
   nhận bước này.
5. Bấm **Hoàn tất sửa chữa**. Hệ thống không cho hoàn tất nếu thiếu kết quả
   hoặc quyết định đã được Chủ cửa hàng xác nhận; serial trở lại trạng thái đã bán.
6. Để minh họa nhiều trạng thái cùng lúc, mở thêm phiếu `DEMO-LAP-0001`
   (đang sửa), `DEMO-LAP-0002` (chờ linh kiện) và `DEMO-PHN-0001`
   (đã hoàn tất).

**Lưu ý demo:** thao tác trên các phiếu mẫu sẽ thay đổi trạng thái của chúng.
Nếu muốn chạy lại đúng từ đầu, tạo database demo mới hoặc khôi phục bản sao
được tạo trước buổi trình bày.

## 3. Kịch bản demo — Nhân viên lập yêu cầu, Chủ cửa hàng duyệt đổi 1-1

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
4. Nhân viên bấm **Gửi duyệt**. Nút này lưu phiếu và gửi yêu cầu cho chủ cửa
   hàng; thông tin xét đổi bị khóa trong lúc chờ duyệt.
5. Nút **Duyệt đổi mới 1-1** chỉ hiện cho thành viên nhóm quản lý kho
   (`stock.group_stock_manager`); backend cũng từ chối người không thuộc nhóm
   hoặc phiếu chưa được gửi duyệt. Chủ cửa hàng cần đăng nhập bằng tài khoản
   đã được cấp đúng nhóm.

### 3.2 Hoàn tất đổi

1. Nhân viên gửi phiếu đổi đủ điều kiện bằng nút **Gửi duyệt**. Có thể lọc các
   yêu cầu đang chờ bằng bộ lọc **Chờ chủ cửa hàng duyệt**.
2. Chủ cửa hàng/quản lý-thủ kho đăng nhập bằng tài khoản quản lý kho và bấm
   **Duyệt đổi mới 1-1**.
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
  trong kho, dùng **Chờ serial thay thế**; khi có hàng, chọn serial mới và bấm
  **Gửi duyệt**, sau đó chủ cửa hàng duyệt. Hệ thống hiện chưa tự tạo đơn
  mua/backorder.
- **Chuyển sang sửa chữa:** với phiếu đổi chưa duyệt, nhập lý do chuyển rồi
  bấm **Chuyển sang sửa chữa**. Phiếu lưu lý do/ngày chuyển và tiếp tục ở
  trạng thái mới tiếp nhận của luồng sửa chữa. Đây là điểm bàn giao từ phần
  nhân viên sang quy trình sửa chữa.

Hai nhánh này chưa có bản ghi riêng trong bộ XML demo hiện tại. Muốn demo các
nhánh đó, hãy dùng database demo mới và tạo phiếu thử qua giao diện; hoặc bổ
sung chúng vào script seed tự động sau khi thống nhất bộ dữ liệu demo. Không
thực hiện trên database đang dùng thật.

## 4. Báo cáo hậu mãi dùng chung

1. Mở menu **Báo cáo Hậu mãi**.
2. Dùng bộ lọc theo loại phiếu, trạng thái và nguyên nhân.
3. Chuyển giữa biểu đồ và pivot để xem số phiếu sửa chữa/đổi mới theo thời
   gian.
4. Báo cáo có các chiều phiếu hậu mãi và thông tin thời gian xử lý theo cấu
   hình hiện tại. Kiểm tra dữ liệu demo trước khi kết luận số liệu đại diện
   cho hoạt động thật.

## 5. Danh sách kiểm tra trước buổi demo

- [ ] Đã đăng nhập vào database thử nghiệm, không phải database đang dùng thật.
- [ ] Đã bật/có dữ liệu demo: tìm thấy serial `DEMO-LAP-0003` và
  `DEMO-PHN-0002`.
- [ ] Tài khoản quản lý kho thuộc nhóm `stock.group_stock_manager`.
- [ ] Chưa duyệt phiếu đổi nếu cần trình bày bước kiểm tra điều kiện.
- [ ] Đã tạo bản sao database hoặc sẵn sàng tạo database demo mới nếu cần chạy
  lại từ đầu.
- [ ] Không giới thiệu các hạng mục chưa làm (gửi/nhận bảo hành hãng thành
  workflow riêng, tự tạo đơn mua/backorder, xử lý phụ kiện thiếu, luân chuyển
  kho combo đầy đủ hoặc chữ ký điện tử) như thể chúng đã có trong hệ thống.
