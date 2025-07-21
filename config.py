import os

class Config:
    """基础配置类"""
    # 数据库配置 - 使用SQLite
    SQLALCHEMY_DATABASE_URI = 'sqlite:///yolo_detection.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask配置
    SECRET_KEY = 'yolo-detection-secret-key-2024'
    DEBUG = True
    
    # 文件上传配置
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    
    # YOLO模型配置
    YOLO_MODEL_PATH = 'yolov8n.pt'  # 默认使用YOLOv8n模型
    DETECTION_CONFIDENCE = 0.25  # 检测置信度阈值

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-production-secret-key-here')

class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
} 