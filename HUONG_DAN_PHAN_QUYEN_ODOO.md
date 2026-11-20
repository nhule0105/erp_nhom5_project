# Hướng dẫn cấu hình phân quyền Odoo cho cửa hàng bán lẻ kiêm bảo hành

## Phần 1: Tạo tài khoản, phân quyền và cấp mật khẩu

Thực hiện lần lượt cho từng tài khoản. Vào **Settings → Users & Companies → Users → New**. Điền thông tin và chọn quyền trên tab **Access Rights** theo bảng dưới đây.

| Mục trên màn hình Odoo | Tài khoản 1: Nhân viên | Tài khoản 2: Chủ cửa hàng |
|---|---|---|
| Name | `Nhân viên` | `Chủ cửa hàng` |
| Email Address | `nhanvien@demo.com` | `chucuahang@demo.com` |
| Mật khẩu | `123456` | `123456` |
| User Type | `Internal User` | `Internal User` |
| **Sales** (mục SALES — cột trái) | `User: All Documents` | `Administrator` |
| **Invoicing** (mục ACCOUNTING — cột phải) | `Billing` (hoặc để trống) | `Administrator` (hoặc `Billing`) |
| **Bank** (mục ACCOUNTING) | Để trống | Để trống |
| **Inventory** (ô thả xuống) | `User` | `Administrator` |
| **Administration** | Để trống | `Settings` (hoặc `Access Rights`) |
| **Kỹ thuật viên bảo hành** (ô dưới Administration) | Tích chọn (✓) | Tích chọn (✓) |
| **Quản lý bảo hành** (ô dưới Administration) | Bỏ trống (☐) | Tích chọn (✓) |
| **Manage Lots / Serial Numbers** (mục TECHNICAL) | Tích chọn (✓) | Tích chọn (✓) |
| **Contact Creation** (mục EXTRA RIGHTS) | Tích chọn (✓) | Tích chọn (✓) |
| Các mục quyền khác đã được tích sẵn | Giữ nguyên mặc định | Giữ nguyên mặc định |

1. Sau khi nhập thông tin và chọn quyền, bấm biểu tượng đám mây nhỏ ở góc trên bên trái để lưu tài khoản.
2. Với từng tài khoản vừa tạo, bấm biểu tượng bánh răng **⚙ → Change Password**.
3. Nhập mật khẩu mới `123456`, xác nhận nếu màn hình yêu cầu, rồi xác nhận thay đổi.
4. Lặp lại các bước trên cho tài khoản còn lại. Có thể đăng xuất/đăng nhập bằng từng tài khoản để kiểm tra quyền hiển thị và thao tác.

> **Lưu ý:** `123456` là mật khẩu đơn giản, chỉ phù hợp cho môi trường demo. Hãy đổi sang mật khẩu riêng, đủ mạnh trước khi dùng thực tế.

## Phần 2: Tắt quy tắc giới hạn dữ liệu (Record Rules)

Nhân viên cửa hàng vừa tiếp nhận sản phẩm bảo hành vừa bán hàng, nên tại quầy cần tra cứu được toàn bộ lịch sử bảo hành của khách hàng, không chỉ các phiếu được giao cho chính nhân viên đó.

Thực hiện bằng tài khoản **Chủ cửa hàng** hoặc tài khoản quản trị đã bật Developer Mode:

1. Vào **Settings → Technical → Security → Record Rules**.
2. Tìm quy tắc có tên **Kỹ thuật viên chỉ xem phiếu được phân công**.
3. Mở quy tắc đó và gạt tắt **Active**, sau đó lưu. Nếu giao diện không có công tắc **Active**, dùng **Action → Archive**.
4. Trên phiên đăng nhập của tài khoản **Nhân viên**, nhấn **F5** để tải lại màn hình rồi mở danh sách phiếu bảo hành và kiểm tra khả năng tra cứu.

Quy tắc này giới hạn phiếu bảo hành theo nhân viên được phân công. Tắt/lưu trữ nó sẽ bỏ giới hạn đó cho nhóm kỹ thuật viên; các quyền truy cập và quy tắc dữ liệu khác vẫn tiếp tục có hiệu lực. Tài khoản Chủ cửa hàng được gán nhóm quản lý bảo hành nên vốn có quy tắc cho phép xem toàn bộ phiếu.
