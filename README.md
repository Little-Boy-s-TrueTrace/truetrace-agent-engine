# TrueTrace Multi-Agent Engine

Runtime Python bất đồng bộ điều phối ba agent tuân thủ:

- Deepfake Inspector xử lý KYC, CCCD, Alibaba vision/eKYC và identity registry.
- Money-Trail Explorer phân tích đồ thị giao dịch theo cửa sổ trượt, đóng băng tài
  khoản có rủi ro cao và tạo AML alert.
- AML Reporter dùng Qwen soạn STR song ngữ ở trạng thái nháp để người thật duyệt.

## Chạy kiểm thử

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

## Chạy local

Engine cần Kafka và backend TrueTrace:

```bash
python main.py
```

Health endpoint: `GET http://localhost:8080/health`.

## Chế độ AI

Mặc định là `demo`, chạy offline và trả kết quả xác định để demo/test. Không dùng
kết quả demo như một phán quyết gian lận.

Alibaba Model Studio:

```dotenv
VISION_API_PROVIDER=alibaba-model-studio
VISION_API_KEY=...
VISION_API_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
VISION_MODEL=qwen-vl-plus

LLM_PROVIDER=dashscope
LLM_API_KEY=...
LLM_API_ENDPOINT=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

Alibaba eKYC gateway:

```dotenv
VISION_API_PROVIDER=alibaba-ekyc
VISION_API_ENDPOINT=https://your-normalizing-gateway.example/deepfake
VISION_API_KEY=...
```

Gateway phải trả các trường chuẩn hóa `deepfake_probability`,
`face_match_score`, `liveness_score`, `signals` và `details`.

Đối chiếu CCCD quốc gia là integration giả định và chỉ được gọi khi cấu hình:

```dotenv
IDENTITY_REGISTRY_ENDPOINT=https://registry-gateway.example/verify
IDENTITY_REGISTRY_API_KEY=...
```

## Ngưỡng rapid mule mặc định

- nhận tối thiểu 1 tỷ VND;
- chuyển tới tối thiểu 20 tài khoản;
- trong 60 giây;
- tổng tiền đi tối thiểu 80% tiền vào;
- risk score từ 7/10 sẽ tạo freeze + alert + STR draft.

Mọi ngưỡng đều có biến môi trường tương ứng trong
`truetrace-deployment/.env.example`.
