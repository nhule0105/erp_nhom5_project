# Đồ án ERP - Nhóm 5

Các module tùy chỉnh cho Odoo 18 nằm trong `custom_addons/`:

- `custom_warranty`: thêm thông tin khách hàng, trạng thái và ngày bảo hành cho
  serial; quản lý phiếu sửa chữa/bảo hành và đổi mới 1-1 với Kanban, kiểm tra
  điều kiện tiếp nhận, luân chuyển tồn kho và phân quyền quản lý kho. Thông tin
  lỗi, trạng thái và ngày kết thúc từ hệ thống nguồn cũng được lưu trên phiếu.
- `custom_crm`: bổ sung quy trình CRM tạo combo sản phẩm và quản lý sản phẩm
  bán hàng.
- `custom_sales`: kiểm tra tồn kho khi xác nhận đơn, kiểm tra serial thực giao,
  tự ghi nhận khách mua/ngày bán/hạn bảo hành theo số tháng cấu hình trên sản
  phẩm và tra cứu đơn bán từ serial.

## Cài đặt và kết nối PostgreSQL

Odoo sử dụng PostgreSQL trong Docker Compose làm cơ sở dữ liệu đích
`erp_tramy`. Database nguồn `laptop_erp` nằm trên PostgreSQL 18 cài trên
Windows; hai database này ở hai PostgreSQL server khác nhau.

1. Tạo file cấu hình local từ mẫu và thay các mật khẩu mẫu bằng mật khẩu riêng:

   ```powershell
   Copy-Item .env.example .env
   ```

   `POSTGRES_PASSWORD` là mật khẩu kết nối PostgreSQL; `ODOO_MASTER_PASSWORD`
   là mật khẩu quản lý database của Odoo. Không commit file `.env`.
2. Khởi động Odoo và PostgreSQL:

   ```powershell
   docker compose up -d
   ```

   PostgreSQL cần ở trạng thái healthy trước khi Odoo khởi động. Thư mục
   `custom_addons` đã được mount vào `/mnt/extra-addons`.
3. Mở `http://localhost:8069`, đăng nhập vào database đích `erp_tramy`.
   PostgreSQL lưu dữ liệu trong volume `odoo-db-data`, nên dữ liệu vẫn còn
   sau khi container được khởi động lại.
4. Trong Odoo, bật chế độ nhà phát triển, cập nhật danh sách ứng dụng, sau đó
   cài **Tự động hóa Bán hàng & Serial Number**. Module này tự phụ thuộc vào
   **Quản lý Bảo hành & Đổi trả**, **Sales** và **Inventory**.
   Khi tạo cơ sở dữ liệu với dữ liệu demo, module bảo hành sẽ nạp sẵn khách
   hàng, sản phẩm/serial và các phiếu bảo hành/đổi trả mẫu ở nhiều trạng thái.
5. Để dùng CRM sản phẩm, cập nhật danh sách ứng dụng rồi cài module
   **Danh mục Sản phẩm CRM**. Module này phụ thuộc vào **Inventory** và
   **Quản lý Bảo hành & Đổi trả**.
6. Để kiểm tra kết nối XML-RPC tới database Odoo `erp_tramy`, đặt mật khẩu đăng
   nhập Odoo đã tạo ở bước 3 rồi chạy. Mặc định tài khoản là `admin`; nếu chọn
   login khác, hãy sửa `ODOO_USERNAME` thành login đó:

   ```powershell
   $env:ODOO_DB = "erp_tramy"
   $env:ODOO_USERNAME = "admin"
   $env:ODOO_PASSWORD = "<mật khẩu đăng nhập Odoo>"
   python scripts/connect_odoo.py
   ```

   Có thể đặt `ODOO_URL` nếu Odoo không chạy tại `http://localhost:8069`.

## Nhập dữ liệu nguồn laptop_erp vào Odoo

Script nhập đọc PostgreSQL nguồn và ghi dữ liệu qua Odoo XML-RPC/ORM, không
ghi SQL trực tiếp vào các bảng nghiệp vụ của Odoo. Các mã nguồn được giữ để
chạy lại an toàn: khách hàng dùng `ref`, sản phẩm dùng `default_code`, serial
dùng `ref`, đơn hàng dùng `client_order_ref` và phiếu bảo hành dùng `ticket_code`.

