# Ma trận tiến độ — Bảo hành, sửa chữa và đổi mới 1-1

## 1. Phạm vi và cách đọc

Tài liệu đối chiếu phần phân công cho **Châu** (sửa chữa/bảo hành) và **Như**
(đổi mới 1-1/hậu mãi) trong `custom_addons/Báo cáo TH ERP nhóm 5.docx` với code
hiện tại.

Code hai người phụ trách đã được tách theo chức năng, nhưng vẫn thuộc cùng
module `custom_warranty` và cùng model `warranty.ticket`. Vì vậy, người phụ
trách trong bảng phản ánh **phân công ở báo cáo**, không phải bằng chứng về
tác giả từng dòng code.

**Trạng thái** đánh giá việc hoàn thành yêu cầu ở mức có thể dùng trong hệ
thống. Nếu chỉ tồn tại một phần hoặc chưa theo đúng toàn bộ quy tắc trong
báo cáo, trạng thái là **Chưa làm** và phần đã có được giải thích trong ghi
chú.

## 2. Ma trận phần Châu — Sửa chữa và bảo hành

| Yêu cầu theo báo cáo / kết quả mong muốn | Trạng thái | Code / backend | Giao diện | Cơ sở đối chiếu và ghi chú |
|---|---|---|---|---|
| Tạo phiếu tiếp nhận bảo hành, có mã phiếu, serial, ngày nhận, lỗi và tình trạng | Đã làm | `custom_addons/custom_warranty/models/warranty_models.py` — `WarrantyTicket` và các trường phiếu | `custom_addons/custom_warranty/views/warranty_views.xml` — form, list, Kanban | Báo cáo: Module 4, User Story 4; form tiếp nhận khi khách mang máy lỗi đến. |
| Nhập serial để tra cứu khách mua, sản phẩm, đơn bán, ngày mua và hạn bảo hành | Đã làm | `custom_addons/custom_warranty/models/warranty_models.py` — các trường related theo `serial_id` | `custom_addons/custom_warranty/views/warranty_views.xml` — thông tin trên form phiếu | Báo cáo: User Story 4; thông tin được lấy từ serial đã liên kết với giao dịch bán/giao hàng. |
| Tra cứu theo số điện thoại khách hàng | Đã làm | `custom_addons/custom_warranty/models/warranty_models.py` — `_onchange_customer_phone` | `custom_addons/custom_warranty/views/warranty_views.xml` — trường số điện thoại và serial | Có tự chọn khi chỉ tìm được một serial; cảnh báo khi có nhiều thiết bị hoặc không tìm thấy. |
| Tính số ngày bảo hành còn lại và hiển thị còn hạn/hết hạn/chưa rõ | Đã làm | `custom_addons/custom_warranty/models/warranty_models.py` — `_compute_days_remaining` | `custom_addons/custom_warranty/views/warranty_views.xml` — ngày hết hạn, số ngày còn lại, trạng thái | Báo cáo yêu cầu tra cứu thời hạn từ lịch sử bán hàng. Code hiện tính và hiển thị, nhưng chưa tự quyết định miễn phí/tính phí. |
| Theo dõi sửa chữa bằng Kanban: mới nhận → đang sửa → chờ linh kiện → đã xong | Đã làm | `custom_addons/custom_warranty/models/warranty_repair.py`; kiểm soát trạng thái dùng chung ở `custom_addons/custom_warranty/models/warranty_models.py` | `custom_addons/custom_warranty/views/warranty_views.xml` — nút thao tác, statusbar, Kanban | Báo cáo: phân công Châu và User Story 5. |
| Không cho hoàn tất sửa chữa nếu chưa ghi kết quả; cập nhật trạng thái serial trong lúc sửa | Đã làm | `custom_addons/custom_warranty/models/warranty_repair.py`; `write` trong `warranty_models.py` | Nút bắt đầu sửa/chờ linh kiện/tiếp tục/hoàn tất trong `warranty_views.xml` | Có kiểm tra kết quả sửa chữa; khi bắt đầu serial thành `under_repair`, khi hoàn tất trở về `sold`. |
| Kiểm thử luồng tiếp nhận, tra cứu, sửa chữa và chính sách chi phí | Đã làm | `custom_addons/custom_warranty/tests/test_warranty_ticket.py` — test luồng sửa chữa và 4 nhánh quyết định mới | Không áp dụng | Đã bổ sung test và kiểm tra cú pháp Python/XML, Problems không có lỗi. Test Odoo tích hợp chưa chạy được do máy hiện không có Docker/Odoo runner. |
| Quyết định bảo hành miễn phí/tính phí theo ngày hết hạn và nguyên nhân | Đã làm | `custom_addons/custom_warranty/models/warranty_models.py` — `_get_warranty_decision_policy`, `action_confirm_warranty_decision`, lý do/người/thời điểm xác nhận | `custom_addons/custom_warranty/views/warranty_views.xml` — chọn quyết định, nhập lý do và nút xác nhận | Mặc định chưa xác định để không tự kết luận; còn hạn + lỗi NSX → miễn phí, còn hạn + lỗi người dùng → tính phí, hết hạn → tính phí, thiếu nguyên nhân/hạn → chờ xác minh. Không tạo thanh toán/hóa đơn. |
| Các nhánh dịch vụ ngoài sửa/chờ linh kiện: gửi hãng, hãng đang xử lý, chờ khách, đã bàn giao | Chưa làm | Chưa có các trạng thái/quy trình riêng | Chưa có trên form/Kanban | Báo cáo yêu cầu các bước sửa, đổi trả, hoàn tất; các trạng thái chi tiết này là phần mở rộng vận hành đề xuất. |
| Người phụ trách kỹ thuật, hẹn trả/SLA và cảnh báo phiếu quá hạn | Đã làm | `warranty_models.py` — kỹ thuật viên, ngày hẹn, mốc bắt đầu/kết thúc, thời gian xử lý và `is_overdue` | `warranty_views.xml` — phân công, cảnh báo, lọc/nhóm theo kỹ thuật viên và quá hạn | Không đặt SLA mặc định; chỉ đánh dấu quá hạn khi người dùng nhập ngày hẹn và phiếu chưa hoàn tất. |
| Checklist tiếp nhận và hồ sơ ảnh tình trạng thiết bị | Đã làm | `warranty_models.py` — tình trạng màn hình/bàn phím/pin-sạc/phụ kiện, ghi chú tiếp nhận và nhiều `ir.attachment` ảnh | `warranty_views.xml` — tab Kiểm tra & mô tả lỗi, widget tải nhiều ảnh | Không có trường mật khẩu/PIN/tài khoản; thông tin có thể xem lại trên phiếu khi bàn giao. |

