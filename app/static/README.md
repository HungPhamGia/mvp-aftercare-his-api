# AfterCare — Hệ thống theo dõi bệnh nhân sau xuất viện

AfterCare là phần mềm hỗ trợ bác sĩ và điều dưỡng **theo dõi bệnh nhân sau khi xuất viện**.
Một trợ lý AI sẽ **gọi điện tự động** cho bệnh nhân theo giao thức của từng bệnh, ghi nhận
triệu chứng, và **gắn cờ ưu tiên** những ca cần bác sĩ xem ngay. Toàn bộ giao diện dành cho
nhân viên y tế dùng **tiếng Việt, ngôn ngữ đời thường**, ưu tiên *việc cần làm* hơn là số liệu.

> Đây là bản nguyên mẫu (prototype) chạy hoàn toàn trên trình duyệt. Dữ liệu là dữ liệu mẫu.
> Ngày "hôm nay" trong bản demo là **16/06/2026**.

---

## Chạy thử

Cần Node.js. Tại thư mục dự án:

```bash
node server.js
```

Mở trình duyệt: `http://127.0.0.1:5174`
(Có thể đổi cổng: `PORT=8080 node server.js`.)

Hoặc chỉ cần mở thẳng `index.html` bằng trình duyệt.

---

## Cấu trúc thư mục

```
aftercare/
├── index.html            # Bảng điều phối (việc cần làm hôm nay)
├── patients.html         # Danh sách bệnh nhân (tìm kiếm, lọc, xem nhanh)
├── case.html             # Chi tiết một ca bệnh
├── call.html             # Màn hình gọi bệnh nhân thủ công
├── appointments.html     # Lịch hẹn tái khám (ngày/tuần/tháng)
├── manager.html          # Quản lý gọi AI (5 công cụ)
├── settings.html         # Cài đặt: hồ sơ, giao diện, hỗ trợ
├── server.js             # Máy chủ tĩnh đơn giản
├── images/               # Logo
├── css/                  # style.css (hệ thống thiết kế) + CSS từng trang
└── js/                   # data.js (dữ liệu) + app.js (dùng chung) + JS từng trang
```

Thứ tự nạp script ở mỗi trang: **`data.js` → `app.js` → `<trang>.js`**.

---

## Các màn hình chính

### 1. Bảng điều phối (`index.html`)
Tập trung vào **việc cần xử lý**, không phải thống kê:
- **Cần bác sĩ xem** — ca được trợ lý nâng cảnh báo.
- **Cuộc gọi AI hôm nay** — lịch gọi trong ngày.
- **Cuộc gọi thất bại** — cần gọi lại.
- **Theo dõi quá hạn** — bệnh nhân trễ lịch.
- **Lịch hẹn hôm nay**.

Di chuột vào một bệnh nhân để **xem nhanh** (triệu chứng, tóm tắt AI, lời bệnh nhân,
lần gọi gần nhất, lần gọi kế tiếp).

### 2. Bệnh nhân (`patients.html`)
- Tìm theo **tên / mã hồ sơ**.
- Lọc theo **chẩn đoán, bác sĩ, mức ưu tiên, trạng thái gọi AI, quá hạn, theo dõi thủ công**.
- **Sắp xếp**, **chế độ gọn**, chuyển đổi **Danh sách / Thẻ**, và **xem nhanh khi di chuột**.

### 3. Chi tiết ca (`case.html`)
Hiển thị đầy đủ: **độ tin cậy AI, lý do nâng cảnh báo, giao thức khớp, diễn biến gần đây,
tuân thủ thuốc, các cuộc gọi trước, tóm tắt & bản ghi**, kèm **dòng thời gian theo dõi**.
Bác sĩ có thể: gọi lại bệnh nhân, lên lịch gọi AI, gán điều dưỡng, đặt lịch khám,
chuyển chuyên khoa, bỏ qua cảnh báo, đóng ca.

### 4. Gọi bệnh nhân (`call.html`)
Màn hình gọi **thủ công**: số điện thoại bệnh nhân & người nhà, nút **Sao chép** và **Gọi**,
ô **ghi chú**, chọn **kết quả cuộc gọi** và **Hoàn tất cuộc gọi**.

### 5. Quản lý gọi AI (`manager.html`)
Một module gồm 5 công cụ (chuyển bằng thẻ ở đầu trang):
- **Lịch gọi AI** — xem theo ngày/tuần/tháng, kéo–thả đổi ngày gọi, danh sách sắp tới,
  **tạo lịch gọi** theo bệnh nhân/bệnh/giao thức với khoảng lặp 3/7/14 ngày hoặc tùy chỉnh
  (chọn ngày bắt đầu → tự tính các ngày gọi tiếp theo), cấu hình **giờ làm việc, gọi lại,
  ngày nghỉ**.
- **Bộ câu hỏi** — bộ câu hỏi theo bệnh, gán tự động/thủ công, **kéo–thả sắp xếp**,
  bắt buộc/tùy chọn, bật/tắt câu hỏi, **nhánh điều kiện**, lịch sử phiên bản.
- **Giao thức & cảnh báo** — thêm/sửa/xóa/nhân bản/bật-tắt quy tắc; đặt điều kiện kích hoạt,
  mức ưu tiên, người nhận thông báo, tự đặt lịch khám, cần duyệt thủ công.
- **Hiệu suất AI** — cuộc gọi hoàn thành/thất bại, tỷ lệ chuyển cảnh báo, thời lượng trung bình,
  số lần can thiệp, phân bố độ tin cậy.
- **Thông báo** — gọi thất bại, ca được nâng cảnh báo, quá hạn, nhắc lịch hẹn, tin nhắn nhóm.

### 6. Lịch hẹn (`appointments.html`)
Giống lịch Google: **ngày/tuần/tháng**, **thêm/sửa/xóa**, **kéo–thả** đổi ngày,
**xem nhanh** khi di chuột, **lọc theo bác sĩ / bệnh nhân / bệnh**.

### 7. Cài đặt (`settings.html`)
- **Đăng nhập (mô phỏng)**, chỉnh **họ tên, chức danh, khoa**. Bấm vào hồ sơ ở thanh bên
  cũng mở trang này.
- **Chế độ Sáng / Tối**, **cỡ chữ**, **tỷ lệ giao diện**.
- **Hỗ trợ tiếp cận**: tương phản cao, giảm chuyển động.
- **FAQ, Hướng dẫn, Liên hệ AfterCare, Báo lỗi / Góp ý**.

Cài đặt được lưu cục bộ trên trình duyệt (theo sở thích người dùng).

---

## Ghi chú kỹ thuật
- Không dùng framework — chỉ HTML/CSS/JavaScript thuần, dễ đọc và chỉnh sửa.
- Bảng màu giữ nhận diện AfterCare: **nền trắng, nhấn xanh lá, nút bo tròn**, có chế độ tối.
- Một số chỉnh sửa trong "Quản lý gọi AI" và "Lịch hẹn" được giữ trong phiên làm việc
  (làm mới trang sẽ trở về dữ liệu mẫu) — phù hợp cho bản trình diễn.
