# Báo cáo phân tích nghiệp vụ thống nhất — ERP Nhóm 5

> Bản tổng hợp này chuẩn hóa nội dung từ `custom_addons/Báo cáo TH ERP nhóm 5.docx`,
> sơ đồ luồng bảo hành/đổi mới và tình trạng mã nguồn hiện tại. “Đã triển khai”
> nghĩa là có logic/giao diện trong addon; không khẳng định đã được UAT trên
> database cửa hàng. Những điểm chưa thống nhất được nêu riêng, không suy đoán
> thành quy tắc đã được cửa hàng phê duyệt.

## 1. Thông tin đề tài

**Tên đề tài:** Ứng dụng Odoo ERP trong quản lý kinh doanh Laptop  
**Nền tảng:** Odoo 18 Community, PostgreSQL, Docker  
**Mục tiêu:** quản lý vòng đời laptop và phụ kiện theo Serial Number (S/N), kết
nối dữ liệu danh mục, kho, bán hàng và hậu mãi; giảm sai sót khi xuất hàng và
tra cứu lịch sử bảo hành/đổi mới.

### 1.1 Bài toán

Theo dõi thiết bị giá trị cao chỉ bằng số lượng tổng không đủ để xác định máy
nào đang ở kho, đã bán cho ai hoặc đang được tiếp nhận sửa chữa. Quy trình rời
rạc cũng làm khó việc kiểm tra hạn bảo hành và đối soát khi đổi máy. Hệ thống
được đề xuất để tập trung dữ liệu theo từng serial và nối các nghiệp vụ:

**Danh mục sản phẩm → Nhập kho/serial → Bán hàng/giao hàng → Bảo hành, sửa chữa
hoặc đổi mới 1-1.**

### 1.2 Phạm vi

- **Danh mục và combo:** dữ liệu sản phẩm, thuộc tính kỹ thuật, nhóm hàng và
  quy tắc combo/khuyến mại.
- **Bán hàng và khách hàng:** đơn bán, kiểm tra tồn, serial thực giao, ngày bán,
  hạn bảo hành và lịch sử khách hàng.
- **Kho/Inventory:** quản lý tồn và di chuyển serial thông qua nghiệp vụ kho
  Odoo.
- **Hậu mãi:** phiếu tiếp nhận, tra cứu bảo hành, sửa chữa, đổi mới 1-1, lịch sử
  serial, báo cáo và biên nhận.
- **Ngoài phạm vi đã xác nhận:** trả hàng/hoàn tiền theo nhu cầu và kế toán/thu
  chi hoàn chỉnh. Các quyết định miễn phí/tính phí sửa chữa được ghi nhận trên
  phiếu nhưng không tự tạo hóa đơn hoặc thanh toán.

### 1.3 Bản đồ module hiện có

| Addon | Vai trò nghiệp vụ | Tình trạng theo rà soát mã nguồn |
|---|---|---|
| `custom_crm` | Danh mục sản phẩm, thuộc tính kỹ thuật, dữ liệu combo và chuyển đổi tồn chưa quản lý serial | Có model/view và logic combo; đây không phải quy trình CRM lead/opportunity. Một số hành động tạo/bóc combo chưa điều khiển luân chuyển kho thành phần. |
| `custom_sales` | Khách hàng, đơn bán, kiểm tra tồn và gán serial khi giao | Có mở rộng Sales/Picking, kiểm tra serial, lịch sử và liên kết serial thực giao tới dòng bán. Script nhập dữ liệu legacy không biến đơn nháp thành giao dịch đã giao. |
| `custom_warranty` | Phiếu hậu mãi, policy bảo hành/đổi, sửa chữa, luân chuyển kho đổi | Có backend, giao diện, security, test, dữ liệu demo XML và báo cáo. |
| Ứng dụng Odoo chuẩn | Sales, Inventory/Stock, sản phẩm, liên hệ | Được cấu hình/tích hợp; không phải addon do nhóm tự viết. |

## 2. Vai trò nghiệp vụ và quyền hạn