## 3. Ma trận phần Như — Đổi mới 1-1 và hậu mãi

| Yêu cầu theo báo cáo / kết quả mong muốn | Trạng thái | Code / backend | Giao diện | Cơ sở đối chiếu và ghi chú |
|---|---|---|---|---|
| Lập phiếu đổi mới 1-1 gắn serial cũ, serial mới, khách hàng, nguyên nhân và tình trạng máy | Đã làm | `custom_addons/custom_warranty/models/warranty_models.py` — `WarrantyTicket`, `new_serial_id`, checklist | `custom_addons/custom_warranty/views/warranty_views.xml` — tab Đổi mới 1-1 | Báo cáo: phân công Như và User Story 6. |
| Chỉ quản lý kho có quyền duyệt đổi | Đã làm | `custom_addons/custom_warranty/models/warranty_exchange.py` — `_check_manager`, `action_approve_exchange` | Nút duyệt chỉ hiện với nhóm quản lý kho | Đã có test `test_regular_stock_user_cannot_approve_exchange`; gọi backend trực tiếp cũng bị chặn. |
| Kiểm tra serial cũ, serial thay thế, cùng sản phẩm, lỗi NSX, hạn và checklist | Đã làm | `warranty_exchange.py` — `_validate_exchange_policy`, `action_approve_exchange`, `_get_lot_location`; policy sản phẩm/danh mục tại `warranty_models.py` | Form đổi mới có serial thay thế và checklist ngoại quan/nước/bảo mật; loại hàng và thời hạn cấu hình ở sản phẩm/danh mục | Thiết bị mới/cũ: mặc định tối đa 30 ngày; phụ kiện: phải cấu hình hạn theo hãng, tối đa 365 ngày. Chỉ đổi lỗi NSX, cùng mã sản phẩm và đạt checklist. |
| Thu hồi serial lỗi, xuất serial mới cho khách và lưu giao dịch kho | Đã làm | `warranty_exchange.py` — `_create_exchange_moves`; các move gắn vào phiếu | Tab Giao dịch kho trên form phiếu | Hàng lỗi vào vị trí cách ly/điều chỉnh, serial mới xuất cho khách; test rollback xác nhận lỗi giữa giao dịch không để lệch tồn. |
| Serial mới kế thừa khách hàng, ngày mua, hạn bảo hành và liên kết bán hàng từ serial cũ | Đã làm | `warranty_exchange.py` — cập nhật `new_sn`; liên kết cha/con ở `warranty_models.py` | Tab Lịch sử hậu mãi trên form serial | Bảo lưu quyền lợi, không khởi động lại thời hạn; truy ngược được các lần đổi tiếp theo. |
| Chặn duyệt lặp để không tạo trùng giao dịch đổi | Đã làm | `warranty_exchange.py`; kiểm tra phiếu đã có move và trạng thái phải hợp lệ | Nút duyệt đổi trên form | Test xác nhận gọi duyệt lại không tạo thêm giao dịch kho. |
| Từ chối đổi khi quá hạn | Đã làm | `warranty_exchange.py` — `_validate_exchange_policy`; thời hạn tại product/category | Báo lỗi khi duyệt | Có test ca quá hạn; thời hạn tối đa không vượt chính sách loại hàng. |
| Ma trận policy theo thiết bị mới/cũ, phụ kiện, lỗi NSX/người dùng và khoảng thời gian | Đã làm | `warranty_models.py` — `exchange_item_type`, `_get_exchange_period_days`; `warranty_exchange.py` — kiểm tra điều kiện | Cấu hình nhóm policy và thời hạn trên form sản phẩm/danh mục | Thiết bị mới/cũ áp dụng tối đa 0–30 ngày; phụ kiện cấu hình theo hãng trong giới hạn 0–365 ngày. Lỗi người dùng/chưa xác định không được đổi. |
| Hết hàng đổi: giữ phiếu chờ serial và tiếp tục khi có hàng | Đã làm | `warranty_models.py` — trạng thái `waiting_serial`; `warranty_exchange.py` — `action_wait_for_exchange_serial` | Nút “Chờ serial thay thế”; chọn serial rồi quản lý duyệt tiếp | Đáp ứng nhánh chờ hàng của báo cáo; hệ thống chưa tự tạo đơn mua/phiếu backorder cung ứng. |
| Cấn trừ hộp/phụ kiện thiếu khi đổi | Chưa làm — cần chốt quy tắc xử lý vật phẩm thiếu trước khi cập nhật tồn kho | Chưa có dòng phụ kiện đi kèm phiếu đổi hoặc giao dịch nhận/giữ phụ kiện | Chưa có checklist/dòng phụ kiện | Báo cáo mục 2.2.1 đề cập cấn trừ bằng hiện vật nhưng chưa quy định cửa hàng giữ phụ kiện, khách bổ sung hay cấn trừ theo giá nào. Không tự tạo nghiệp vụ tiền vì cửa hàng đã xác nhận không hoàn tiền. |
| Đổi riêng một món trong combo nhưng vẫn truy được quan hệ với combo đã bán | Đã làm | `custom_crm/models/product_combo.py` lưu rule trên dòng bán; `custom_sales/models/sale_order_custom.py` gắn rule cho dòng quà và liên kết serial thực giao với dòng bán; serial thay thế giữ nguyên liên kết | Dòng đơn bán hiển thị rule combo; serial và phiếu hậu mãi dẫn đến dòng bán gốc | Không suy luận từ tổng đơn: rule được lưu trực tiếp lúc tạo quà, dòng serial được lưu sau giao hàng; đổi 1-1 bảo toàn liên kết nguồn. |
| Từ chối đổi thì chuyển tiếp rõ ràng sang sửa chữa/bảo hành | Đã làm phần Như kết nối luồng: chuyển phiếu đổi chưa duyệt thành phiếu sửa chữa, bắt buộc lưu lý do/ngày chuyển; quy trình sửa chữa tiếp theo thuộc Châu | `warranty_exchange.py` — `action_refer_exchange_to_repair`; audit fields và kiểm tra chuyển trạng thái tại `warranty_models.py` | Nút “Chuyển sang sửa chữa”; lý do được giữ và khóa sau khi chuyển | Test chuyển phiếu quá hạn sang repair, bắt buộc lý do và tiếp tục bắt đầu sửa. SLA/policy sửa chữa là phần Châu. |
| Chỉ đổi 1-1, không trả hàng/hoàn tiền sau mua | Đã làm | Loại phiếu chỉ còn `repair` và `exchange`; backend không có action trả hàng | Không còn lựa chọn/nút/tab trả hàng trong `warranty_views.xml` | Theo chính sách cửa hàng đã xác nhận. Không đồng nghĩa đã triển khai hoàn tiền; hoàn tiền nằm ngoài phạm vi. |
| Lịch sử serial gốc → serial đổi → các lần bảo hành/sửa tiếp theo | Đã làm | `warranty_models.py` — `x_replaced_from_lot_id`, `x_replacement_lot_ids`, quan hệ phiếu; cập nhật quan hệ trong `warranty_exchange.py` | Tab “Lịch sử hậu mãi” trên form serial | Test đổi nhiều lần xác nhận chuỗi serial và phiếu đổi/bảo hành liên quan. |
| Báo cáo chung số phiếu sửa/đổi theo tháng, loại, trạng thái, nguyên nhân và thời gian xử lý | Đã làm | `views/warranty_report_views.xml` — pivot có kỹ thuật viên và tổng thời gian xử lý | Menu “Báo cáo Hậu mãi”, biểu đồ/pivot và bộ lọc quá hạn | Không có tiền/kế toán; thời gian chỉ phát sinh khi phiếu bắt đầu sửa. |
| Kiểm thử policy, đổi thành công, bảo toàn quyền lợi, quá hạn, chờ hàng, rollback, chuyển sửa chữa, quyền, báo cáo, dòng bán/serial combo và loại phiếu trả không được hỗ trợ | Đã làm | `custom_addons/custom_warranty/tests/test_warranty_ticket.py`; `custom_addons/custom_sales/tests/test_sales_custom.py` | Không áp dụng | Đã chạy tích hợp 18 test: 13 test `custom_warranty` và 5 test `custom_sales`, 0 lỗi/0 thất bại; gồm kiểm tra serial đổi giữ dòng bán gốc và serial quà liên kết đúng dòng/rule combo. |

