# Dự Án Ứng Dụng Phát Trực Tiếp Video qua RTP/RTSP

## 📋 Giới Thiệu

Đây là một dự án **phát trực tiếp video** (Video Streaming) sử dụng giao thức **RTSP (Real-Time Streaming Protocol)** và **RTP (Real-Time Transport Protocol)**. Dự án được phát triển bằng **Python** với giao diện đồ họa **Tkinter**.

**Mục đích học tập:** Hiểu rõ cách hoạt động của các giao thức mạng thời gian thực, socket lập trình, và xử lý luồng đa luồng (threading) trong Python.

---

## 🎯 Tính Năng Chính

✅ **Server RTSP**: Lắng nghe các yêu cầu từ client và phát trực tiếp video  
✅ **Client GUI**: Giao diện đồ họa để kiểm soát phát video (Play, Pause, Stop)  
✅ **Giao thức RTP**: Đóng gói dữ liệu video theo tiêu chuẩn RTP  
✅ **Điều khiển qua RTSP**: Sử dụng RTSP để điều khiển việc phát video  
✅ **Hỗ trợ MJPEG**: Định dạng video JPEG liên tiếp  

---

## 📁 Cấu Trúc Thư Mục

```
python_rtp/
├── README.md                 # Tài liệu hướng dẫn (file này)
├── Server.py                 # Server RTSP chính
├── ServerWorker.py           # Xử lý kết nối client (chạy trên thread riêng)
├── Client.py                 # Client GUI chính
├── ClientLauncher.py         # Chương trình khởi động Client
├── RtpPacket.py              # Lớp đóng gói/giải nén gói RTP
├── VideoStream.py            # Lớp đọc stream video từ file
└── movie.Mjpeg               # File video MJPEG mẫu
```

---

## 🔧 Yêu Cầu Hệ Thống

### Phần Mềm Cần Cài
- **Python 3.6+** (khuyến nghị 3.8 trở lên)
- **Tkinter** (thường có sẵn với Python)
- **Pillow (PIL)** - Thư viện xử lý ảnh

### Cài Đặt Thư Viện
```bash
pip install pillow
```

### Kiểm Tra Cài Đặt
```bash
# Kiểm tra Python
python --version

# Kiểm tra Tkinter (chạy trên Python)
python -m tkinter

# Kiểm tra Pillow
python -c "from PIL import Image; print('Pillow OK')"
```

---

## 🚀 Hướng Dẫn Sử Dụng

### Bước 1: Chuẩn Bị File Video
Đảm bảo bạn có một file video MJPEG. Format file phải:
- Có phần mở rộng `.Mjpeg`
- Mỗi frame được lưu dạng JPEG
- Tên tệp được ghi trước với chiều dài (5 ký tự)

**Ví dụ:** Nếu frame có kích thước 1024 byte, tệp sẽ có: `01024` + dữ liệu JPEG

### Bước 2: Khởi Động Server

Mở **Terminal/Command Prompt** và chạy:

```bash
python Server.py 6000
```

**Giải thích:**
- `Server.py` - Chương trình server
- `6000` - Cổng RTSP (có thể thay đổi, khuyến nghị từ 1024-65535)

**Kết quả mong đợi:**
```
Server lắng nghe trên cổng 6000...
```

### Bước 3: Khởi Động Client

Mở **Terminal/Command Prompt** mới (trong cùng thư mục) và chạy:

```bash
python ClientLauncher.py localhost 6000 5004 movie.Mjpeg
```

**Giải thích tham số:**
| Tham số | Ý Nghĩa | Ví Dụ |
|--------|---------|-------|
| `localhost` | Địa chỉ server | `192.168.1.5` hoặc `localhost` |
| `6000` | Cổng RTSP của server | Phải khớp với server |
| `5004` | Cổng RTP của client | Có thể là cổng bất kỳ |
| `movie.Mjpeg` | Tên file video | Đường dẫn tương đối hoặc tuyệt đối |

### Bước 4: Điều Khiển Video trong GUI

Cửa sổ Client sẽ xuất hiện với 4 nút:

| Nút | Chức Năng | Mô Tả |
|-----|----------|-------|
| **Setup** | Thiết lập kết nối | Khởi tạo phiên làm việc với server |
| **Play** | Phát video | Bắt đầu phát video từ server |
| **Pause** | Tạm dừng | Dừng phát, có thể tiếp tục |
| **Teardown** | Ngắt kết nối | Đóng kết nối và thoát ứng dụng |

