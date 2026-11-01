# Báo cáo tiến độ tuần — Toàn bộ đồ án ERP Nhóm 5

**Thời gian báo cáo:** 26/10/2026–31/10/2026  
**Môi trường kiểm tra:** Odoo 18, database thử nghiệm `erp_nhom5_demo`  
**Phạm vi:** Toàn bộ mã nguồn dự án, ba addon tùy chỉnh và các luồng tích hợp với
Sales, Inventory, PostgreSQL nguồn và dữ liệu demo.

## 1. Tổng quan phạm vi nhóm

Trong repository hiện có **3 addon tùy chỉnh**:

1. `custom_crm` — danh mục sản phẩm, thuộc tính kỹ thuật và quản lý combo.
2. `custom_sales` — đơn bán, khách hàng, tồn kho và Serial Number.
3. `custom_warranty` — tiếp nhận bảo hành/sửa chữa, đổi mới 1-1 và báo cáo
   hậu mãi.

Các addon tích hợp với ứng dụng chuẩn Odoo như **Sales Management**,
**Inventory/Stock**, sản phẩm và khách hàng. Đây là cấu hình/mở rộng trên Odoo,
không phải các addon chuẩn do nhóm tự viết.

Ngoài addon, repository có script kết nối Odoo, xem trước/nhập dữ liệu từ
`laptop_erp`, tạo dữ liệu nguồn mẫu có kiểm soát backup, cùng seed demo cho
luồng bán hàng và hậu mãi.

**Tóm tắt trạng thái:** các luồng nghiệp vụ cốt lõi đã có code backend và giao
diện. Cả ba addon đã được cài trên database thử nghiệm. Lượt kiểm thử tích hợp
gần nhất ghi nhận **31 post-tests, 0 lỗi, 0 thất bại**; test tự động hiện tập
trung ở Sales và Hậu mãi, chưa có bộ test độc lập cho CRM. Phần nhập dữ liệu
thực từ nguồn và kiểm thử người dùng cuối cần tiếp tục xác nhận trên môi trường
được nhóm sử dụng.

## 2. Tiến độ theo từng addon

| Addon | Đã hoàn thành | Đang kiểm chứng / hoàn thiện | Chưa hoàn thành / cần quyết định |
|---|---|---|---|
| **`custom_crm` — Danh mục sản phẩm CRM** (`18.0.2.3.0`) | Danh mục laptop/phụ kiện và cấu hình thuộc tính kỹ thuật; cấu hình combo/quà tặng theo khoảng tổng hóa đơn; chọn sản phẩm quà; theo dõi tồn khả dụng và serial phụ kiện; quản lý vòng đời combo/linh kiện (sẵn sàng, đã xuất, lỗi); hiển thị số combo khả dụng. | Kiểm tra cấu hình combo kết hợp với đơn bán và tồn thực trên database demo. Chưa có bộ test riêng trong `custom_crm`; một số luồng được kiểm tra thông qua test Sales. | Trường giới hạn giá trị quà `gift_value_limit` đã có trên model/giao diện và kiểm tra không âm, nhưng chưa được thực thi end-to-end để giới hạn giá trị quà khi áp dụng. Cần xác nhận quy tắc giá trị, giá tham chiếu và cách xử lý khi vượt mức. |
| **`custom_sales` — Bán hàng Laptop** (`18.0.2.6.0`) | Tự sinh mã khách hàng; hiển thị thông tin kỹ thuật và tồn sản phẩm; kiểm tra đủ tồn trước khi xác nhận đơn; tự sinh Serial khi nhập hàng theo serial và chuyển tồn cũ chưa có serial; tự phân bổ/kiểm tra serial giao (đủ số lượng, đúng sản phẩm, không trùng, còn tồn); tự ghi khách hàng, ngày giao và hạn bảo hành; gợi ý combo, thêm dòng quà khi xác nhận và lưu rule combo trên dòng bán; serial thực giao liên kết về đúng dòng bán; có lịch sử mua hàng và seed demo đơn bán. | Kiểm thử tự động các luồng xác nhận đơn, quà combo và giao serial đã chạy. Cần UAT thao tác báo giá/giao hàng, giao một phần và điều chỉnh đơn theo quy trình cửa hàng. | Chưa xác nhận quy tắc thay đổi/hủy quà sau khi đã xác nhận đơn và tình huống giao hàng từng phần. Cần hoàn thiện/kiểm chứng việc áp dụng giới hạn giá trị quà từ CRM. |
| **`custom_warranty` — Bảo hành, sửa chữa, đổi mới 1-1** (`18.0.1.14.0` trong manifest) | Tra cứu khách hàng/sản phẩm/ngày mua/hạn bảo hành qua serial và số điện thoại; trạng thái sửa chữa; quyết định miễn phí/tính phí theo thời hạn và nguyên nhân, có lý do/người/thời điểm xác nhận; checklist màn hình, bàn phím, pin/sạc, phụ kiện, ghi chú và ảnh; phân công kỹ thuật viên; ngày hẹn/SLA, cảnh báo quá hạn và scheduled action; in biên nhận PDF; policy đổi 1-1 theo nhóm hàng/hạn/checklist; chờ serial thay thế; quyền duyệt đổi cho quản lý kho; luân chuyển kho có rollback; chuyển phiếu đổi chưa duyệt sang sửa chữa có audit; lịch sử serial gốc/thay thế và báo cáo hậu mãi dạng biểu đồ/pivot. | Checklist/SLA và view phiếu đã được nạp trong database demo; tiếp tục UAT theo các nhóm tiếp nhận, kỹ thuật viên và quản lý. Kiểm tra nghiệp vụ thời gian xử lý và báo cáo bằng dữ liệu thực tế. | Chưa có các trạng thái dịch vụ như gửi hãng/chờ khách/bàn giao; quyết định bảo hành hiện phân loại miễn phí/tính phí nhưng chưa tạo hóa đơn/thu tiền; chưa tự tạo đơn mua/backorder khi thiếu serial thay thế; chưa có quy tắc nhận, giữ hoặc định giá phụ kiện/hộp thiếu khi đổi. Không hỗ trợ trả hàng/hoàn tiền theo chính sách phạm vi hiện tại. |