## 4. Hạng mục dùng chung

| Hạng mục | Trạng thái | Vị trí code / giao diện | Ghi chú |
|---|---|---|---|
| Dữ liệu phiếu, serial, khách hàng, hạn bảo hành và trạng thái chung | Đã làm | Backend: `custom_addons/custom_warranty/models/warranty_models.py`; view: `custom_addons/custom_warranty/views/warranty_views.xml` | Đây là nền dùng chung cho hai nhánh, không nên nhân đôi model. |
| Nạp riêng logic sửa chữa và đổi mới theo file | Đã làm | `custom_addons/custom_warranty/models/warranty_repair.py`, `custom_addons/custom_warranty/models/warranty_exchange.py`; nạp qua `custom_addons/custom_warranty/models/__init__.py` | Tách code theo chức năng nhưng vẫn cùng module/model để giữ liên kết phiếu. |
| Ghi ngày giao, hạn bảo hành và dòng bán gốc lên serial sau bán | Đã làm | `custom_addons/custom_sales/models/sale_order_custom.py` — `StockPicking._action_done`; `custom_addons/custom_warranty/models/sale_order_line.py` | Phiếu hậu mãi dẫn đến dòng bán gốc; dòng quà cho biết rule combo đã áp dụng. |
| Backend chỉ cho quản lý kho duyệt đổi; nhân viên kho thường không thể gọi action duyệt trực tiếp | Đã làm | `custom_addons/custom_warranty/models/warranty_exchange.py` — `_check_manager` | Nút UI giới hạn nhóm quản lý; test `test_regular_stock_user_cannot_approve_exchange` xác nhận backend từ chối user thường. |
| Phân quyền đầy đủ theo nhân viên tiếp nhận, kỹ thuật viên và phiếu được giao | Chưa làm — phần phân nhóm và người phụ trách thuộc Châu; chưa có ma trận quyền chi tiết đã chốt | ACL: `custom_addons/custom_warranty/security/ir.model.access.csv`; hiện cấp quyền theo nhóm user/manager | Duyệt đổi đã được chặn backend cho nhân viên thường; chưa có nhóm riêng tiếp nhận/kỹ thuật hoặc record rules theo người tạo/người phụ trách. |
| Chuyển phiếu đổi đủ điều kiện sang quy trình sửa chữa có audit | Đã làm phần nối dùng chung | `models/warranty_exchange.py`, `models/warranty_models.py` | Nút chuyển từ phiếu đổi sang sửa chữa | Châu tiếp tục phụ trách chính policy miễn phí/tính phí và trạng thái sửa chữa; Như phụ trách yêu cầu lý do và giữ audit khi bàn giao. |