---

## 📡 Luồng Giao Tiếp (Communication Flow)

### Quy Trình Kết Nối

```
CLIENT                              SERVER
  |                                    |
  |--- SETUP Request (RTSP) --------->|
  |                                    |
  |<--- 200 OK Response ---|           |
  |                        |           |
  |         [Session ID được tạo]      |
  |                        |           |
  |--- PLAY Request (RTSP) --------->|
  |                                    |
  |<--- 200 OK Response ---|           |
  |                        |           |
  |      [RTP Packets được gửi trên UDP]
  |<--- RTP Packets (UDP) <---------|  |
  |<--- RTP Packets (UDP) <---------|  |
  |         ...                        |
  |                                    |
  |--- PAUSE Request (RTSP) -------->|
  |<--- 200 OK Response <---------|   |
  |                                    |
  |--- TEARDOWN Request (RTSP) ----->|
  |<--- 200 OK Response <---------|   |
  |                                    |
```

### Các Giai Đoạn (States)

Cả client và server đều quản lý trạng thái kết nối:

```
INIT ──SETUP──> READY ──PLAY──> PLAYING
               (Ready)           (Phát)
                 ^                 |
                 |___PAUSE________|
                 
TEARDOWN → INIT (Kết thúc)
```

---

## 📚 Chi Tiết Các File

### 1. **Server.py** - Server RTSP Chính

```python
python Server.py <port>
```

**Chức năng:**
- Khởi tạo socket RTSP (TCP)
- Lắng nghe kết nối từ client (port mặc định: 6000)
- Tạo thread mới cho mỗi client kết nối
- Chuyển giao cho `ServerWorker` xử lý

**Dòng chảy:**
1. Tạo socket TCP
2. Bind vào port
3. Lắng nghe kết nối (loop vô hạn)
4. Khi client kết nối → tạo `ServerWorker` trên thread mới

---

### 2. **ServerWorker.py** - Xử Lý Kết Nối Client

**Chức năng:**
- Nhận và xử lý yêu cầu RTSP từ client
- Quản lý trạng thái phiên làm việc (INIT → READY → PLAYING)
- Gửi RTP packets chứa video stream
- Tạo thread riêng để gửi RTP data

**Xử lý Yêu Cầu RTSP:**

| Yêu Cầu | Từ Trạng Thái | Đến Trạng Thái | Hành Động |
|---------|-------------|--|-----------|
| **SETUP** | INIT | READY | Tạo VideoStream, tạo Session ID |
| **PLAY** | READY | PLAYING | Bắt đầu gửi RTP packets |
| **PAUSE** | PLAYING | READY | Dừng gửi RTP packets |
| **TEARDOWN** | Bất kỳ | INIT | Đóng kết nối, giải phóng tài nguyên |

**Định Dạng RTSP Request:**
```
SETUP movie.Mjpeg RTSP/1.0
CSeq: 1
Transport: RTP/UDP; client_port=5004
```

**Định Dạng RTSP Response:**
```
RTSP/1.0 200 OK
CSeq: 1
Session: 123456
```

---

### 3. **Client.py** - Client GUI

**Chức năng chính:**
- Tạo giao diện Tkinter (buttons, label hiển thị video)
- Kết nối tới server qua RTSP
- Gửi yêu cầu RTSP (SETUP, PLAY, PAUSE, TEARDOWN)
- Nhận RTP packets qua UDP
- Giải nén ảnh JPEG từ RTP packets và hiển thị

**Các State:**
- `INIT` - Chưa kết nối
- `READY` - Đã setup, sẵn sàng phát
- `PLAYING` - Đang phát video

**Luồng Phát Video:**
1. Nhấn "Setup" → Gửi RTSP SETUP
2. Nhấn "Play" → Gửi RTSP PLAY, bắt đầu listen RTP trên thread mới
3. Thread `listenRtp()` nhận RTP packets
4. Mỗi packet được giải nén → ghi vào cache file → hiển thị lên GUI
5. Nhấn "Pause" → Gửi RTSP PAUSE
6. Nhấn "Teardown" → Ngắt kết nối

**Tệp Cache:**
- Format: `cache-<SESSION_ID>.jpg`
- Ví dụ: `cache-123456.jpg`
- Được tạo tạm thời để lưu frame hiện tại

---