Sơ đồ thống nhất hai vai trò ở mức nghiệp vụ. Nhóm kỹ thuật viên là phân công
nội bộ thuộc vai trò Nhân viên, không phải vai trò nghiệp vụ thứ ba.

| Vai trò thống nhất | Trách nhiệm nghiệp vụ | Ánh xạ hiện có trong Odoo / giới hạn |
|---|---|---|
| **Nhân viên** | Tra cứu khách hàng/serial; tiếp nhận máy; ghi lỗi và checklist; phân loại ban đầu; theo dõi phiếu; thực hiện công việc sửa chữa được giao; lập và theo dõi yêu cầu đổi; bán hàng theo quyền được cấp. | Odoo hiện có nhóm stock user và nhóm warranty technician. Technician bị giới hạn phiếu theo người được giao. Stock user có quyền đọc/tạo/sửa phiếu, nhưng không có rule chung chỉ giới hạn phiếu do chính họ tạo. Các nút workflow chủ yếu được điều kiện theo trạng thái, không phải mỗi nút đều có kiểm tra nhóm. |
| **Chủ cửa hàng (quản lý/thủ kho)** | Xác nhận hướng xử lý; duyệt đổi; chọn serial thay thế; điều phối kho và giám sát kết quả. | Action duyệt đổi kiểm tra `stock.group_stock_manager`; nhóm warranty manager có quyền quản lý và xem phiếu. Cần cấp đúng nhóm cho tài khoản chủ cửa hàng và thử bằng tài khoản thực tế. |

**Nguyên tắc phân quyền:** nhân viên không tự duyệt đổi, xác nhận miễn phí/tính
phí hoặc tự điều chỉnh giao
dịch kho đổi. Quản lý/thủ kho chịu trách nhiệm duyệt sau khi hồ sơ và serial
thay thế hợp lệ. Không xóa phiếu/giao dịch đã phát sinh để sửa lịch sử; dùng
workflow/audit phù hợp.

## 3. Quy tắc nghiệp vụ hậu mãi

### 3.1 Bảo hành và sửa chữa

1. Tiếp nhận serial cùng thông tin khách và mô tả lỗi; hệ thống tra cứu sản
   phẩm, chủ sở hữu, ngày mua và hạn bảo hành nếu dữ liệu serial đã được ghi
   nhận đầy đủ.
2. Nhân viên kiểm tra ngoại quan, phụ kiện, dấu hiệu vào nước/chập cháy và tình
   trạng bảo mật; lưu ghi chú/ảnh cần thiết.
3. Ghi nhận nguyên nhân và quyết định dịch vụ. Code hỗ trợ xác nhận quyết định
   miễn phí/tính phí theo thời hạn và nguyên nhân, kèm lý do/người/thời điểm.
   Chỉ Chủ cửa hàng/quản lý kho được xác nhận; audit không sửa trực tiếp được.
   Trường hợp thiếu dữ liệu phải xác minh, không tự kết luận.
4. Theo dõi sửa chữa qua các trạng thái hiện có: **Mới tiếp nhận → Đang sửa →
   Chờ linh kiện → Đang sửa → Hoàn tất**. Mô tả lỗi phải có trước khi bắt đầu;
   không thể hoàn tất nếu thiếu kết quả sửa chữa hoặc quyết định miễn phí/tính
   phí đã được chủ cửa hàng xác nhận; serial được cập nhật theo quá trình.
5. Người phụ trách, SLA/ngày hẹn, thời gian xử lý, cảnh báo quá hạn và biên nhận
   PDF được hỗ trợ trong code. Cần UAT lịch cron, ngày nghỉ và nội dung biên
   nhận tại môi trường sử dụng.

**Giới hạn:** ghi quyết định tính phí không đồng nghĩa đã thu tiền hoặc lập hóa
đơn. Gửi hãng, trạng thái hãng đang xử lý, chờ khách và bàn giao chưa phải các
workflow riêng được xác nhận trong code.

### 3.2 Đổi mới 1-1