## 5. Đề xuất bổ sung theo mức ưu tiên

| Ưu tiên | Đề xuất và lợi ích | Trạng thái hiện tại | Vị trí code hiện tại / dự kiến | Giao diện hiện tại / dự kiến | Cơ sở |
|---|---|---|---|---|---|
| P0 — Rất cao | **Chính sách đổi tập trung, có thể kiểm thử:** quy định nhóm hàng mới/cũ/phụ kiện, lỗi NSX/người dùng, hạn và checklist đủ điều kiện. | Đã làm | `models/warranty_models.py` — policy product/category; `models/warranty_exchange.py` — `_validate_exchange_policy` | Form sản phẩm/danh mục cấu hình loại hàng và thời hạn; phiếu hiển thị checklist | Thiết bị mới/cũ tối đa 30 ngày; phụ kiện cấu hình theo hãng, tối đa 365 ngày; cùng sản phẩm, lỗi NSX, checklist đạt. |
| P0 — Rất cao | **Không đưa serial hàng đổi cũ vào tồn có thể bán; rollback nếu giao dịch lỗi.** | Đã làm | `models/warranty_exchange.py`, `tests/test_warranty_ticket.py` — `test_exchange_rolls_back_both_moves_when_second_step_fails` | Tab hiển thị hai stock move trên phiếu | Test mô phỏng lỗi sau khi thu hồi serial cũ và xác nhận cả tồn, serial, phiếu và move được rollback. |
| P1 — Cao | **Chờ hàng đổi khi hết tồn:** giữ phiếu chờ serial thay thế rồi tiếp tục duyệt khi có hàng, không tạo lại phiếu. | Đã làm phần chờ/tiếp tục; chưa tự tạo đơn mua/backorder — chưa có rule nhà cung cấp, kho nhận và luồng mua cần dùng | `models/warranty_models.py`, `models/warranty_exchange.py` | Nút “Chờ serial thay thế”; chọn serial khi có hàng và quản lý duyệt | Nhánh chờ hàng của báo cáo đã đáp ứng; tự tạo procurement để lại vì cần quy trình mua hàng được thống nhất. |
| P1 — Cao | **Chuyển từ đổi sang sửa chữa có lưu lý do và lịch sử.** | Đã làm phần Như kết nối; Châu còn hoàn thiện policy/trạng thái sửa chữa | `models/warranty_models.py`, `models/warranty_exchange.py`; phần tiếp tục ở `models/warranty_repair.py` | Nút chuyển yêu cầu lý do; phiếu chuyển sang trạng thái sửa chữa mới | Lưu được lý do/ngày chuyển; chưa tự gán miễn phí/tính phí vì quy tắc thuộc Châu và chưa chốt đầy đủ. |
| P1 — Cao | **Checklist nhận máy có bằng chứng:** ảnh ngoại quan, phụ kiện, mô tả vết xước/va đập và xác nhận khách; không lưu mật khẩu/đăng nhập. | Đã làm phần checklist và ảnh; chưa có mẫu biên nhận/xác nhận điện tử riêng | `models/warranty_models.py` / attachments | Tab tiếp nhận cho phép ghi checklist và tải nhiều ảnh; không thu thập dữ liệu nhạy cảm. |
| P1 — Cao | **Cấn trừ hộp/phụ kiện thiếu khi đổi.** | Chưa làm — chưa có chính sách cửa hàng xác định xử lý/định giá phụ kiện thiếu | Dự kiến model phụ kiện kèm phiếu và giao dịch kho | Dự kiến checklist/dòng phụ kiện trên form | Cần quyết định xử lý bằng hiện vật và quy tắc định giá; không tự đưa khoản thu/hoàn tiền vào nghiệp vụ. |
| P1 — Cao | **Phân quyền đúng vai trò:** tiếp nhận, kỹ thuật viên, người duyệt đổi. | Phần backend chặn duyệt đổi đã làm; nhóm riêng, quyền sửa chữa và record rules chưa làm — cần Châu chốt ma trận quyền và người phụ trách phiếu | `models/warranty_exchange.py`; phần còn lại tại `security/ir.model.access.csv` và security XML | Nút duyệt kho chỉ dành quản lý; phân nhóm/giới hạn phiếu còn thiếu | Thiếu danh sách vai trò và quyền CRUD/ủy quyền trên từng trạng thái; không tự khóa nhân viên theo giả định. |
| P2 — Vừa | **Theo dõi thời gian xử lý:** kỹ thuật viên phụ trách, ngày hẹn, thời điểm bắt đầu/dừng, cảnh báo phiếu chậm. | Đã làm | `custom_warranty/models/warranty_models.py` | Thông tin người xử lý, ngày hẹn, mốc thời gian và bộ lọc “Quá hạn” trên list/search | Không đặt SLA cố định; ngày hẹn do nhân viên nhập. |
| P2 — Vừa | **Lịch sử chuỗi serial khi đổi nhiều lần:** truy ngược serial gốc → serial thay thế → phiếu hậu mãi tiếp theo. | Đã làm | `models/warranty_models.py`, `models/warranty_exchange.py` | Tab “Lịch sử hậu mãi” trên form serial | Quan hệ trước/sau và phiếu hậu mãi đã có test đổi nhiều lần. |
| P2 — Vừa | **Báo cáo hậu mãi dùng chung:** số phiếu theo tháng, loại xử lý, trạng thái, nguyên nhân và thời gian xử lý. | Đã làm | `views/warranty_report_views.xml` | Menu “Báo cáo Hậu mãi”, pivot có kỹ thuật viên và tổng thời gian xử lý | Châu phụ trách chỉ số sửa chữa/SLA; Như phụ trách các số liệu đổi. |
| P2 — Vừa | **Truy vết serial đổi thuộc món nào trong combo đã bán.** | Đã làm — dòng quà giữ rule combo, serial giao lưu dòng bán gốc và serial đổi kế thừa dòng bán | `custom_crm/models/product_combo.py`, `custom_sales/models/sale_order_custom.py`, `custom_warranty/models/warranty_models.py`, `custom_warranty/models/warranty_exchange.py` | Rule hiển thị trên dòng đơn bán; serial và phiếu hậu mãi có đường dẫn tới dòng bán gốc | Liên kết được lưu trực tiếp khi tạo quà/giao hàng, không suy luận rule từ tổng đơn. |

