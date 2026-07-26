import os

class Config:
    # Kafka
    KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
    KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'truetrace-engine')
    
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
    VISION_API_PROVIDER = os.getenv('VISION_API_PROVIDER', 'mock')  # mock, alibaba, azure
    VISION_API_KEY = os.getenv('VISION_API_KEY', '')
    VISION_API_ENDPOINT = os.getenv('VISION_API_ENDPOINT', '')
    
    # LLM
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'mock')  # mock, bedrock, dashscope, openai
    LLM_API_KEY = os.getenv('LLM_API_KEY', '')
    LLM_MODEL = os.getenv('LLM_MODEL', 'qwen-plus')
    
    # Database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_NAME = os.getenv('DB_NAME', 'truetrace')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
    
    # Agent thresholds
    MONEY_TRAIL_FREEZE_THRESHOLD = float(os.getenv('MONEY_TRAIL_FREEZE_THRESHOLD', '7.0'))
    MONEY_TRAIL_WINDOW_SECONDS = int(os.getenv('MONEY_TRAIL_WINDOW_SECONDS', '600'))
    FAN_OUT_MIN_TARGETS = int(os.getenv('FAN_OUT_MIN_TARGETS', '5'))
    STRUCTURING_THRESHOLD_VND = int(os.getenv('STRUCTURING_THRESHOLD_VND', '200000000'))