1. Nhân viên lập phiếu đổi, chọn serial cũ, ghi mô tả lỗi, nguyên nhân và
   checklist tiếp nhận.
2. Code kiểm tra serial cũ/khách/ngày mua, thời hạn cấu hình, lỗi nhà sản xuất,
   checklist và serial mới cùng sản phẩm, còn khả dụng. Nếu chưa có serial thay
   thế, phiếu có thể ở trạng thái chờ serial; hệ thống chưa tự tạo đơn mua hay
   backorder.
3. Chủ cửa hàng/quản lý kho kiểm tra hồ sơ và duyệt. Backend chặn người không
   thuộc nhóm quản lý kho, kể cả khi gọi action trực tiếp.
4. Khi duyệt, hệ thống tạo giao dịch kho trong cùng luồng: serial cũ được đưa
   khỏi vị trí khách sang vị trí lỗi/điều chỉnh; serial mới được chuyển từ kho
   nội bộ cho khách. Giao dịch có cơ chế rollback nếu bước xử lý thất bại.
5. Serial mới kế thừa khách hàng, ngày mua, hạn bảo hành và liên kết bán hàng
   từ serial cũ; chuỗi serial và phiếu hậu mãi được lưu để truy xuất.

**Chính sách trong phạm vi:** chỉ đổi 1-1 khi đủ điều kiện; không tạo nghiệp vụ
trả hàng/hoàn tiền sau mua. Điều kiện đổi 0–30 ngày là điều kiện đổi do lỗi,
không phải thời hạn hoàn tiền.

Sản phẩm phải được phân nhóm chính sách đổi tại sản phẩm hoặc danh mục trước
khi tiếp nhận đổi: thiết bị mới/đã qua sử dụng tối đa 30 ngày; phụ kiện theo
thời hạn hãng đã cấu hình, tối đa 365 ngày. Sản phẩm chưa được phân nhóm không
đủ điều kiện đổi, tránh tự áp hạn thiết bị cho phụ kiện hoặc hàng chưa rõ loại.
Khi cập nhật module trên dữ liệu sẵn có, cửa hàng cần rà soát và cấu hình các
sản phẩm/danh mục trước khi áp dụng quy trình đổi.

### 3.3 Luồng từ chối đổi

Nếu không đủ điều kiện đổi, nhân viên ghi nhận lý do. Phiếu đổi chưa duyệt có
thể được chuyển sang phiếu sửa chữa với lý do và thời điểm chuyển được lưu.
Tiếp nhận sửa chữa không có nghĩa tự động chấp nhận miễn phí: phải xác nhận
nguyên nhân, hạn bảo hành và quyết định dịch vụ theo hồ sơ.

### 3.4 Ngoại lệ phụ kiện và combo

- **Thiếu hộp/phụ kiện:** tài liệu gốc đề cập xử lý bằng hiện vật nhưng chưa
  thống nhất cách cửa hàng nhận, giữ, định giá hoặc giao bù. Chưa có dòng phụ
  kiện và giao dịch kho đủ để tự động hóa ngoại lệ; cần chốt quy tắc trước khi
  triển khai.
- **Combo:** serial giao và dòng bán/rule combo có thể truy vết ở mức dữ liệu.
  Tuy nhiên, code combo hiện không thực hiện đầy đủ việc tiêu thụ/hoàn nhập tồn
  thành phần như một workflow bundle. Cần phân biệt liên kết nguồn dữ liệu với
  nghiệp vụ kho combo hoàn chỉnh.

## 4. Quy trình tổng thể theo hai vai trò

### 4.1 Bán hàng và ghi nhận serial

1. **Nhân viên:** chọn khách hàng, sản phẩm và tạo đơn bán.
2. **Hệ thống:** kiểm tra tồn; tạo giao hàng/picking theo Odoo.
3. **Nhân viên/thủ kho theo phân quyền thực tế:** xác định serial thực giao.
4. **Hệ thống:** kiểm tra serial theo sản phẩm, tình trạng khả dụng và không
   trùng; khi giao hàng hoàn tất, liên kết serial thực giao với khách, dòng bán,
   ngày bán và dữ liệu bảo hành theo code.