Trước lần nhập đầu tiên, cập nhật danh sách ứng dụng trong Odoo rồi nâng cấp
module **Custom Warranty - Đổi trả 1-1** để có các trường lưu mô tả, trạng thái
và ngày kết thúc từ hệ thống nguồn. Sau đó chạy thử chỉ đọc:

```powershell
python scripts\import_laptop_erp.py
```

Script hỏi login/mật khẩu Odoo và mật khẩu PostgreSQL cục bộ, không hiển thị
mật khẩu khi gõ. Không gửi mật khẩu qua chat. Chỉ sau khi xem kết quả dry-run,
có thể chạy lại với `--apply` để nhập dữ liệu. Đơn bán nhập ở trạng thái nháp
để không giả lập xác nhận/giao hàng; serial `in_stock` được đưa vào vị trí kho
chính của công ty Odoo, còn serial `sold`/`in_warranty` không được tự tạo tồn
kho. Vị trí nguồn được lưu riêng nếu bảng nguồn có cột vị trí.

### Thêm dữ liệu demo liên kết đầy đủ

Để tạo thêm dữ liệu giả lập ở PostgreSQL nguồn rồi đồng bộ qua Odoo, trước hết
giữ file backup `laptop_erp` và chạy dry-run:

```powershell
python scripts\seed_laptop_erp_demo.py --backup-file "$HOME\Documents\erp-backup\laptop_erp.backup"
```

Nếu phần xem trước hợp lệ, chạy thao tác ghi có kiểm tra backup và xác nhận
tường minh:

```powershell
python scripts\seed_laptop_erp_demo.py --apply --backup-file "$HOME\Documents\erp-backup\laptop_erp.backup"
```

Script thêm 10 khách hàng, 10 laptop, 20 serial, 10 đơn, 15 dòng đơn và 5
phiếu bảo hành trong một transaction PostgreSQL. Mọi bản ghi có tiền tố
`DEMO-ERP-20261023`; dữ liệu hiện có không bị sửa. Sau khi script xác nhận đã
commit thành công, chạy `python scripts\import_laptop_erp.py` để kiểm tra khô,
rồi `python scripts\import_laptop_erp.py --apply` để đồng bộ các dòng mới qua
Odoo ORM/API. Đơn hàng Odoo vẫn là báo giá nháp; không tự xác nhận giao hàng.

## Luồng sử dụng

1. Tạo sản phẩm có theo dõi tồn kho theo serial và nhập serial vào kho.
2. Tạo đơn bán, chọn khách hàng và sản phẩm; xác nhận đơn sau khi hệ thống kiểm
   tra đủ tồn kho khả dụng. Xử lý phiếu giao hàng và quét đúng serial thực tế.
   Sau khi giao, serial liên kết với khách hàng/đơn bán và được cập nhật ngày
   bán, hạn bảo hành.
3. Cấu hình thời hạn bảo hành theo tháng và thời hạn đổi mới theo ngày ở tab
   Kho của từng sản phẩm.
   Thời hạn đổi mới mặc định là 30 ngày nhưng có thể cấu hình theo sản phẩm.
4. Tạo phiếu trong menu **Hậu Mãi & Đổi Trả** bằng cách nhập serial hoặc số
   điện thoại khách hàng. Kỹ thuật viên theo dõi sửa chữa qua các giai đoạn
   **Mới tiếp nhận → Đang sửa → Chờ thay linh kiện → Đã xong**.
5. Quản lý kho có thể duyệt đổi mới 1-1 khi lỗi do nhà sản xuất, còn trong
   thời hạn đổi mới, đạt kiểm tra ngoại quan/bảo mật và serial thay thế cùng
   sản phẩm còn tồn kho nội bộ. Hệ thống ghi nhận các phiếu dịch chuyển kho,
   chuyển máy lỗi sang vị trí hàng lỗi, giao máy mới cho khách và giữ nguyên
   ngày bán/hạn bảo hành ban đầu.
6. Luồng **Trả hàng** độc lập chỉ nhập lại serial từ vị trí Khách hàng về kho
   nội bộ. Module không tạo hoàn tiền, hóa đơn điều chỉnh hoặc nghiệp vụ kế
   toán. Chính sách thời hạn đang cấu hình theo từng sản phẩm; không nên coi
   con số demo là chính sách áp dụng chung. Có thể đặt thời hạn mặc định ở
   **Nhóm sản phẩm**; nếu sản phẩm có cấu hình riêng thì cấu hình sản phẩm
   được ưu tiên.