### 4. **RtpPacket.py** - Đóng Gói/Giải Nén RTP

**Cấu Trúc RTP Header (12 bytes):**

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|V=2|P|X|  CC   |M|     PT      |       sequence number         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                           timestamp                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|           synchronization source (SSRC) identifier            |
+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
```

**Các Trường:**
- **V** (2 bits) - Phiên bản = 2
- **P** (1 bit) - Padding = 0
- **X** (1 bit) - Extension = 0
- **CC** (4 bits) - CSRC count = 0
- **M** (1 bit) - Marker = 0
- **PT** (7 bits) - Payload Type = 26 (MJPEG)
- **Sequence** (16 bits) - Số thứ tự frame
- **Timestamp** (32 bits) - Thời gian
- **SSRC** (32 bits) - ID nguồn

**Phương Thức:**

| Phương Thức | Ý Nghĩa |
|------------|---------|
| `encode()` | Đóng gói dữ liệu thành RTP packet |
| `decode()` | Giải nén RTP packet |
| `seqNum()` | Lấy số thứ tự frame |
| `getPayload()` | Lấy dữ liệu video (JPEG) |
| `getPacket()` | Lấy toàn bộ packet (header + payload) |

---

### 5. **VideoStream.py** - Đọc Stream Video

**Chức năng:**
- Mở file MJPEG
- Đọc từng frame liên tiếp
- Theo dõi số frame đã đọc

**Format File MJPEG:**
```
[5 ký tự chiều dài][JPEG data][5 ký tự chiều dài][JPEG data]...
```

Ví dụ:
```
00512[JPEG 512 bytes]01024[JPEG 1024 bytes]...
```

**Phương Thức:**

| Phương Thức | Ý Nghĩa |
|------------|---------|
| `nextFrame()` | Đọc frame tiếp theo |
| `frameNbr()` | Trả về số frame hiện tại |

---

### 6. **ClientLauncher.py** - Chương Trình Khởi Động

**Chức năng:**
- Nhận tham số từ command line
- Khởi tạo Tkinter root window
- Tạo Client object
- Khởi chạy GUI main loop

**Tham số:**
```bash
python ClientLauncher.py <server_addr> <server_port> <rtp_port> <video_file>
```

---

## 🎓 Khái Niệm Quan Trọng

### 1. **RTSP (Real-Time Streaming Protocol)**
- Giao thức **điều khiển** phát video (như điều khiển DVD)
- Sử dụng **TCP** (kết nối đáng tin cậy)
- Các lệnh: SETUP, PLAY, PAUSE, TEARDOWN
- Chạy trên cổng mặc định 554

### 2. **RTP (Real-Time Transport Protocol)**
- Giao thức **vận chuyển** dữ liệu video
- Sử dụng **UDP** (nhanh, nhưng có thể mất packet)
- Thích hợp cho truyền phát trực tiếp
- Header nhỏ, overhead thấp

### 3. **MJPEG (Motion JPEG)**
- Định dạng video = chuỗi ảnh JPEG
- Mỗi frame là một ảnh JPEG độc lập
- Dễ xử lý nhưng cần băng thông lớn
- Thích hợp cho các ứng dụng giám sát

### 4. **Threading (Xử Lý Đa Luồng)**
- Server tạo thread mới cho mỗi client (xử lý song song)
- Client sử dụng thread để listen RTP (không block GUI)
- Tránh "ứng dụng không phản hồi"

### 5. **Socket Programming**
- **TCP Socket** (RTSP): kết nối ổn định, order đảm bảo
- **UDP Socket** (RTP): nhanh, không cần kết nối, có thể mất packet

---

## ⚙️ Tham Số Cấu Hình

### Server Port (RTSP)
- **Khuyến nghị:** 6000-9000
- **Mặc định:** 6000
- Phải khớp giữa client và server

### Client Port (RTP)
- **Khuyến nghị:** 5000-6000
- **Mặc định:** 5004
- Có thể bất kỳ (miễn sao không bị chiếm)

### Kích Thước Buffer
- RTP receive buffer: 20480 bytes
- RTSP command buffer: 1024 bytes
- Tăng nếu video chất lượng cao

---

## 🔍 Gỡ Lỗi (Troubleshooting)

### ❌ Lỗi: "Cannot connect to server"
**Nguyên nhân:**
- Server chưa chạy
- IP/port không đúng
- Tường lửa chặn

**Giải pháp:**
```bash
# Kiểm tra server đang chạy
netstat -an | findstr 6000