## 3. Luồng tích hợp toàn hệ thống đã có

### 3.1 Danh mục và combo → đơn bán

- Sản phẩm có thuộc tính kỹ thuật, nhóm hàng và chính sách bảo hành/đổi.
- Combo được cấu hình theo tổng tiền đơn và sản phẩm quà; tồn serial phụ kiện
  khả dụng được tổng hợp để xem số combo có thể cung cấp.
- Khi xác nhận đơn, hệ thống chọn combo phù hợp và thêm các dòng quà vào đơn.
- Dòng quà giữ thông tin rule combo; serial giao liên kết với dòng bán, cho
  phép tra lại nguồn gốc khuyến mại từ serial/hồ sơ hậu mãi.

### 3.2 Nhập hàng → tồn kho/Serial → giao hàng

- Serial được tạo khi hoàn tất nhập hàng theo số sê-ri duy nhất.
- Có thao tác chuyển tồn serial cũ chưa định danh thành Serial Number.
- Trước khi xác nhận đơn, hệ thống kiểm tra tồn khả dụng theo kho.
- Khi giao, hệ thống phân bổ và xác thực serial thực giao.
- Sau giao thành công, serial được liên kết với khách hàng, đơn/dòng bán, phiếu
  giao, ngày bán và thời hạn bảo hành tính theo cấu hình sản phẩm.

### 3.3 Bán hàng → bảo hành/sửa chữa/đổi mới

- Phiếu hậu mãi lấy thông tin sản phẩm và quyền lợi bảo hành từ serial đã bán.
- Sửa chữa theo trạng thái; đổi mới 1-1 có điều kiện riêng và dịch chuyển tồn
  kho; lịch sử serial và các phiếu hậu mãi được liên kết để truy vết.
- Báo cáo hậu mãi cho phép tổng hợp phiếu theo tháng, loại, trạng thái, nguyên
  nhân và kỹ thuật viên/thời gian xử lý.

## 4. Dữ liệu, tích hợp và vận hành

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Odoo 18 + PostgreSQL bằng Docker Compose | Đã cấu hình và chạy trong môi trường phát triển | `custom_addons/` được mount vào container Odoo; dữ liệu lưu ở PostgreSQL volume. |
| Kết nối XML-RPC tới Odoo | Đã có script | `scripts/connect_odoo.py`; cần dùng thông tin môi trường cục bộ. |
| Xem trước dữ liệu nguồn | Đã có script | `scripts/preview_laptop_erp.py`; hỗ trợ kiểm tra/mapping trước khi ghi. |
| Nhập `laptop_erp` vào Odoo | Đã có script dry-run/apply | `scripts/import_laptop_erp.py` ghi qua Odoo XML-RPC/ORM; cần xác nhận dry-run và kết quả đồng bộ trên database nguồn/đích được nhóm chọn. |
| Tạo dữ liệu mẫu trong PostgreSQL nguồn | Đã có script có kiểm soát backup | `scripts/seed_laptop_erp_demo.py`; thao tác apply yêu cầu backup hợp lệ và xác nhận rõ ràng. |
| Seed luồng bán hàng | Đã có seed trong `custom_sales/demo/` | Có ví dụ tạo đơn/serial demo; kiểm tra sản phẩm, kho và database đích trước khi chạy. |
| Seed hậu mãi | Đã có XML demo trong `custom_warranty/demo/` | Nạp khi cài addon với demo data bật; không tự nạp lại bằng thao tác upgrade thông thường. |
| Kiểm thử tự động CRM riêng | Chưa có | CRM hiện được kiểm chứng gián tiếp qua một phần test của Sales; cần thêm test độc lập. |