5. **Chủ cửa hàng:** giám sát tồn và chứng từ kho khi cần.

**Điểm cần lưu ý:** không coi đơn nháp/quotation từ import lịch sử là giao dịch
đã bán hoặc đã giao. Dữ liệu bảo hành nguồn cần được ánh xạ sang trường serial
đang dùng cho trạng thái bảo hành để có hiệu lực trên phiếu hậu mãi.

### 4.2 Tiếp nhận, sửa chữa và bảo hành

| Bước | Nhân viên | Hệ thống | Chủ cửa hàng |
|---|---|---|---|
| Tra cứu/tiếp nhận | Nhập serial hoặc điện thoại, mô tả lỗi, checklist và bằng chứng | Hiển thị dữ liệu serial/bán/bảo hành có sẵn; tạo phiếu | — |
| Phân loại | Ghi nhận nguyên nhân/đề xuất xử lý | Tính tình trạng hạn; cung cấp action xác nhận chính sách | Xác nhận ngoại lệ theo quy trình cửa hàng |
| Sửa chữa | Thực hiện, cập nhật trạng thái và kết quả | Theo dõi trạng thái, kỹ thuật viên, thời gian/SLA; không cho hoàn tất thiếu kết quả | Theo dõi tiến độ |
| Trả máy | Ghi kết quả và bàn giao theo quy trình cửa hàng | Đóng phiếu; serial trở về trạng thái phù hợp | Giám sát |

### 4.3 Đổi mới 1-1

| Bước | Nhân viên | Hệ thống | Chủ cửa hàng/quản lý-thủ kho |
|---|---|---|---|
| Yêu cầu đổi | Tra cứu serial, tiếp nhận máy, ghi lỗi/checklist | Nạp thông tin serial và policy từ sản phẩm/danh mục | — |
| Kiểm tra | Bổ sung nguyên nhân và hồ sơ; nếu thiếu hàng đánh dấu chờ serial | Kiểm tra thời hạn, lỗi NSX, checklist và serial thay thế | — |
| Duyệt | Theo dõi phiếu, không tự duyệt | Chặn quyền duyệt nếu không phải stock manager | Kiểm tra và duyệt/từ chối theo quyền |
| Luân chuyển | Bàn giao máy lỗi/máy mới | Tạo hai dịch chuyển kho; rollback nếu giao dịch lỗi; bảo lưu ngày mua/hạn BH | Xác nhận serial và thực tế kho |
| Kết thúc | Tra cứu lịch sử sau đổi | Ghi chuỗi serial và phiếu hậu mãi | Giám sát báo cáo |

### 4.4 Nhánh không đủ điều kiện đổi

Nhân viên ghi lý do và chuyển phiếu chưa duyệt sang sửa chữa nếu phù hợp. Hệ
thống lưu lịch sử chuyển; quy trình sửa tiếp tục theo mục 4.2. Không chuyển
thành hoàn tiền hoặc nhập hàng lại như hàng bán được.

## 5. Yêu cầu chức năng và trạng thái triển khai