# Kiểm tra kết nối
ping localhost
```

### ❌ Lỗi: "Unable to bind PORT"
**Nguyên nhân:**
- Port đã bị sử dụng
- Quyền hạn không đủ

**Giải pháp:**
```bash
# Sử dụng port khác
python ClientLauncher.py localhost 6000 5005 movie.Mjpeg
```

### ❌ Lỗi: "IOError" khi mở video
**Nguyên nhân:**
- File video không tồn tại
- Đường dẫn sai
- Định dạng không hỗ trợ

**Giải pháp:**
```bash
# Kiểm tra file tồn tại
dir movie.Mjpeg

# Sử dụng đường dẫn tuyệt đối
python ClientLauncher.py localhost 6000 5004 "C:\path\to\movie.Mjpeg"
```

### ❌ Lỗi: Video không hiển thị
**Nguyên nhân:**
- Packet RTP bị mất
- Thread receiver bị treo
- File cache bị xóa

**Giải pháp:**
- Kiểm tra logs (console)
- Bật chế độ debug
- Kiểm tra file cache được tạo: `cache-*.jpg`

---

## 📊 Hiệu Suất

### Tốc Độ Dữ Liệu (Bitrate)

**Ví dụ tính toán:**
```
Frame size: 1024 bytes
FPS (Frames Per Second): 20
Bitrate = 1024 × 20 × 8 bits = 163,840 bps ≈ 160 kbps
```

### Độ Trễ (Latency)
- **RTSP Setup:** ~100-500ms
- **RTP transmission:** ~50-200ms
- **Total:** ~200-700ms

---

## 🛠️ Mở Rộng Dự Án

### Ý Tưởng Cải Tiến:

1. **Hỗ trợ Video Codec Khác**
   - Thêm H.264, H.265
   - Thêm VP8, VP9

2. **Nén Dữ Liệu**
   - Giảm quality JPEG
   - Xóa các frame không thay đổi

3. **Điều Chỉnh Tốc Độ**
   - Thêm control FPS
   - Adaptive bitrate

4. **Đo Lường Chất Lượng**
   - Thêm packet loss counter
   - Thêm latency monitor

5. **Hỗ Trợ Nhiều Client**
   - Load balancing
   - Session management

6. **Bảo Mật**
   - RTSP authentication
   - Mã hóa RTP

---

## 📝 Ví Dụ Chạy Ứng Dụng

### Terminal 1 - Chạy Server:
```bash
C:\project> python Server.py 6000
```

### Terminal 2 - Chạy Client:
```bash
C:\project> python ClientLauncher.py localhost 6000 5004 movie.Mjpeg
```

**Kết quả mong đợi:**

**Server Console:**
```
Data received:
SETUP movie.Mjpeg RTSP/1.0
CSeq: 1
Transport: RTP/UDP; client_port=5004

processing SETUP

Data received:
PLAY movie.Mjpeg RTSP/1.0
CSeq: 2
Session: 123456

processing PLAY
```

**Client GUI:**
- Xuất hiện cửa sổ với 4 nút
- Video hiển thị trong vùng label
- Frame counter cập nhật

---

## 📖 Tài Liệu Tham Khảo

### RFC Standards:
- **RFC 3550** - RTP (Real-Time Transport Protocol)
- **RFC 7826** - RTSP (Real-Time Streaming Protocol)
- **RFC 2435** - RTP Payload Format for JPEG-Compressed Video

### Python Docs:
- [socket — Low-level networking interface](https://docs.python.org/3/library/socket.html)
- [threading — Thread-based parallelism](https://docs.python.org/3/library/threading.html)
- [tkinter — Python interface to Tcl/Tk](https://docs.python.org/3/library/tkinter.html)
- [PIL/Pillow Documentation](https://pillow.readthedocs.io/)

---

## 📞 Hỗ Trợ

Nếu gặp vấn đề:
1. Kiểm tra logs/console output
2. Xác minh tất cả file có mặt
3. Kiểm tra phiên bản Python (3.6+)
4. Kiểm tra thư viện đã cài đặt (`pip list`)

---

## 📄 Giấy Phép

Dự án này được sử dụng cho mục đích học tập.

---

**Tác Giả:** Dự án hướng dẫn  
**Ngày cập nhật:** 2025  
**Phiên bản:** 1.0