## Nạp dữ liệu demo an toàn

Dữ liệu trong `custom_warranty/demo/` chỉ được nạp khi cài module với tùy chọn
**Load demonstration data**. Bộ demo có sẵn tồn kho 1 chiếc cho serial cũ ở
vị trí **Khách hàng** và serial mới ở vị trí **Kho nội bộ**, nên quản lý kho
có thể thử nút **Duyệt đổi mới 1-1**. Sau khi duyệt, hai giao dịch hoàn tất
được hiển thị ngay trên tab **Giao dịch kho** của phiếu.

Không bật dữ liệu demo hoặc chạy lại seed trên database production hiện tại.
Để thử an toàn, hãy dùng bản sao database thử nghiệm, bật **Load demonstration
data** khi cài `custom_warranty`, rồi kiểm tra các phiếu có mã bắt đầu bằng
`HM/`. Bộ demo có riêng phiếu đổi hàng 1:1 và phiếu trả hàng. Tài khoản thử
các nút duyệt phải thuộc nhóm **Inventory / Administrator**
(`stock.group_stock_manager`); không cần cấp quyền quản trị hệ thống.

## Custom phân hệ Bán hàng

- **S1.1 – Kiểm tra tồn khả dụng:** trước khi xác nhận, tổng hợp số lượng hàng
  lưu kho theo từng sản phẩm và từ chối đơn nếu tồn khả dụng tại kho xuất không
  đủ. Với sản phẩm theo serial, hệ thống còn yêu cầu đủ serial đang sẵn sàng bán.
  Trên báo giá không cần chọn serial. Serial thực tế được quét/chọn trên phiếu
  giao hàng, khi đã rõ thiết bị nào sẽ giao cho khách.
- **S1.2 – Kiểm tra serial khi giao:** trước khi xác nhận phiếu giao, yêu cầu
  đủ số lượng serial, đúng sản phẩm, không trùng và còn số lượng trong vị trí
  kho xuất.
- **S1.3 – Ghi nhận bảo hành:** sau khi giao thành công, cập nhật khách hàng,
  đơn bán, ngày bán, trạng thái serial và ngày hết hạn bảo hành.
- **S1.4 – Cấu hình thời hạn:** đặt số tháng bảo hành tại tab **Kho** trên sản
  phẩm. Hạn bảo hành được tính theo tháng lịch từ ngày giao hàng.
- **S1.5 – Tra cứu nguồn gốc:** mở serial trong Inventory để xem khách mua,
  đơn bán liên kết, ngày bán và hạn bảo hành; đơn bán cũng có tab serial đã giao
  và hồ sơ khách hàng có lịch sử mua hàng.

Kiểm thử nghiệp vụ ở `custom_sales/tests/` tạo dữ liệu đơn hàng, tồn kho và
serial trong transaction test của Odoo. Sau khi cập nhật code, nâng cấp cả
**Quản lý Bảo hành & Đổi trả** và **Quản lý Bán hàng Laptop** để nạp các field
và giao diện mới.

### Tạo 10 giao dịch demo cho custom Bán hàng

Sau khi nâng cấp hai module, có thể thêm 10 đơn demo đã giao cho sản phẩm
`XPS15`. Lệnh tạo một phiếu nhập đủ serial, 10 khách hàng và 10 đơn bán; số
serial nhập được cộng thêm phần nhu cầu của các đơn giao XPS15 đang chờ để
không dùng hàng đã được giữ chỗ. Mỗi đơn demo giao một serial và ghi nhận thời
hạn bảo hành đang cấu hình trên sản phẩm. Các đơn không được xuất hóa đơn và
có mã `DEMO-S1` để phân biệt. Chạy lại script không tạo bản sao; nếu bộ demo
đã tồn tại nhưng không hoàn chỉnh, script dừng thay vì tự sửa giao dịch:

```powershell
docker compose exec -T web sh -c 'odoo -d erp_tramy -u custom_warranty,custom_sales --stop-after-init --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"'
docker compose restart web
Get-Content .\custom_addons\custom_sales\demo\seed_sales_s1.py -Raw |
  docker compose exec -T web sh -c 'odoo shell -d erp_tramy --no-http --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"'
```

Việc chạy script tạo các phiếu nhập/xuất và thay đổi tồn kho của `XPS15`.

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