| Mã | Yêu cầu | Trạng thái | Căn cứ triển khai / giới hạn |
|---|---|---|---|
| FR-01 | Lưu danh mục sản phẩm và thuộc tính kỹ thuật | Đã làm một phần | Có model/view sản phẩm; phạm vi thực tế không nên diễn giải thành đủ mọi thuộc tính ở đề xuất ban đầu. |
| FR-02 | Quản lý serial/tồn kho theo từng thiết bị | Đã làm | Dùng Inventory/Stock Odoo và các trường mở rộng serial; có rủi ro hai trường trạng thái serial (`lifecycle_status` và `x_custom_status`) có thể lệch nhau, cần xử lý/kiểm chứng trước khi coi là nguồn trạng thái duy nhất. |
| FR-03 | Bán hàng và kiểm tra serial thực giao | Đã làm | Có kiểm tra tồn/serial và lưu serial giao về dòng bán. Cần UAT giao một phần và điều chỉnh đơn. |
| FR-04 | Tra cứu khách, sản phẩm, ngày mua và hạn bảo hành từ serial | Đã làm một phần | Hoạt động khi serial có dữ liệu đúng; dữ liệu ngày hết hạn nhập legacy hiện có thể chỉ nằm ở `source_end_date`, không tự động trở thành hạn bảo hành vận hành trên serial. |
| FR-05 | Tạo phiếu hậu mãi và theo dõi sửa chữa | Đã làm | Phiếu dùng chung; mô tả lỗi cần trước khi bắt đầu; trạng thái mới nhận/đang sửa/chờ linh kiện/hoàn tất. Chưa có các trạng thái hãng/chờ khách/bàn giao riêng. |
| FR-06 | Quyết định miễn phí/tính phí | Đã làm | Chỉ quản lý kho xác nhận; lý do và người/thời điểm được lưu, không sửa audit trực tiếp; quyết định phải được xác nhận trước khi hoàn tất sửa chữa. Không tạo invoice/payment. |
| FR-07 | Checklist, ảnh và biên nhận | Đã làm một phần | Checklist, attachments và PDF receipt có; chữ ký là khu vực ký tay, không phải e-signature. |
| FR-08 | SLA, người phụ trách, cảnh báo quá hạn và báo cáo hậu mãi | Đã làm | Có trường/mốc xử lý/cron và graph/pivot; cần UAT scheduling, múi giờ và ngày nghỉ. |
| FR-09 | Đổi mới 1-1 có duyệt và di chuyển serial nguyên tử | Đã làm | Có kiểm tra policy, quyền quản lý kho, giao dịch move và rollback. |
| FR-10 | Chờ serial mới khi hết tồn | Đã làm một phần | Có trạng thái chờ/chọn serial; chưa tự tạo procurement/backorder. |
| FR-11 | Trả hàng/hoàn tiền | Không hỗ trợ theo phạm vi | Loại phiếu refund/return không được hỗ trợ; không có quy trình kế toán. |
| FR-12 | Combo có luân chuyển tồn thành phần hoàn chỉnh | Chưa làm đầy đủ | Có rule và một phần truy vết; action tạo/bóc combo không tiêu thụ/hoàn nhập thành phần bằng stock workflow. |
| FR-13 | Xử lý hộp/phụ kiện thiếu bằng hiện vật | Chưa làm | Chưa chốt policy cửa hàng và chưa có dòng/giao dịch phụ kiện trên phiếu đổi. |
| FR-14 | Phân quyền vừa đúng hai actor nghiệp vụ | Đã làm một phần | Có stock user/manager và nhóm warranty technician/manager; cần kiểm tra quyền stock user và ánh xạ tài khoản tại môi trường triển khai. |

## 6. Các điểm bất đồng cần thống nhất