### Phân công và trạng thái — cân bằng giữa Như và Châu

| Ưu tiên | Đầu việc | Phụ trách chính | Trạng thái | Phối hợp / ranh giới / lý do nếu chưa làm |
|---|---|---|---|---|
| P0 — Rất cao | Policy đổi 1-1 theo nhóm thiết bị mới/cũ/phụ kiện, lỗi, hạn và checklist | **Như** | **Đã làm** | Cấu hình trên sản phẩm/danh mục; Châu rà soát giao điểm với sửa chữa. |
| P0 — Rất cao | Tính toàn vẹn giao dịch đổi kho và rollback khi lỗi | **Như** | **Đã làm** | Có test lỗi giữa hai dịch chuyển, tồn/serial/phiếu không bị cập nhật dở. |
| P1 — Cao | Giữ phiếu chờ serial thay thế và tiếp tục khi có hàng | **Như** | **Đã làm một phần** | Có trạng thái chờ và thao tác tiếp tục; chưa tự tạo đơn mua/backorder vì chưa chốt nhà cung cấp/kho nhận/quy trình mua. |
| P1 — Cao | Lịch sử serial gốc → serial thay thế → phiếu hậu mãi sau đổi | **Như** | **Đã làm** | Tab lịch sử trên serial và kiểm thử đổi nhiều lần. |
| P1 — Cao | Cấn trừ hộp/phụ kiện thiếu bằng hiện vật khi đổi | **Như** | **Chưa làm** | Cần cửa hàng chốt giữ/bổ sung phụ kiện và cách định giá hiện vật; không tự đưa khoản tiền vào luồng đổi. |
| P2 — Vừa | Liên kết serial đổi với món thuộc combo/khuyến mại đã bán | **Như** | **Đã làm** | Rule combo được lưu trên dòng quà, serial thực giao liên kết dòng bán gốc; serial thay thế kế thừa liên kết để phiếu hậu mãi tra ngược được. |
| P1 — Cao | Chuyển phiếu đổi chưa duyệt sang sửa chữa và lưu lý do/ngày chuyển | **Như kết nối; Châu tiếp nhận quy trình sửa** | **Đã làm** | Nút chuyển và audit đã có; Châu đã bổ sung policy miễn phí/tính phí, phân công kỹ thuật và workflow sửa chữa. |
| P0 — Rất cao | Policy bảo hành miễn phí/tính phí theo hạn và nguyên nhân | **Châu** | **Đã làm** | Có quy tắc, lý do, người/thời điểm xác nhận và test các nhánh chính sách; test tích hợp chờ môi trường Odoo. |
| P1 — Cao | Checklist tiếp nhận có ảnh, phụ kiện, ngoại quan và biên nhận | **Châu** | **Đã làm** | Đã có checklist, ghi chú, phụ kiện, nhiều ảnh và mẫu biên nhận QWeb PDF; chữ ký trên mẫu chỉ là khu vực ký tay, không phải chữ ký điện tử. Không thu thập mật khẩu/tài khoản. |
| P1 — Cao | Quyền tiếp nhận/kỹ thuật/quản lý và giới hạn phiếu theo người phụ trách | **Châu và Như** | **Đã làm** | Đã thêm nhóm riêng Kỹ thuật viên bảo hành và Quản lý bảo hành, ACL và Record Rule; không thay đổi nhóm `stock` hiện có. Kỹ thuật viên chỉ thấy phiếu được phân công, quản lý thấy toàn bộ. |
| P2 — Vừa | SLA, người phụ trách, thời gian xử lý và cảnh báo trễ | **Châu** | **Đã làm** | Đã có kỹ thuật viên, ngày hẹn, mốc bắt đầu/kết thúc, thời gian xử lý và bộ lọc quá hạn; không tự đặt SLA cố định. |
| P2 — Vừa | Báo cáo vận hành phiếu hậu mãi | **Chia theo nghiệp vụ** | **Đã làm** | Báo cáo có số phiếu theo tháng/loại/trạng thái/nguyên nhân, kỹ thuật viên và tổng thời gian xử lý. Có thêm biên nhận QWeb PDF; không gồm kế toán. |