## 5. Kiểm thử và tình trạng triển khai

- Lần chạy tích hợp gần nhất trên Odoo 18/database `erp_nhom5_demo`: **31
  post-tests, 0 thất bại, 0 lỗi**. Runner thực thi test của `custom_sales` và
  `custom_warranty`; không có suite riêng cho `custom_crm`.
- Đã xác nhận `custom_crm`, `custom_sales`, `custom_warranty` đều ở trạng thái
  installed trên database thử nghiệm tại thời điểm kiểm tra; view checklist và
  các trường SLA đã được nạp.
- Database chính `erp_nhom5` chưa được nâng cấp trong lượt kiểm chứng này.
  Cần sao lưu và có xác nhận trước khi áp dụng thay đổi lên database chính.
- Workspace có các sửa đổi local chưa commit để tương thích Odoo 18 và sửa lỗi
  view/test. Vì vậy, trạng thái đã chạy trên database demo chưa đồng nghĩa các
  sửa đổi đó đã có trên `origin/main` hoặc đã phát hành.
- Log nâng cấp có cảnh báo về XML ID cũ `custom_sales.menu_sale_shared_products`
  và `action_sale_shared_products`; không làm lượt nâng cấp thất bại nhưng nên
  rà soát phần cleanup menu ở lần dọn tiếp theo.

## 6. Công việc còn lại của toàn nhóm

| Ưu tiên | Công việc | Phối hợp | Điều kiện hoàn tất |
|---|---|---|---|
| **P0** | Review, kiểm thử và đưa các sửa local tương thích Odoo 18 lên nhánh Git thống nhất | Nhóm phát triển | Cài/nâng cấp thành công từ source trên Git; test hồi quy đạt. |
| **P0** | UAT toàn quy trình: sản phẩm/combo → nhập Serial → báo giá/đơn → giao → hậu mãi; kiểm tra từng vai trò | Sales, CRM, Inventory, Hậu mãi | Người dùng chạy được kịch bản trên database demo và xác nhận kết quả. |
| **P1** | Chốt và thực thi giới hạn giá trị quà combo | CRM + Sales | Thống nhất giá tham chiếu, ngưỡng, xử lý vượt mức; bổ sung test biên. |
| **P1** | Chốt quy tắc xử lý phụ kiện/hộp thiếu trong đổi 1-1 | Hậu mãi + cửa hàng | Có quy trình nhận/giữ/bổ sung được duyệt; không tự suy diễn khoản tiền. |
| **P1** | Chốt luồng thiếu serial thay thế: nhà cung cấp, mua hàng, kho nhận, backorder/thông báo | Sales/Inventory + mua hàng | Quy trình được thống nhất và có test tích hợp. |
| **P1** | Kiểm chứng nhập dữ liệu nguồn trên database mục tiêu | Nhóm dữ liệu + quản trị Odoo | Backup phù hợp, dry-run được duyệt, apply và đối soát số lượng/bản ghi. |
| **P2** | Bổ sung test riêng cho CRM và kiểm thử giao diện/phân quyền theo vai trò cho toàn hệ thống | Nhóm phát triển | Có test cho CRUD combo/tồn, role, các luồng giao/hủy và kết quả UAT. |
| **P2** | Mở rộng trạng thái dịch vụ, SLA theo loại dịch vụ và tích hợp hóa đơn nếu cần | Hậu mãi + cửa hàng/kế toán | Quy trình và dữ liệu đầu vào được thống nhất trước khi phát triển. |

## 7. Nội dung ngắn để trình bày trong họp tuần

> Toàn repo hiện có ba addon tùy chỉnh: CRM sản phẩm/combo, Sales/Serial và
> Bảo hành–Sửa chữa–Đổi mới 1-1, tích hợp với các ứng dụng chuẩn Sales và
> Inventory của Odoo 18. Nhóm đã triển khai luồng liên kết từ cấu hình sản phẩm,
> tồn kho/Serial, bán hàng, giao hàng đến tra cứu hậu mãi; đồng thời có script
> nhập dữ liệu nguồn và seed demo. Trên database thử nghiệm, cả ba addon đã
> được cài và lượt kiểm thử tích hợp gần nhất đạt 31 post-tests, không lỗi hoặc
> thất bại. Việc tiếp theo của toàn nhóm là UAT xuyên module, kiểm chứng nhập dữ
> liệu thực, hoàn thiện giới hạn giá trị quà combo và thống nhất nghiệp vụ mua
> bù/thiếu phụ kiện. Các sửa tương thích Odoo 18 còn ở local cần review và đưa
> lên Git trước khi nâng cấp database chính.