| Chủ đề | Nội dung trong tài liệu/sơ đồ | Code hiện tại | Cách ghi thống nhất và việc cần làm |
|---|---|---|---|
| Hạn đổi | Sơ đồ và pseudocode dùng 30 ngày; DOCX có bảng phân biệt thiết bị mới/cũ, 0–30 và 31–365 ngày; phụ kiện có thời hạn theo hãng. | Thời hạn cấu hình trên sản phẩm/danh mục; mặc định thiết bị tối đa 30 ngày, phụ kiện cần cấu hình. Rule đổi yêu cầu lỗi NSX, checklist đạt và cùng sản phẩm. | Không gộp thành “mọi mặt hàng đổi 30 ngày”. Cửa hàng/nhóm cần xác nhận policy cuối cùng theo nhóm hàng, hàng mới/cũ và hãng phụ kiện; cập nhật cấu hình và báo cáo theo quyết định đó. |
| Sau 30 ngày | DOCX mô tả thiết bị mới trong thời gian bảo hành có thể chuyển sang bảo hành hãng; dùng chung luồng sơ đồ để tiếp nhận sửa chữa. | Có sửa chữa nội bộ và tính phí/miễn phí; chưa có workflow gửi hãng/nhận lại từ hãng. | Có thể tiếp nhận/sửa theo chức năng đang có; không tuyên bố hệ thống tự gửi hãng hoặc quản lý trạng thái hãng. |
| Đổi và hoàn tiền | Bảng business rules loại trừ đổi/trả theo nhu cầu; sơ đồ là đổi 1-1. | Không có luồng trả hàng/hoàn tiền. | Thống nhất chỉ đổi 1-1 theo điều kiện; không tự đặt thời hạn hoàn tiền. |
| Hai vai trò | Sơ đồ dùng Nhân viên và Chủ cửa hàng (quản lý/thủ kho). | ACL dùng nhiều nhóm Odoo, kỹ thuật viên có record rule; stock user chưa giới hạn phiếu theo người tạo. | Giữ hai actor khi mô tả nghiệp vụ; phụ lục kỹ thuật ghi nhóm Odoo chi tiết, cấu hình account và quyền riêng trước UAT. |
| Combo | DOCX yêu cầu đổi đúng món lỗi và quản lý thành phần serial độc lập. | Có rule/link dòng bán và serial; chưa có workflow tiêu thụ/hoàn nhập đủ thành phần. | Ghi tính năng truy vết đã có, không tuyên bố xử lý kho bundle hoàn chỉnh. |
| Hộp/phụ kiện thiếu | DOCX đề xuất cấn trừ bằng hiện vật. | Chưa có policy chi tiết hoặc dòng giao dịch phụ kiện. | Chờ cửa hàng thống nhất ai giữ/cấp bù, điều kiện và chứng từ; không tạo xử lý tiền khi chưa có chính sách. |
| Trạng thái serial | Các addon có trường trạng thái serial riêng. | `lifecycle_status` và `x_custom_status` có thể được cập nhật khác nhau, ảnh hưởng chọn serial. | Cần chọn nguồn trạng thái chuẩn và đồng bộ/migration trước khi xem là dữ liệu kiểm soát duy nhất. |
| Nhập lịch sử | Dữ liệu legacy có thể được nhập để tra cứu. | Script có thể để đơn ở trạng thái quotation và lưu ngày hết hạn nguồn ở trường riêng. | Phân biệt dữ liệu lịch sử với giao dịch bán/giao đã hoàn tất; kiểm tra mapping trước khi dùng cho tính bảo hành. |

## 7. Yêu cầu phi chức năng và dữ liệu

- **Toàn vẹn kho:** mỗi thiết bị theo dõi bằng serial; giao dịch đổi phải thu hồi
  serial lỗi và cấp serial thay thế nhất quán, rollback nếu lỗi.
- **Truy xuất:** lưu quan hệ khách hàng, sản phẩm, dòng bán, serial gốc/thay thế
  và các phiếu hậu mãi liên quan.
- **Bảo vệ thông tin khách:** checklist bảo mật chỉ ghi nhận trạng thái đã đăng
  xuất/đã xóa mật khẩu; không lưu mật khẩu, PIN hay token tài khoản.
- **Phân quyền:** duyệt đổi thuộc quản lý/thủ kho; kỹ thuật viên chỉ xử lý phiếu
  được giao theo rule hiện có.
- **Bằng chứng:** lưu checklist/ảnh và biên nhận; tuân thủ quy trình sao lưu
  database trước demo hoặc nâng cấp.
- **Môi trường:** Odoo 18 Community và PostgreSQL qua Docker; demo/UAT nên dùng
  database tách biệt, không thao tác trên database nghiệp vụ.

## 8. Kế hoạch hoàn thiện ưu tiên