**Cân bằng khối lượng:** Như đã hoàn tất policy đổi, rollback, lịch sử serial,
phần chờ serial và kết nối chuyển sang sửa chữa; đồng thời hoàn tất phần backend
duyệt đổi trong hạng mục phân quyền và báo cáo số liệu. Các việc Như còn mở là
phụ kiện thiếu và truy vết combo, đều đang chờ quy tắc/dữ liệu liên kết được
chốt; không tạo nghiệp vụ suy đoán. Châu đã hoàn thiện phần sửa chữa/bảo hành, checklist tiếp nhận, phân công kỹ
thuật viên, SLA và báo cáo thời gian xử lý. Ma trận quyền riêng theo vai trò
tiếp nhận/kỹ thuật chưa mở rộng vì chưa có chính sách quyền được chốt; quyền
hiện tại vẫn được giữ nguyên. Phần dashboard đã chia rõ: Như phụ trách số liệu
đổi, Châu phụ trách chỉ số sửa chữa/SLA.

## 6. Khuyến nghị về trả hàng hoàn tiền hay chỉ đổi 1-1

**Khuyến nghị cho phạm vi hiện tại: chỉ hỗ trợ đổi mới 1-1 theo điều kiện đã
công bố; không tạo luồng trả hàng để hoàn tiền sau khi mua.** Đây là lựa chọn
phù hợp với chính sách cửa hàng bạn vừa xác nhận, đồng thời đúng trọng tâm đồ
án là serial, hậu mãi và luân chuyển kho. Code hiện đã bỏ loại phiếu trả hàng
độc lập; các ngoại lệ không đủ điều kiện đổi nên được xử lý bằng sửa chữa/bảo
hành nếu đủ điều kiện, không biến thành hoàn tiền.

