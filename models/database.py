from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DetectionResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    detection_type = db.Column(db.String(20), nullable=False)  # image, video, camera, rtsp
    original_file = db.Column(db.String(255))
    result_file = db.Column(db.String(255))
    detections = db.Column(db.Text)  # JSON格式的检测结果
    confidence = db.Column(db.Float)
    # 新增字段用于跟踪和计数
    tracking_enabled = db.Column(db.Boolean, default=False)
    tracking_results = db.Column(db.Text)  # JSON格式的跟踪结果
    counting_enabled = db.Column(db.Boolean, default=False)
    counting_class = db.Column(db.String(50))  # 计数的目标类别
    counting_results = db.Column(db.Text)  # JSON格式的计数结果
    total_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AlertRecord(db.Model):
    """预警记录表"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    detection_result_id = db.Column(db.Integer, db.ForeignKey('detection_result.id'), nullable=True)
    alert_type = db.Column(db.String(20), default='new_target')  # 预警类型：new_target(新目标出现)
    target_id = db.Column(db.Integer, nullable=False)  # 触发预警的目标ID
    target_class = db.Column(db.String(50), nullable=False)  # 目标类别
    frame_number = db.Column(db.Integer, nullable=True)  # 视频帧号（如果是视频）
    frame_image = db.Column(db.String(255), nullable=False)  # 预警帧图像文件路径
    bbox = db.Column(db.Text)  # JSON格式的边界框坐标
    confidence = db.Column(db.Float)  # 检测置信度
    description = db.Column(db.Text)  # 预警描述
    is_handled = db.Column(db.Boolean, default=False)  # 是否已处理
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RTSPStream(db.Model):
    """RTSP流配置表"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # 流名称
    url = db.Column(db.String(500), nullable=False)  # RTSP地址
    username = db.Column(db.String(100))  # RTSP用户名
    password = db.Column(db.String(100))  # RTSP密码
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    detection_enabled = db.Column(db.Boolean, default=True)  # 是否启用检测
    model_path = db.Column(db.String(255), default='yolov8n.pt')  # 使用的模型
    tracking_enabled = db.Column(db.Boolean, default=False)  # 是否启用跟踪
    counting_enabled = db.Column(db.Boolean, default=False)  # 是否启用计数
    alert_enabled = db.Column(db.Boolean, default=False)  # 是否启用预警
    position_x = db.Column(db.Integer, default=0)  # 在四宫格中的X位置
    position_y = db.Column(db.Integer, default=0)  # 在四宫格中的Y位置
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 