| Ưu tiên | Công việc | Phụ trách đề xuất | Tiêu chí hoàn tất |
|---|---|---|---|
| P0 | Chốt ma trận hạn đổi theo thiết bị mới/cũ/phụ kiện; thống nhất 30 ngày và các nhánh sau thời hạn | Chủ cửa hàng/nhóm nghiệp vụ; Như cập nhật policy đổi, Châu rà nhánh sửa chữa | Có bảng chính sách được duyệt, cấu hình tương ứng, test các nhánh biên. |
| P0 | Rà soát nguồn trạng thái serial kép và mapping hạn bảo hành khi nhập legacy | Nhóm kỹ thuật; Như phối hợp Sales/CRM | Một nguồn trạng thái vận hành nhất quán; serial import tra cứu đúng hạn bảo hành; có test/regression. |
| P1 | Cấu hình và UAT phân quyền hai vai trò trên database sạch | Như và Châu phối hợp; Chủ cửa hàng kiểm tra | Nhân viên không duyệt đổi; quản lý duyệt được; technician chỉ thấy phiếu được giao; các nút workflow đúng quyền. |
| P1 | Hoàn thiện tình huống gửi hãng/chờ khách/bàn giao nếu cửa hàng cần | Châu | Có trạng thái, người phụ trách, dấu thời gian và test chuyển trạng thái. |
| P1 | Chốt và triển khai xử lý hộp/phụ kiện thiếu bằng hiện vật | Như, cần chủ cửa hàng phê duyệt quy tắc | Dòng phụ kiện và stock moves có thể kiểm tra/đối soát, không tạo hoàn tiền ngoài policy. |
| P1 | Hoàn thiện kho combo/BoM và kiểm thử đổi từng thành phần | Phụ trách CRM/Sales phối hợp Như | Tồn component đúng sau lắp/bóc, giao hàng và đổi; test serial từng thành phần. |
| P2 | UAT biên nhận, SLA/cron, báo cáo và giao hàng một phần | Châu (hậu mãi), Như (đổi), người dùng cửa hàng | Checklist UAT có người xác nhận và kết quả trên database thử nghiệm. |

## 9. Kết luận

Code đã tạo được nền tảng liên thông cho bán hàng theo serial, tiếp nhận/sửa
chữa hậu mãi và đổi mới 1-1 có giao dịch kho. Những nội dung này không đồng
nghĩa mọi mục tiêu trong DOCX đã được tự động hóa: gửi hãng, hoàn tiền, xử lý
đầy đủ vật phẩm thiếu, luân chuyển thành phần combo, đồng bộ mọi dữ liệu legacy
và ánh xạ quyền theo hai actor vẫn cần quyết định hoặc hoàn thiện.

Trong báo cáo/demo, trình bày đúng hai vai trò **Nhân viên** và **Chủ cửa hàng
(quản lý/thủ kho)**. Chỉ mô tả một chức năng là đã làm khi code có logic tương
ứng; với tính năng có giao diện nhưng chưa tích hợp hoặc cần dữ liệu/quy tắc
chưa chốt, dùng trạng thái **Đã làm một phần** hoặc **Chưa làm**.

## 10. Tài liệu tham chiếu

- Đề xuất và phân tích ban đầu: [`custom_addons/Báo cáo TH ERP nhóm 5.docx`](./custom_addons/Báo%20c%C3%A1o%20TH%20ERP%20nh%C3%B3m%205.docx)
- Ma trận phân công hậu mãi: [`BAO_CAO_BAO_HANH_DOI_TRA_NHU_CHAU.md`](./BAO_CAO_BAO_HANH_DOI_TRA_NHU_CHAU.md)
- Hướng dẫn demo: [`FLOW_BAO_HANH_DOI_TRA.md`](./FLOW_BAO_HANH_DOI_TRA.md)
- Tiến độ toàn nhóm: [`BAO_CAO_TIEN_DO_TUAN.md`](./BAO_CAO_TIEN_DO_TUAN.md)
- Addon danh mục: [`custom_crm/`](./custom_addons/custom_crm/)
- Addon bán hàng: [`custom_sales/`](./custom_addons/custom_sales/)
- Addon hậu mãi: [`custom_warranty/`](./custom_addons/custom_warranty/)