Không nên tự đặt một mốc “hoàn tiền X ngày” nếu cửa hàng không có chính sách
đó. Báo cáo DOCX cũng ghi “Đổi/Trả theo nhu cầu” là không hỗ trợ trên hệ
thống; các mốc 0–30 ngày trong bảng là điều kiện **đổi 1-1 do lỗi NSX**, không
phải thời hạn trả hàng/hoàn tiền. Code hiện áp dụng tối đa 30 ngày cho thiết
bị mới/đã qua sử dụng; phụ kiện cần cấu hình thời hạn theo hãng, tối đa 365
ngày. Cửa hàng vẫn cần xác nhận policy thực tế ở sản phẩm/danh mục trước khi
dùng; không mặc định 12 tháng cho mọi phụ kiện.

Nếu sau này cửa hàng muốn cho trả hàng hoàn tiền như một chính sách kinh doanh
riêng, hãy chốt trước phạm vi sản phẩm, số ngày, điều kiện hàng/bao bì, trường
hợp lỗi người dùng, phí/khấu trừ và luồng kế toán với người có trách nhiệm.
Khi đó mới bổ sung thành nghiệp vụ riêng; không nên dùng chung nút đổi 1-1
hoặc gọi việc nhập serial về kho là “hoàn tiền”.

## 7. Kịch bản demo đề xuất

