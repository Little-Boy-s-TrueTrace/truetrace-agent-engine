import os

class Config:
    ENVIRONMENT = os.getenv('TRUETRACE_ENV', 'demo').strip().lower()
    # Kafka
    KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
    KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'truetrace-engine')
    KAFKA_MAX_MESSAGE_BYTES = int(os.getenv('KAFKA_MAX_MESSAGE_BYTES', '10485760'))
    
    # Kafka Topics
    TOPIC_KYC_SUBMISSIONS = 'truetrace.kyc.submissions'
    TOPIC_TRANSACTIONS = 'truetrace.transactions'
    TOPIC_FINDINGS_DEEPFAKE = 'truetrace.findings.deepfake'
    TOPIC_FINDINGS_MONEY_TRAIL = 'truetrace.findings.money_trail'
    TOPIC_REPORTS_STR = 'truetrace.reports.str'
    TOPIC_ALERTS = 'truetrace.alerts'
    
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    
    # Backend API
    BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8080')
    
    # Vision API
    VISION_API_PROVIDER = os.getenv('VISION_API_PROVIDER', 'demo')  # demo, alibaba-model-studio, alibaba-ekyc
    VISION_API_KEY = os.getenv('VISION_API_KEY', '')
    VISION_API_ENDPOINT = os.getenv(
        'VISION_API_ENDPOINT',
        'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
    )
    VISION_MODEL = os.getenv('VISION_MODEL', 'qwen-vl-plus')
    IDENTITY_REGISTRY_ENDPOINT = os.getenv('IDENTITY_REGISTRY_ENDPOINT', '')
    IDENTITY_REGISTRY_API_KEY = os.getenv('IDENTITY_REGISTRY_API_KEY', '')
    VISION_TIMEOUT_SECONDS = float(os.getenv('VISION_TIMEOUT_SECONDS', '20'))
    MAX_IMAGE_BYTES = int(os.getenv('MAX_IMAGE_BYTES', str(8 * 1024 * 1024)))
    DEEPFAKE_REVIEW_THRESHOLD = float(os.getenv('DEEPFAKE_REVIEW_THRESHOLD', '0.50'))
    DEEPFAKE_REJECT_THRESHOLD = float(os.getenv('DEEPFAKE_REJECT_THRESHOLD', '0.80'))
    
    # LLM
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'demo')  # demo, dashscope
    LLM_API_KEY = os.getenv('LLM_API_KEY', '')
    LLM_MODEL = os.getenv('LLM_MODEL', 'qwen-plus')
    LLM_API_ENDPOINT = os.getenv(
        'LLM_API_ENDPOINT',
        'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
    )
    LLM_TIMEOUT_SECONDS = float(os.getenv('LLM_TIMEOUT_SECONDS', '25'))
    
    # Database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_NAME = os.getenv('DB_NAME', 'truetrace')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
    INTERNAL_API_TOKEN = os.getenv('TRUETRACE_SECURITY_SYNC_TOKEN', '')
    
    # Agent thresholds
    MONEY_TRAIL_FREEZE_THRESHOLD = float(os.getenv('MONEY_TRAIL_FREEZE_THRESHOLD', '7.0'))
    MONEY_TRAIL_WINDOW_SECONDS = int(os.getenv('MONEY_TRAIL_WINDOW_SECONDS', '60'))
    FAN_OUT_MIN_TARGETS = int(os.getenv('FAN_OUT_MIN_TARGETS', '20'))
    RAPID_MOVEMENT_MIN_INFLOW_VND = int(os.getenv('RAPID_MOVEMENT_MIN_INFLOW_VND', '1000000000'))
    RAPID_MOVEMENT_RATIO = float(os.getenv('RAPID_MOVEMENT_RATIO', '0.80'))
    STRUCTURING_THRESHOLD_VND = int(os.getenv('STRUCTURING_THRESHOLD_VND', '200000000'))

    @classmethod
    def validate_runtime(cls):
        """Fail closed when a production process still uses demo credentials/providers."""
        if cls.ENVIRONMENT != 'production':
            return

        errors = []
        if cls.VISION_API_PROVIDER not in {'alibaba-model-studio', 'alibaba-ekyc'}:
            errors.append('VISION_API_PROVIDER must use an Alibaba production provider')
        if not cls.VISION_API_KEY:
            errors.append('VISION_API_KEY is required')
        if not cls.IDENTITY_REGISTRY_ENDPOINT or not cls.IDENTITY_REGISTRY_API_KEY:
            errors.append('IDENTITY_REGISTRY_ENDPOINT and IDENTITY_REGISTRY_API_KEY are required')
        if cls.LLM_PROVIDER != 'dashscope' or not cls.LLM_API_KEY:
            errors.append('LLM_PROVIDER=dashscope and LLM_API_KEY are required')
        if len(cls.INTERNAL_API_TOKEN) < 32:
            errors.append('TRUETRACE_SECURITY_SYNC_TOKEN must contain at least 32 characters')
        if cls.DB_PASSWORD in {'', 'postgres', 'password'}:
            errors.append('DB_PASSWORD must not use a demo/default value')
        if cls.KAFKA_BOOTSTRAP.startswith('localhost'):
            errors.append('KAFKA_BOOTSTRAP must target production infrastructure')
        if cls.REDIS_HOST in {'localhost', '127.0.0.1'}:
            errors.append('REDIS_HOST must target production infrastructure')

        if errors:
            raise RuntimeError(
                'Production configuration rejected: ' + '; '.join(errors)
            )