1. Tạo phiếu sửa chữa bằng số điện thoại; xác minh serial, khách, ngày mua và
   hạn bảo hành.
2. Chuyển phiếu qua **Đang sửa → Chờ thay linh kiện → Đã xong**, ghi kết quả.
3. Tạo phiếu đổi 1-1 còn trong hạn; có thể đưa phiếu vào “Chờ serial thay
   thế”, gán serial khi hàng có sẵn rồi để quản lý duyệt; chỉ ra serial cũ vào
   vị trí hàng lỗi, serial mới giao khách và hạn bảo hành được giữ nguyên.
4. Demo ca đổi không đạt điều kiện; nhập lý do và chuyển sang sửa chữa/bảo
   hành. Châu tiếp tục phân luồng dịch vụ theo chính sách sửa chữa.
5. Nêu chính sách phạm vi: không trả hàng/hoàn tiền sau mua; không demo luồng
   này vì cửa hàng không hỗ trợ.

## 8. Các vị trí code chính

| Phần | Backend / dữ liệu | Giao diện | Test |
|---|---|---|---|
| Châu — sửa chữa/bảo hành | `custom_addons/custom_warranty/models/warranty_repair.py`; dữ liệu phiếu chung tại `custom_addons/custom_warranty/models/warranty_models.py` | `custom_addons/custom_warranty/views/warranty_views.xml` | `custom_addons/custom_warranty/tests/test_warranty_ticket.py` |
| Như — đổi mới 1-1 | `custom_addons/custom_warranty/models/warranty_exchange.py`; policy, trạng thái và lịch sử serial tại `custom_addons/custom_warranty/models/warranty_models.py` | Form đổi/serial tại `custom_addons/custom_warranty/views/warranty_views.xml`; báo cáo tại `custom_addons/custom_warranty/views/warranty_report_views.xml` | `custom_addons/custom_warranty/tests/test_warranty_ticket.py` |
| Báo cáo dùng chung / điều hướng sang sửa chữa | `warranty_exchange.py` — chuyển đổi có audit; report action trong `warranty_report_views.xml` | Nút chuyển từ phiếu đổi; menu “Báo cáo Hậu mãi” | `test_exchange_can_be_referred_to_repair_with_audited_reason`, `test_operations_report_includes_repair_and_exchange_tickets` |
| Liên kết dòng bán, rule combo và serial giao/đổi | `custom_addons/custom_crm/models/product_combo.py`, `custom_addons/custom_sales/models/sale_order_custom.py`, `custom_addons/custom_warranty/models/warranty_models.py`, `custom_addons/custom_warranty/models/warranty_exchange.py` | `custom_addons/custom_sales/views/sale_order_views.xml`, `custom_addons/custom_warranty/views/warranty_views.xml` | `custom_addons/custom_sales/tests/test_sales_custom.py`, `custom_addons/custom_warranty/tests/test_warranty_ticket.py` |
| Nạp hai phần mở rộng vào module | `custom_addons/custom_warranty/models/__init__.py` | — | — |

## 9. Rà soát cấu trúc module

Giữ cấu trúc chuẩn addon Odoo (`models/`, `views/`, `demo/`, `tests/`,
`security/`, `data/`, `migrations/`); không tách thành addon riêng vì phiếu,
serial và thao tác kho dùng chung. Logic sửa chữa và đổi mới nằm riêng ở
`warranty_repair.py` và `warranty_exchange.py`. Đã bỏ
`demo/warranty_exchange_samples.xml` vì tạo lại sản phẩm/serial/phiếu đổi mẫu
đã có trong `demo/warranty_demo.xml`. Báo cáo đổi có file view riêng để không
trộn với form phiếu. Các thư mục cache `__pycache__` là file sinh tự động,
được `.gitignore` loại trừ, không cần đưa vào source.
