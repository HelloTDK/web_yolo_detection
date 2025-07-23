from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import cv2
import numpy as np

# 强制使用CPU，避免CUDA问题
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

# 设置OpenCV线程数，优化CPU性能
cv2.setNumThreads(4)

try:
    import torch
    # 强制PyTorch使用CPU
    if torch.cuda.is_available():
        print("检测到CUDA，但强制使用CPU以避免兼容性问题")
    torch.set_num_threads(4)
    device = torch.device('cpu')
except ImportError:
    print("PyTorch未安装，将使用基础图像处理功能")

from ultralytics import YOLO
import base64
import io
from PIL import Image
from datetime import datetime
import json
from collections import defaultdict, deque
import time
from yolo_seg_handler import YOLOSegmentationHandler
from watermark_detector import (
    watermark_detector, 
    load_watermark_detector, 
    detect_watermarks_in_image,
    get_watermark_detector_info
)

app = Flask(__name__)
CORS(app)

# 简化的配置 - 使用SQLite数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///yolo_detection.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['SECRET_KEY'] = 'yolo-detection-secret-key-2024'

db = SQLAlchemy(app)

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)

# 数据库模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DetectionResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    detection_type = db.Column(db.String(20), nullable=False)  # image, video, camera
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

# 初始化YOLO模型
model = None
seg_handler = None
current_model_path = 'yolov8n.pt'  # 当前加载的模型路径
current_model_type = 'detection'  # 'detection' 或 'segmentation'

def load_yolo_model(model_path='yolov8n.pt'):
    global model, seg_handler, current_model_path, current_model_type
    try:
        # 判断是否为分割模型
        if 'seg' in model_path.lower():
            # 加载分割模型
            seg_handler = YOLOSegmentationHandler(model_path)
            if seg_handler.model:
                current_model_type = 'segmentation'
                model = seg_handler.model  # 保持兼容性
                current_model_path = model_path
                print(f"✅ YOLO分割模型加载成功: {model_path}")
                return True
            else:
                return False
        else:
            # 加载普通检测模型
            model = YOLO(model_path)
            seg_handler = None
            current_model_type = 'detection'
            current_model_path = model_path
            print(f"✅ YOLO检测模型加载成功: {model_path}")
            return True
    except Exception as e:
        print(f"❌ YOLO模型加载失败: {e}")
        return False

# 跟踪器和计数器类
class ObjectTracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 1
        self.max_disappeared = 3  # 全帧检测模式下，减少消失帧数但保持稳定
        self.max_distance = 80  # 适中的距离阈值，平衡准确性和稳定性
        self.counting_class = None
        self.detection_history = []  # 添加检测历史记录
        
        # 新增累积计数功能
        self.cumulative_ids = set()  # 记录所有出现过的ID
        self.cumulative_counts_by_class = defaultdict(set)  # 按类别记录出现过的ID
        
        # 新增预警功能
        self.alert_enabled = False  # 是否启用预警
        self.new_targets_this_frame = []  # 当前帧新出现的目标
        
    def set_counting_class(self, class_name):
        """设置需要计数的类别"""
        self.counting_class = class_name
    
    def set_alert_enabled(self, enabled):
        """设置是否启用预警"""
        self.alert_enabled = enabled
    
    def get_new_targets(self):
        """获取当前帧新出现的目标"""
        return self.new_targets_this_frame.copy()
    
    def clear_new_targets(self):
        """清空新目标记录"""
        self.new_targets_this_frame = []
        
    def calculate_centroid(self, bbox):
        """计算边界框的中心点"""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)
        
    def calculate_distance(self, point1, point2):
        """计算两点之间的欧几里得距离"""
        return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
    
    def _filter_stable_detections(self, detections):
        """过滤稳定的检测结果，减少闪烁"""
        if not detections:
            return detections
            
        filtered_detections = []
        for detection in detections:
            # 过滤条件：置信度 >= 0.5 且 框的面积 >= 最小面积
            bbox = detection['bbox']
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            area = width * height
            
            # 过滤条件
            if (detection['confidence'] >= 0.5 and 
                area >= 1000 and  # 最小面积阈值
                width >= 20 and height >= 20):  # 最小尺寸阈值
                filtered_detections.append(detection)
                
        return filtered_detections
        
    def update(self, detections, frame_height):
        """更新跟踪器"""
        # 清空上一帧的新目标记录
        self.new_targets_this_frame = []
        
        # 清理消失太久的轨迹
        self._cleanup_disappeared_tracks()
        
        # 过滤稳定的检测结果，减少闪烁
        stable_detections = self._filter_stable_detections(detections)
        
        if not stable_detections:
            # 如果没有稳定的检测结果，增加所有轨迹的消失计数
            for track_id in self.tracks:
                self.tracks[track_id]['disappeared'] += 1
            return self.get_current_tracks()
        
        # 为每个检测结果计算中心点
        detection_centroids = []
        for detection in stable_detections:
            centroid = self.calculate_centroid(detection['bbox'])
            detection_centroids.append({
                'centroid': centroid,
                'detection': detection
            })
        
        # 如果没有现有轨迹，创建新轨迹
        if not self.tracks:
            for detection_info in detection_centroids:
                self._create_new_track(detection_info)
        else:
            # 匹配检测结果到现有轨迹
            self._match_detections_to_tracks(detection_centroids, frame_height)
        
        return self.get_current_tracks()
    
    def _cleanup_disappeared_tracks(self):
        """清理消失太久的轨迹"""
        disappeared_ids = []
        for track_id in self.tracks:
            if self.tracks[track_id]['disappeared'] > self.max_disappeared:
                disappeared_ids.append(track_id)
        
        for track_id in disappeared_ids:
            del self.tracks[track_id]
    
    def _create_new_track(self, detection_info):
        """创建新轨迹"""
        detection = detection_info['detection']
        centroid = detection_info['centroid']
        
        # 限制最大轨迹数量，防止轨迹爆炸
        if len(self.tracks) >= 50:  # 最多同时跟踪50个目标
            return
        
        track_id = self.next_id
        self.tracks[track_id] = {
            'centroid': centroid,
            'disappeared': 0,
            'bbox': detection['bbox'],
            'class': detection['class'],
            'confidence': detection['confidence'],
            'history': deque([centroid], maxlen=10)
        }
        
        # 记录累积计数
        self.cumulative_ids.add(track_id)
        self.cumulative_counts_by_class[detection['class']].add(track_id)
        
        # 如果启用预警，记录新目标
        if self.alert_enabled:
            new_target = {
                'id': track_id,
                'class': detection['class'],
                'confidence': detection['confidence'],
                'bbox': detection['bbox'],
                'centroid': centroid
            }
            self.new_targets_this_frame.append(new_target)
        
        self.next_id += 1
    
    def _match_detections_to_tracks(self, detection_centroids, frame_height):
        """匹配检测结果到现有轨迹"""
        if not detection_centroids:
            return
        
        # 获取当前轨迹信息
        track_centroids = []
        track_ids = []
        
        for track_id, track in self.tracks.items():
            track_centroids.append(track['centroid'])
            track_ids.append(track_id)
        
        # 计算距离矩阵
        distance_matrix = np.zeros((len(track_centroids), len(detection_centroids)))
        
        for i, track_centroid in enumerate(track_centroids):
            for j, detection_info in enumerate(detection_centroids):
                distance = self.calculate_distance(track_centroid, detection_info['centroid'])
                distance_matrix[i][j] = distance
        
        # 使用匈牙利算法或简单的贪心匹配
        used_detection_indices = set()
        used_track_indices = set()
        
        # 按距离排序进行匹配
        matches = []
        for i in range(len(track_centroids)):
            for j in range(len(detection_centroids)):
                if distance_matrix[i][j] < self.max_distance:
                    matches.append((i, j, distance_matrix[i][j]))
        
        # 按距离排序，优先匹配最近的
        matches.sort(key=lambda x: x[2])
        
        # 应用匹配
        for track_idx, detection_idx, distance in matches:
            if track_idx not in used_track_indices and detection_idx not in used_detection_indices:
                track_id = track_ids[track_idx]
                detection_info = detection_centroids[detection_idx]
                detection = detection_info['detection']
                centroid = detection_info['centroid']
                
                # 更新轨迹
                self.tracks[track_id]['centroid'] = centroid
                self.tracks[track_id]['disappeared'] = 0
                self.tracks[track_id]['bbox'] = detection['bbox']
                self.tracks[track_id]['class'] = detection['class']
                self.tracks[track_id]['confidence'] = detection['confidence']
                self.tracks[track_id]['history'].append(centroid)
                
                # 更新累积计数（如果类别发生变化）
                self.cumulative_ids.add(track_id)
                self.cumulative_counts_by_class[detection['class']].add(track_id)
                
                used_track_indices.add(track_idx)
                used_detection_indices.add(detection_idx)
        
        # 为未匹配的检测结果创建新轨迹
        for j, detection_info in enumerate(detection_centroids):
            if j not in used_detection_indices:
                self._create_new_track(detection_info)
        
        # 增加未匹配轨迹的消失计数
        for i, track_id in enumerate(track_ids):
            if i not in used_track_indices:
                self.tracks[track_id]['disappeared'] += 1
    
    def get_current_tracks(self):
        """获取当前活跃的轨迹（只返回未消失的轨迹）"""
        tracking_results = []
        for track_id, track in self.tracks.items():
            # 只返回未消失的轨迹
            if track['disappeared'] == 0:
                tracking_results.append({
                    'id': track_id,
                    'bbox': track['bbox'],
                    'class': track['class'],
                    'confidence': track['confidence'],
                    'centroid': track['centroid']
                })
        return tracking_results
    
    def get_current_counts(self):
        """获取当前屏幕内的目标数量统计"""
        counts = defaultdict(int)
        for track_id, track in self.tracks.items():
            if track['disappeared'] == 0:  # 只统计当前活跃的轨迹
                counts[track['class']] += 1
        return dict(counts)
    
    def get_cumulative_counts(self):
        """获取累积计数统计（从视频开始到现在总共出现过的不同ID数量）"""
        counts = {}
        for class_name, id_set in self.cumulative_counts_by_class.items():
            counts[class_name] = len(id_set)
        return counts
    
    def get_total_count(self, class_name=None):
        """获取累积总数量（从视频开始到现在总共出现过的不同ID数量）"""
        cumulative_counts = self.get_cumulative_counts()
        if class_name:
            return cumulative_counts.get(class_name, 0)
        return sum(cumulative_counts.values())
    
    def get_current_screen_count(self, class_name=None):
        """获取当前屏幕内的数量（用于实时显示）"""
        counts = self.get_current_counts()
        if class_name:
            return counts.get(class_name, 0)
        return sum(counts.values())
    
    def get_count_summary(self):
        """获取完整的计数摘要"""
        return {
            'current_screen': self.get_current_counts(),
            'cumulative_total': self.get_cumulative_counts(),
            'total_unique_ids': len(self.cumulative_ids),
            'current_screen_total': self.get_current_screen_count(),
            'cumulative_total_count': self.get_total_count()
        }

# 全局跟踪器实例
tracker = ObjectTracker()

def save_alert_frame(frame, user_id, target_info, frame_number=None, detection_result_id=None):
    """保存预警帧到文件和数据库"""
    try:
        # 确保预警目录存在
        alert_dir = os.path.join('static', 'alerts')
        os.makedirs(alert_dir, exist_ok=True)
        
        # 生成预警帧文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 精确到毫秒
        filename = f'alert_{timestamp}_id{target_info["id"]}.jpg'
        filepath = os.path.join(alert_dir, filename)
        
        # 在帧上绘制预警信息
        frame_copy = frame.copy()
        x1, y1, x2, y2 = target_info['bbox']
        
        # 绘制红色预警框
        cv2.rectangle(frame_copy, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 3)
        
        # 绘制预警标签
        alert_label = f'ALERT! New {target_info["class"]} ID:{target_info["id"]}'
        label_size = cv2.getTextSize(alert_label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        
        # 预警标签背景（红色）
        cv2.rectangle(frame_copy, (int(x1), int(y1) - label_size[1] - 15), 
                     (int(x1) + label_size[0] + 10, int(y1)), (0, 0, 255), -1)
        
        # 预警标签文字（白色）
        cv2.putText(frame_copy, alert_label, (int(x1) + 5, int(y1) - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 在图像顶部添加时间戳
        timestamp_text = f'Alert Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        cv2.putText(frame_copy, timestamp_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # 保存图像
        cv2.imwrite(filepath, frame_copy)
        
        # 保存到数据库
        alert_record = AlertRecord(
            user_id=user_id,
            detection_result_id=detection_result_id,
            target_id=target_info['id'],
            target_class=target_info['class'],
            frame_number=frame_number,
            frame_image=os.path.join('alerts', filename),
            bbox=json.dumps(target_info['bbox']),
            confidence=target_info['confidence'],
            description=f'新目标出现: {target_info["class"]} (ID: {target_info["id"]})',
            is_handled=False
        )
        
        db.session.add(alert_record)
        db.session.commit()
        
        print(f"🚨 预警记录已保存: {filename} - {target_info['class']} ID:{target_info['id']}")
        
        return alert_record.id
        
    except Exception as e:
        print(f"❌ 保存预警帧失败: {e}")
        db.session.rollback()
        return None

def get_model_files(directory='models'):
    """获取指定目录下的模型文件列表"""
    model_extensions = ['.pt', '.onnx', '.torchscript']
    model_files = []
    
    # 确保models目录存在
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if any(file.lower().endswith(ext) for ext in model_extensions):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    model_files.append({
                        'name': file,
                        'path': file_path,
                        'relative_path': os.path.relpath(file_path),
                        'size': file_size,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'modified': os.path.getmtime(file_path)
                    })
    except Exception as e:
        print(f"扫描模型文件时出错: {e}")
    
    # 添加预训练模型选项
    pretrained_models = [
        {'name': 'YOLOv8n (检测)', 'path': 'yolov8n.pt', 'relative_path': 'yolov8n.pt', 'size': 0, 'size_mb': 6.2, 'modified': 0, 'pretrained': True, 'type': 'detection'},
        {'name': 'YOLOv8n-seg (分割)', 'path': 'yolov8n-seg.pt', 'relative_path': 'yolov8n-seg.pt', 'size': 0, 'size_mb': 6.7, 'modified': 0, 'pretrained': True, 'type': 'segmentation'},
        {'name': 'YOLOv8s-seg (分割)', 'path': 'yolov8s-seg.pt', 'relative_path': 'yolov8s-seg.pt', 'size': 0, 'size_mb': 22.5, 'modified': 0, 'pretrained': True, 'type': 'segmentation'},
        {'name': 'YOLOv8m-seg (分割)', 'path': 'yolov8m-seg.pt', 'relative_path': 'yolov8m-seg.pt', 'size': 0, 'size_mb': 49.9, 'modified': 0, 'pretrained': True, 'type': 'segmentation'}
    ]
    
    return pretrained_models + model_files

# API路由
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        return jsonify({
            'success': True,
            'message': '登录成功',
            'user': {
                'id': user.id,
                'username': user.username
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': '用户名或密码错误'
        }), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if User.query.filter_by(username=username).first():
        return jsonify({
            'success': False,
            'message': '用户名已存在'
        }), 400
    
    user = User(username=username, password=password)
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '注册成功'
    })

@app.route('/api/detect_image', methods=['POST'])
def detect_image():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400
    
    file = request.files['file']
    user_id = request.form.get('user_id', 1)
    use_segmentation = request.form.get('use_segmentation', 'false').lower() == 'true'
    show_masks = request.form.get('show_masks', 'true').lower() == 'true'
    show_boxes = request.form.get('show_boxes', 'true').lower() == 'true'
    mask_alpha = float(request.form.get('mask_alpha', 0.4))
    
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # 根据模型类型和用户选择进行检测或分割
        try:
            img = cv2.imread(filepath)
            detections = []
            segmentation_results = None
            
            if use_segmentation and current_model_type == 'segmentation' and seg_handler:
                # 使用分割模型
                seg_results = seg_handler.predict(img)
                if seg_results:
                    result = seg_results[0]
                    segmentation_results = result
                    
                    # 转换为标准检测格式
                    for i, (box, conf, cls, cls_name) in enumerate(zip(
                        result.get('boxes', []),
                        result.get('confidences', []),
                        result.get('classes', []),
                        result.get('class_names', [])
                    )):
                        detections.append({
                            'class': cls_name,
                            'confidence': float(conf),
                            'bbox': box,
                            'has_mask': i < len(result.get('masks', []))
                        })
                    
                    # 生成可视化结果
                    img = seg_handler.visualize_segmentation(
                        img, result, show_boxes, show_masks, True, mask_alpha
                    )
                
            else:
                # 使用普通检测模型
                results = model(filepath)
                
                for r in results:
                    boxes = r.boxes
                    if boxes is not None:
                        for box in boxes:
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            conf = box.conf[0].cpu().numpy()
                            cls = box.cls[0].cpu().numpy()
                            
                            detections.append({
                                'class': model.names[int(cls)],
                                'confidence': float(conf),
                                'bbox': [float(x1), float(y1), float(x2), float(y2)],
                                'has_mask': False
                            })
                            
                            # 在图像上绘制检测框
                            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                            cv2.putText(img, f'{model.names[int(cls)]}: {conf:.2f}', 
                                      (int(x1), int(y1)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # 保存结果图像
            result_filename = 'result_' + filename
            result_filepath = os.path.join('static', result_filename)
            cv2.imwrite(result_filepath, img)
            
            # 保存到数据库
            detection_result = DetectionResult(
                user_id=user_id,
                detection_type='image',
                original_file=filename,
                result_file=result_filename,
                detections=json.dumps(detections),
                confidence=max([d['confidence'] for d in detections]) if detections else 0
            )
            db.session.add(detection_result)
            db.session.commit()
            
            response_data = {
                'success': True,
                'message': '检测完成' if not use_segmentation else '分割检测完成',
                'detections': detections,
                'result_image': f'/static/{result_filename}',
                'detection_count': len(detections),
                'model_type': current_model_type,
                'used_segmentation': use_segmentation and current_model_type == 'segmentation'
            }
            
            # 如果是分割结果，添加分割信息
            if segmentation_results:
                response_data['segmentation_results'] = {
                    'masks_count': len(segmentation_results.get('masks', [])),
                    'segments_count': len(segmentation_results.get('segments', []))
                }
            
            return jsonify(response_data)
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'检测失败: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': '不支持的文件格式'}), 400

@app.route('/api/detect_video', methods=['POST'])
def detect_video():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400
    
    file = request.files['file']
    user_id = request.form.get('user_id', 1)
    
    # 新增参数：跟踪、计数和预警设置
    enable_tracking = request.form.get('enable_tracking', 'false').lower() == 'true'
    enable_counting = request.form.get('enable_counting', 'false').lower() == 'true'
    counting_class = request.form.get('counting_class', '')
    enable_alert = request.form.get('enable_alert', 'false').lower() == 'true'
    
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    if file and allowed_video_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        original_name, original_ext = os.path.splitext(filename)
        filename = timestamp + original_name + '.mp4'  # 强制使用.mp4扩展名
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], timestamp + secure_filename(file.filename))
        file.save(filepath)
        
        try:
            # 处理视频检测
            cap = cv2.VideoCapture(filepath)
            
            # 检查视频是否成功打开
            if not cap.isOpened():
                return jsonify({'success': False, 'message': '无法打开视频文件，请检查视频格式'}), 400
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 验证视频参数
            if fps <= 0:
                fps = 25.0  # 默认帧率
            if width <= 0 or height <= 0:
                return jsonify({'success': False, 'message': '视频尺寸无效'}), 400
            
            result_filename = 'result_' + filename
            result_filepath = os.path.join('static', result_filename)
            
            # 使用浏览器兼容性更好的编码器
            # 调整编码器优先级，优先使用浏览器支持最好的编码器
            encoders = [
                ('H264', cv2.VideoWriter_fourcc(*'H264')),  # H.264 (浏览器支持最好)
                ('h264', cv2.VideoWriter_fourcc(*'h264')),  # H.264 备选
                ('avc1', cv2.VideoWriter_fourcc(*'avc1')),  # H.264 另一种格式
                ('X264', cv2.VideoWriter_fourcc(*'X264')),  # H.264 x264编码器
                ('XVID', cv2.VideoWriter_fourcc(*'XVID')),  # Xvid (广泛支持)
                ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),  # MPEG-4 Part 2 (备选)
                ('MJPG', cv2.VideoWriter_fourcc(*'MJPG')),  # Motion JPEG (兜底)
            ]
            
            out = None
            selected_encoder = None
            for encoder_name, fourcc in encoders:
                try:
                    print(f"🔧 尝试编码器: {encoder_name} ({fourcc})")
                    out = cv2.VideoWriter(result_filepath, fourcc, fps, (width, height))
                    # 测试是否能正确写入
                    if out.isOpened():
                        selected_encoder = encoder_name
                        print(f"✅ 成功使用编码器: {encoder_name} ({fourcc})")
                        break
                    else:
                        print(f"❌ 编码器 {encoder_name} 初始化失败")
                        out.release()
                        out = None
                except Exception as e:
                    print(f"❌ 编码器 {encoder_name} 出错: {e}")
                    if out:
                        out.release()
                        out = None
                    continue
            
            if out is None or not out.isOpened():
                cap.release()
                return jsonify({'success': False, 'message': '无法创建输出视频文件'}), 500
            
            all_detections = []
            all_tracking_results = []
            frame_count = 0
            processed_frames = 0
            current_detections = []  # 保存当前检测结果，在多帧之间保持
            current_tracking_results = []  # 保存当前跟踪结果
            detection_interval = 1  # 全帧检测，每帧都进行检测
            detection_hold_frames = 1  # 不保持帧数，每帧都是实时结果
            last_detection_frame = -detection_hold_frames  # 上次检测的帧号
            
            # 初始化跟踪器和计数器
            global tracker
            tracker = ObjectTracker()  # 重新初始化跟踪器
            
            # 设置预警功能
            if enable_tracking and enable_alert:
                tracker.set_alert_enabled(True)
            
            print(f"📹 开始处理视频: {total_frames} 帧")
            print(f"🎯 跟踪启用: {enable_tracking}, 计数启用: {enable_counting}, 预警启用: {enable_alert}")

            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 每detection_interval帧检测一次以提高性能
                if frame_count % detection_interval == 0:
                    try:
                        results = model(frame)
                        
                        # 更新上次检测帧号
                        last_detection_frame = frame_count
                        
                        # 清空上一次的检测结果
                        current_detections = []
                        frame_detections = []
                        
                        for r in results:
                            boxes = r.boxes
                            if boxes is not None:
                                for box in boxes:
                                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                    conf = box.conf[0].cpu().numpy()
                                    cls = box.cls[0].cpu().numpy()
                                    
                                    detection_info = {
                                        'frame': frame_count,
                                        'class': model.names[int(cls)],
                                        'confidence': float(conf),
                                        'bbox': [float(x1), float(y1), float(x2), float(y2)]
                                    }
                                    
                                    # 添加到总检测结果
                                    all_detections.append(detection_info)
                                    
                                    # 添加到当前检测结果（用于绘制）
                                    current_detections.append({
                                        'bbox': [x1, y1, x2, y2],
                                        'class': model.names[int(cls)],
                                        'confidence': conf,
                                        'detection_frame': frame_count
                                    })
                                    
                                    # 添加到帧检测结果（用于跟踪）
                                    frame_detections.append({
                                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                                        'class': model.names[int(cls)],
                                        'confidence': float(conf)
                                    })
                        
                        # 如果启用跟踪，更新跟踪器
                        if enable_tracking:
                            current_tracking_results = tracker.update(frame_detections, height)
                            
                            # 保存跟踪结果
                            for track in current_tracking_results:
                                track_info = {
                                    'frame': frame_count,
                                    'track_id': track['id'],
                                    'class': track['class'],
                                    'confidence': track['confidence'],
                                    'bbox': track['bbox'],
                                    'centroid': track['centroid']
                                }
                                all_tracking_results.append(track_info)
                            
                            # 如果启用预警，检查并处理新目标
                            if enable_alert:
                                new_targets = tracker.get_new_targets()
                                for new_target in new_targets:
                                    # 保存预警帧
                                    alert_id = save_alert_frame(
                                        frame=frame,
                                        user_id=user_id,
                                        target_info=new_target,
                                        frame_number=frame_count,
                                        detection_result_id=None  # 视频处理完成后再关联
                                    )
                                    if alert_id:
                                        print(f"🚨 预警触发! 新目标: {new_target['class']} ID:{new_target['id']} 在第 {frame_count} 帧")
                                    
                    except Exception as detection_error:
                        print(f"⚠️  帧 {frame_count} 检测失败: {detection_error}")
                
                # 检查检测结果是否过期（超过保持帧数就清空）
                if frame_count - last_detection_frame > detection_hold_frames:
                    current_detections = []
                
                # 如果启用跟踪，获取当前活跃的轨迹
                if enable_tracking:
                    # 如果不是检测帧，只更新轨迹状态但不重新检测
                    if frame_count % detection_interval != 0:
                        # 增加所有轨迹的消失计数
                        for track_id in tracker.tracks:
                            tracker.tracks[track_id]['disappeared'] += 1
                        # 清理消失太久的轨迹
                        tracker._cleanup_disappeared_tracks()
                    
                    current_tracking_results = tracker.get_current_tracks()
                else:
                    current_tracking_results = []
                
                # 绘制检测框或跟踪框
                if enable_tracking:
                    # 如果启用跟踪，绘制当前帧的跟踪结果
                    for track_info in current_tracking_results:
                        x1, y1, x2, y2 = track_info['bbox']
                        class_name = track_info['class']
                        confidence = track_info['confidence']
                        track_id = track_info['id']
                        
                        # 绘制跟踪框（蓝色）
                        color = (255, 0, 0)  # 蓝色表示跟踪
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                        
                        # 绘制标签（包含跟踪ID）
                        label = f'ID:{track_id} {class_name}: {confidence:.2f}'
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                        
                        # 标签背景
                        cv2.rectangle(frame, (int(x1), int(y1) - label_size[1] - 10), 
                                    (int(x1) + label_size[0], int(y1)), color, -1)
                        
                        # 标签文字
                        cv2.putText(frame, label, (int(x1), int(y1) - 5), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                        
                        # 绘制轨迹点
                        centroid = track_info['centroid']
                        cv2.circle(frame, (int(centroid[0]), int(centroid[1])), 3, color, -1)
                else:
                    # 如果没有启用跟踪，绘制普通检测框
                    for detection in current_detections:
                        x1, y1, x2, y2 = detection['bbox']
                        class_name = detection['class']
                        confidence = detection['confidence']
                        
                        # 根据帧数差异调整透明度（越老越透明）
                        frame_diff = frame_count - detection.get('detection_frame', frame_count)
                        alpha = max(0.3, 1.0 - (frame_diff / detection_hold_frames) * 0.7)
                        
                        # 绘制检测框
                        color = (0, int(255 * alpha), 0)  # 绿色，透明度渐变
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                        
                        # 绘制标签背景
                        label = f'{class_name}: {confidence:.2f}'
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                        
                        # 标签背景也应用透明度
                        overlay = frame.copy()
                        cv2.rectangle(overlay, (int(x1), int(y1) - label_size[1] - 10), 
                                    (int(x1) + label_size[0], int(y1)), color, -1)
                        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                        
                        # 绘制标签文字
                        cv2.putText(frame, label, (int(x1), int(y1) - 5), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                
                # 绘制计数信息
                if enable_counting:
                    # 获取完整的计数摘要
                    count_summary = tracker.get_count_summary()
                    
                    # 显示累积计数（总共出现过的不同ID数量）
                    if counting_class:
                        total_count = tracker.get_total_count(counting_class)
                        current_count = tracker.get_current_screen_count(counting_class)
                        count_text = f"累积 {counting_class}: {total_count} (当前: {current_count})"
                    else:
                        total_count = tracker.get_total_count()
                        current_count = tracker.get_current_screen_count()
                        count_text = f"累积总数: {total_count} (当前: {current_count})"
                    
                    # 绘制计数信息
                    cv2.putText(frame, count_text, (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # 可选：显示详细信息
                    if len(count_summary['cumulative_total']) > 1:
                        details = []
                        for class_name, count in count_summary['cumulative_total'].items():
                            details.append(f"{class_name}: {count}")
                        detail_text = " | ".join(details)
                        cv2.putText(frame, detail_text, (10, 60), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                # 写入帧到输出视频
                out.write(frame)
                frame_count += 1
                processed_frames += 1
                
                # 每处理100帧打印一次进度
                if processed_frames % 100 == 0:
                    progress = (processed_frames / total_frames) * 100 if total_frames > 0 else 0
                    detections_count = len(current_detections)
                    print(f"🎬 处理进度: {progress:.1f}% ({processed_frames}/{total_frames}) - 当前检测: {detections_count}")
                
                # 内存管理：定期清理过期的检测结果
                if frame_count % 500 == 0:
                    current_detections = [d for d in current_detections 
                                        if frame_count - d.get('detection_frame', 0) <= detection_hold_frames]
            
            cap.release()
            out.release()
            
            # 验证输出文件是否存在且有效
            if not os.path.exists(result_filepath):
                return jsonify({'success': False, 'message': '生成视频文件失败'}), 500
            
            file_size = os.path.getsize(result_filepath)
            if file_size < 1024:  # 小于1KB可能是空文件
                return jsonify({'success': False, 'message': '生成的视频文件过小，可能损坏'}), 500
            
            # 验证视频文件是否可以正常读取
            test_cap = cv2.VideoCapture(result_filepath)
            if not test_cap.isOpened():
                test_cap.release()
                return jsonify({'success': False, 'message': '生成的视频文件无法打开，可能格式不兼容'}), 500
            
            # 测试读取第一帧
            test_ret, test_frame = test_cap.read()
            test_cap.release()
            
            if not test_ret:
                return jsonify({'success': False, 'message': '生成的视频文件无法读取帧，可能已损坏'}), 500
            
            print(f"✅ 视频处理完成: {result_filename} ({file_size} bytes)")
            print(f"🎬 使用编码器: {selected_encoder}")
            print(f"📊 视频验证: 文件可正常读取")
            
            # 获取最终计数结果
            final_counts = tracker.get_cumulative_counts()  # 使用累积计数
            count_summary = tracker.get_count_summary()
            
            # 保存到数据库
            detection_result = DetectionResult(
                user_id=user_id,
                detection_type='video',
                original_file=os.path.basename(filepath),
                result_file=result_filename,
                detections=json.dumps(all_detections),
                confidence=max([d['confidence'] for d in all_detections]) if all_detections else 0,
                tracking_enabled=enable_tracking,
                tracking_results=json.dumps(all_tracking_results) if enable_tracking else None,
                counting_enabled=enable_counting,
                counting_class='' if enable_counting else None,  # 不再保存特定类别
                counting_results=json.dumps(count_summary) if enable_counting else None,  # 保存完整的计数摘要
                total_count=tracker.get_total_count() if enable_counting else 0  # 累积总数
            )
            db.session.add(detection_result)
            db.session.commit()
            
            response_data = {
                'success': True,
                'message': '视频检测完成',
                'detections': all_detections,
                'result_video': f'/static/{result_filename}',
                'detection_count': len(all_detections),
                'processed_frames': processed_frames,
                'total_detections': len(all_detections)
            }
            
            # 如果启用跟踪，添加跟踪结果
            if enable_tracking:
                response_data['tracking_results'] = all_tracking_results
                response_data['tracking_count'] = len(all_tracking_results)
            
            # 如果启用计数，添加计数结果
            if enable_counting:
                response_data['counting_results'] = final_counts  # 累积计数
                response_data['count_summary'] = count_summary  # 完整的计数摘要
                response_data['total_count'] = tracker.get_total_count()  # 累积总数
                response_data['current_screen_count'] = tracker.get_current_screen_count()  # 当前屏幕内数量
            
            return jsonify(response_data)
            
        except Exception as e:
            print(f"❌ 视频处理异常: {e}")
            return jsonify({'success': False, 'message': f'视频检测失败: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': '不支持的视频格式'}), 400

# 在app.py中添加重置tracker的API接口
@app.route('/api/tracking/reset', methods=['POST'])
def reset_tracker():
    """重置跟踪器和计数器"""
    try:
        global tracker
        tracker = ObjectTracker()  # 重新初始化跟踪器
        return jsonify({
            'success': True,
            'message': '跟踪器已重置'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置失败: {str(e)}'}), 500

@app.route('/api/detect_camera', methods=['POST'])
def detect_camera():
    # 这个接口用于启动摄像头检测
    user_id = request.json.get('user_id', 1)
    
    try:
        # 重置跟踪器，确保每次启动摄像头都是全新的状态
        global tracker
        tracker = ObjectTracker()
        
        # 这里返回摄像头检测的配置信息
        # 实际的摄像头检测会在前端通过WebRTC实现
        return jsonify({
            'success': True,
            'message': '摄像头检测模式已启动',
            'camera_config': {
                'fps': 30,
                'resolution': '640x480'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'摄像头启动失败: {str(e)}'}), 500

@app.route('/api/process_frame', methods=['POST'])
def process_frame():
    """处理从前端发送的摄像头帧"""
    try:
        data = request.get_json()
        image_data = data.get('image')
        user_id = data.get('user_id', 1)
        
        # 新增参数：跟踪、计数和预警设置
        enable_tracking = data.get('enable_tracking', False)
        enable_counting = data.get('enable_counting', False)
        counting_class = data.get('counting_class', '')
        enable_alert = data.get('enable_alert', False)
        
        # 解码base64图像
        image_data = image_data.split(',')[1]  # 移除data:image/jpeg;base64,前缀
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # 转换为OpenCV格式
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        height, width = frame.shape[:2]
        
        # YOLO检测
        results = model(frame)
        
        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = box.conf[0].cpu().numpy()
                    cls = box.cls[0].cpu().numpy()
                    
                    detections.append({
                        'class': model.names[int(cls)],
                        'confidence': float(conf),
                        'bbox': [float(x1), float(y1), float(x2), float(y2)]
                    })
        
        response_data = {
            'success': True,
            'detections': detections
        }
        
        # 如果启用跟踪，更新跟踪器
        if enable_tracking:
            global tracker
            
            # 设置预警功能
            if enable_alert:
                tracker.set_alert_enabled(True)
            
            tracking_results = tracker.update(detections, height)
            response_data['tracking_results'] = tracking_results
            
            # 如果启用预警，检查并处理新目标
            if enable_alert:
                new_targets = tracker.get_new_targets()
                response_data['new_targets'] = new_targets
                
                # 为每个新目标保存预警帧
                alert_ids = []
                for new_target in new_targets:
                    alert_id = save_alert_frame(
                        frame=frame,
                        user_id=user_id,
                        target_info=new_target,
                        frame_number=None,  # 摄像头模式没有帧号
                        detection_result_id=None
                    )
                    if alert_id:
                        alert_ids.append(alert_id)
                        print(f"🚨 实时预警! 新目标: {new_target['class']} ID:{new_target['id']}")
                
                response_data['alert_ids'] = alert_ids
            
            # 如果启用计数，返回计数结果
            if enable_counting:
                count_summary = tracker.get_count_summary()
                response_data['counting_results'] = count_summary['cumulative_total']  # 累积计数
                response_data['count_summary'] = count_summary  # 完整的计数摘要
                response_data['total_count'] = tracker.get_total_count()  # 累积总数
                response_data['current_screen_count'] = tracker.get_current_screen_count()  # 当前屏幕内数量
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'帧处理失败: {str(e)}'}), 500

@app.route('/api/tracking/counts', methods=['GET'])
def get_tracking_counts():
    """获取当前计数结果"""
    try:
        global tracker
        counts = tracker.get_current_counts()
        total_count = tracker.get_total_count()
        return jsonify({
            'success': True,
            'counts': counts,
            'total_count': total_count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取计数失败: {str(e)}'}), 500

@app.route('/api/model/classes', methods=['GET'])
def get_model_classes():
    """获取当前模型支持的类别"""
    try:
        global model
        if model is None:
            return jsonify({'success': False, 'message': '模型未加载'}), 400
        
        classes = list(model.names.values())
        return jsonify({
            'success': True,
            'classes': classes
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取类别失败: {str(e)}'}), 500

@app.route('/api/history/<int:user_id>')
def get_history(user_id):
    """获取用户的检测历史"""
    try:
        results = DetectionResult.query.filter_by(user_id=user_id).order_by(DetectionResult.created_at.desc()).all()
        
        history = []
        for result in results:
            history.append({
                'id': result.id,
                'detection_type': result.detection_type,
                'original_file': result.original_file,
                'result_file': result.result_file,
                'detections': json.loads(result.detections) if result.detections else [],
                'confidence': result.confidence,
                'created_at': result.created_at.isoformat()
            })
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取历史记录失败: {str(e)}'}), 500

@app.route('/api/history/delete/<int:record_id>', methods=['DELETE'])
def delete_history_record(record_id):
    """删除单个检测历史记录"""
    try:
        # 查找记录
        record = DetectionResult.query.get(record_id)
        if not record:
            return jsonify({'success': False, 'message': '记录不存在'}), 404
        
        # 删除关联的文件
        if record.result_file:
            result_file_path = os.path.join('static', record.result_file)
            if os.path.exists(result_file_path):
                try:
                    os.remove(result_file_path)
                    print(f"删除结果文件: {result_file_path}")
                except Exception as e:
                    print(f"删除结果文件失败: {e}")
        
        # 删除原始文件（如果存在）
        if record.original_file:
            original_file_path = os.path.join(app.config['UPLOAD_FOLDER'], record.original_file)
            if os.path.exists(original_file_path):
                try:
                    os.remove(original_file_path)
                    print(f"删除原始文件: {original_file_path}")
                except Exception as e:
                    print(f"删除原始文件失败: {e}")
        
        # 删除数据库记录
        db.session.delete(record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '历史记录删除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除记录失败: {str(e)}'}), 500

@app.route('/api/history/batch-delete', methods=['DELETE'])
def batch_delete_history():
    """批量删除检测历史记录"""
    try:
        data = request.get_json()
        record_ids = data.get('record_ids', [])
        user_id = data.get('user_id')
        
        if not record_ids:
            return jsonify({'success': False, 'message': '未指定要删除的记录'}), 400
        
        deleted_count = 0
        failed_count = 0
        
        for record_id in record_ids:
            try:
                # 查找记录
                record = DetectionResult.query.filter_by(id=record_id, user_id=user_id).first()
                if not record:
                    failed_count += 1
                    continue
                
                # 删除关联的文件
                if record.result_file:
                    result_file_path = os.path.join('static', record.result_file)
                    if os.path.exists(result_file_path):
                        try:
                            os.remove(result_file_path)
                        except:
                            pass
                
                if record.original_file:
                    original_file_path = os.path.join(app.config['UPLOAD_FOLDER'], record.original_file)
                    if os.path.exists(original_file_path):
                        try:
                            os.remove(original_file_path)
                        except:
                            pass
                
                # 删除数据库记录
                db.session.delete(record)
                deleted_count += 1
                
            except Exception as e:
                print(f"删除记录 {record_id} 失败: {e}")
                failed_count += 1
        
        db.session.commit()
        
        message = f'成功删除 {deleted_count} 条记录'
        if failed_count > 0:
            message += f'，{failed_count} 条记录删除失败'
        
        return jsonify({
            'success': True,
            'message': message,
            'deleted_count': deleted_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'批量删除失败: {str(e)}'}), 500

@app.route('/api/history/clear/<int:user_id>', methods=['DELETE'])
def clear_user_history(user_id):
    """清空用户的所有检测历史"""
    try:
        # 获取用户的所有记录
        records = DetectionResult.query.filter_by(user_id=user_id).all()
        
        if not records:
            return jsonify({'success': True, 'message': '没有需要清空的记录'})
        
        deleted_count = 0
        
        for record in records:
            try:
                # 删除关联的文件
                if record.result_file:
                    result_file_path = os.path.join('static', record.result_file)
                    if os.path.exists(result_file_path):
                        try:
                            os.remove(result_file_path)
                        except:
                            pass
                
                if record.original_file:
                    original_file_path = os.path.join(app.config['UPLOAD_FOLDER'], record.original_file)
                    if os.path.exists(original_file_path):
                        try:
                            os.remove(original_file_path)
                        except:
                            pass
                
                # 删除数据库记录
                db.session.delete(record)
                deleted_count += 1
                
            except Exception as e:
                print(f"删除记录时出错: {e}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功清空所有历史记录，共删除 {deleted_count} 条记录',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'清空历史记录失败: {str(e)}'}), 500

@app.route('/api/models', methods=['GET'])
def get_models():
    """获取可用的模型列表"""
    try:
        models_dir = request.args.get('dir', 'models')
        model_files = get_model_files(models_dir)
        
        return jsonify({
            'success': True,
            'models': model_files,
            'current_model': current_model_path,
            'models_directory': models_dir
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取模型列表失败: {str(e)}'}), 500

@app.route('/api/models/load', methods=['POST'])
def load_model():
    """加载指定的模型"""
    try:
        data = request.get_json()
        model_path = data.get('model_path')
        
        if not model_path:
            return jsonify({'success': False, 'message': '未指定模型路径'}), 400
        
        # 检查模型文件是否存在（对于本地文件）
        if not model_path.startswith('yolov8') and not os.path.exists(model_path):
            return jsonify({'success': False, 'message': f'模型文件不存在: {model_path}'}), 404
        
        # 加载模型
        success = load_yolo_model(model_path)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'模型加载成功: {model_path}',
                'current_model': current_model_path,
                'model_info': {
                    'path': current_model_path,
                    'classes': list(model.names.values()) if model else [],
                    'class_count': len(model.names) if model else 0
                }
            })
        else:
            return jsonify({'success': False, 'message': '模型加载失败'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'加载模型时出错: {str(e)}'}), 500

@app.route('/api/models/current', methods=['GET'])
def get_current_model():
    """获取当前模型信息"""
    try:
        model_info = {
            'path': current_model_path,
            'loaded': model is not None,
            'type': current_model_type,
            'classes': list(model.names.values()) if model else [],
            'class_count': len(model.names) if model else 0,
            'supports_segmentation': current_model_type == 'segmentation'
        }
        
        return jsonify({
            'success': True,
            'model_info': model_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取模型信息失败: {str(e)}'}), 500

@app.route('/api/segment_image', methods=['POST'])
def segment_image():
    """专门的图像分割接口"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400
    
    file = request.files['file']
    user_id = request.form.get('user_id', 1)
    show_masks = request.form.get('show_masks', 'true').lower() == 'true'
    show_boxes = request.form.get('show_boxes', 'true').lower() == 'true'
    show_labels = request.form.get('show_labels', 'true').lower() == 'true'
    mask_alpha = float(request.form.get('mask_alpha', 0.4))
    conf_threshold = float(request.form.get('conf_threshold', 0.25))
    iou_threshold = float(request.form.get('iou_threshold', 0.45))
    
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    # 检查是否加载了分割模型
    if current_model_type != 'segmentation' or not seg_handler:
        return jsonify({
            'success': False, 
            'message': '当前未加载分割模型，请先加载YOLO分割模型（如yolov8n-seg.pt）'
        }), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            img = cv2.imread(filepath)
            
            # 执行分割预测
            seg_results = seg_handler.predict(img, conf=conf_threshold, iou=iou_threshold)
            
            if not seg_results:
                return jsonify({
                    'success': True,
                    'message': '未检测到任何目标',
                    'detections': [],
                    'segmentation_results': {'masks_count': 0, 'segments_count': 0},
                    'result_image': None
                })
            
            result = seg_results[0]
            
            # 生成可视化结果
            vis_img = seg_handler.visualize_segmentation(
                img, result, show_boxes, show_masks, show_labels, mask_alpha
            )
            
            # 保存结果图像
            result_filename = 'seg_result_' + filename
            result_filepath = os.path.join('static', result_filename)
            cv2.imwrite(result_filepath, vis_img)
            
            # 转换为标准检测格式
            detections = []
            for i, (box, conf, cls, cls_name) in enumerate(zip(
                result.get('boxes', []),
                result.get('confidences', []),
                result.get('classes', []),
                result.get('class_names', [])
            )):
                detections.append({
                    'class': cls_name,
                    'confidence': float(conf),
                    'bbox': box,
                    'has_mask': i < len(result.get('masks', [])),
                    'mask_area': None  # 可以计算掩码面积
                })
            
            # 保存到数据库
            detection_result = DetectionResult(
                user_id=user_id,
                detection_type='image_segmentation',
                original_file=filename,
                result_file=result_filename,
                detections=json.dumps(detections),
                confidence=max([d['confidence'] for d in detections]) if detections else 0
            )
            db.session.add(detection_result)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '图像分割完成',
                'detections': detections,
                'segmentation_results': {
                    'masks_count': len(result.get('masks', [])),
                    'segments_count': len(result.get('segments', [])),
                    'total_objects': len(detections)
                },
                'result_image': f'/static/{result_filename}',
                'model_type': 'segmentation',
                'visualization_settings': {
                    'show_masks': show_masks,
                    'show_boxes': show_boxes,
                    'show_labels': show_labels,
                    'mask_alpha': mask_alpha
                }
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'分割失败: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': '不支持的文件格式'}), 400

@app.route('/api/segment_video', methods=['POST'])
def segment_video():
    """视频分割接口"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400
    
    file = request.files['file']
    user_id = request.form.get('user_id', 1)
    show_masks = request.form.get('show_masks', 'true').lower() == 'true'
    show_boxes = request.form.get('show_boxes', 'true').lower() == 'true'
    show_labels = request.form.get('show_labels', 'true').lower() == 'true'
    mask_alpha = float(request.form.get('mask_alpha', 0.4))
    conf_threshold = float(request.form.get('conf_threshold', 0.25))
    iou_threshold = float(request.form.get('iou_threshold', 0.45))
    
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    # 检查是否加载了分割模型
    if current_model_type != 'segmentation' or not seg_handler:
        return jsonify({
            'success': False, 
            'message': '当前未加载分割模型，请先加载YOLO分割模型（如yolov8n-seg.pt）'
        }), 400
    
    if file and allowed_video_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        original_name, original_ext = os.path.splitext(filename)
        input_filename = timestamp + filename
        output_filename = 'seg_result_' + timestamp + original_name + '.mp4'
        
        input_filepath = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        output_filepath = os.path.join('static', output_filename)
        
        file.save(input_filepath)
        
        try:
            # 使用分割处理器处理视频
            def progress_callback(progress, current_frame, total_frames):
                print(f"🎬 分割进度: {progress:.1f}% ({current_frame}/{total_frames})")
            
            result_stats = seg_handler.process_video_segmentation(
                input_filepath, output_filepath,
                conf=conf_threshold, iou=iou_threshold,
                show_boxes=show_boxes, show_masks=show_masks, 
                show_labels=show_labels, mask_alpha=mask_alpha,
                progress_callback=progress_callback
            )
            
            # 转换结果格式
            all_detections = []
            for frame_result in result_stats['results']:
                if frame_result['result'] and 'boxes' in frame_result['result']:
                    for i, (box, conf, cls, cls_name) in enumerate(zip(
                        frame_result['result'].get('boxes', []),
                        frame_result['result'].get('confidences', []),
                        frame_result['result'].get('classes', []),
                        frame_result['result'].get('class_names', [])
                    )):
                        all_detections.append({
                            'frame': frame_result['frame'],
                            'class': cls_name,
                            'confidence': float(conf),
                            'bbox': box,
                            'has_mask': i < len(frame_result['result'].get('masks', []))
                        })
            
            # 保存到数据库
            detection_result = DetectionResult(
                user_id=user_id,
                detection_type='video_segmentation',
                original_file=input_filename,
                result_file=output_filename,
                detections=json.dumps(all_detections),
                confidence=max([d['confidence'] for d in all_detections]) if all_detections else 0
            )
            db.session.add(detection_result)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'视频分割完成！处理了 {result_stats["total_frames"]} 帧',
                'result_video': f'/static/{output_filename}',
                'segmentation_stats': {
                    'total_frames': result_stats['total_frames'],
                    'total_detections': result_stats['total_detections'],
                    'total_masks': result_stats['total_masks'],
                    'average_detections_per_frame': result_stats['average_detections_per_frame']
                },
                'detections': all_detections,
                'model_type': 'segmentation'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'视频分割失败: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': '不支持的视频格式'}), 400

@app.route('/api/models/upload', methods=['POST'])
def upload_model():
    """上传模型文件到服务器"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'}), 400
        
        # 检查文件扩展名
        if not allowed_model_file(file.filename):
            return jsonify({'success': False, 'message': '不支持的模型文件格式'}), 400
        
        # 确保models目录存在
        models_dir = 'models'
        os.makedirs(models_dir, exist_ok=True)
        
        # 保存文件
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        unique_filename = timestamp + filename
        filepath = os.path.join(models_dir, unique_filename)
        
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'message': '模型文件上传成功',
            'file_path': filepath,
            'filename': unique_filename
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'上传模型失败: {str(e)}'}), 500

@app.route('/api/models/delete', methods=['DELETE'])
def delete_model():
    """删除指定的模型文件"""
    try:
        data = request.get_json()
        model_path = data.get('model_path')
        
        if not model_path:
            return jsonify({'success': False, 'message': '未指定模型路径'}), 400
        
        # 防止删除预训练模型
        if model_path.startswith('yolov8') and not os.path.exists(model_path):
            return jsonify({'success': False, 'message': '不能删除预训练模型'}), 400
        
        # 检查文件是否存在
        if not os.path.exists(model_path):
            return jsonify({'success': False, 'message': '模型文件不存在'}), 404
        
        # 如果是当前使用的模型，不允许删除
        if model_path == current_model_path:
            return jsonify({'success': False, 'message': '不能删除当前正在使用的模型'}), 400
        
        # 删除文件
        os.remove(model_path)
        
        return jsonify({
            'success': True,
            'message': f'模型文件删除成功: {model_path}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除模型失败: {str(e)}'}), 500

# 预警记录相关API
@app.route('/api/alerts/<int:user_id>')
def get_alerts(user_id):
    """获取用户的预警记录"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        is_handled = request.args.get('is_handled', None)
        
        # 构建查询
        query = AlertRecord.query.filter_by(user_id=user_id)
        
        # 如果指定了处理状态，添加过滤条件
        if is_handled is not None:
            query = query.filter_by(is_handled=is_handled.lower() == 'true')
        
        # 分页查询
        alerts = query.order_by(AlertRecord.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        alert_list = []
        for alert in alerts.items:
            alert_list.append({
                'id': alert.id,
                'alert_type': alert.alert_type,
                'target_id': alert.target_id,
                'target_class': alert.target_class,
                'frame_number': alert.frame_number,
                'frame_image': f'/static/{alert.frame_image}',
                'bbox': json.loads(alert.bbox) if alert.bbox else None,
                'confidence': alert.confidence,
                'description': alert.description,
                'is_handled': alert.is_handled,
                'created_at': alert.created_at.isoformat()
            })
        
        return jsonify({
            'success': True,
            'alerts': alert_list,
            'pagination': {
                'page': alerts.page,
                'pages': alerts.pages,
                'per_page': alerts.per_page,
                'total': alerts.total,
                'has_next': alerts.has_next,
                'has_prev': alerts.has_prev
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取预警记录失败: {str(e)}'}), 500

@app.route('/api/alerts/mark_handled', methods=['POST'])
def mark_alert_handled():
    """标记预警为已处理"""
    try:
        data = request.get_json()
        alert_ids = data.get('alert_ids', [])
        user_id = data.get('user_id')
        
        if not alert_ids:
            return jsonify({'success': False, 'message': '未指定预警记录'}), 400
        
        # 批量更新
        updated_count = 0
        for alert_id in alert_ids:
            alert = AlertRecord.query.filter_by(id=alert_id, user_id=user_id).first()
            if alert:
                alert.is_handled = True
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'已标记 {updated_count} 条预警为已处理',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'标记失败: {str(e)}'}), 500

@app.route('/api/alerts/delete', methods=['DELETE'])
def delete_alerts():
    """删除预警记录"""
    try:
        data = request.get_json()
        alert_ids = data.get('alert_ids', [])
        user_id = data.get('user_id')
        
        if not alert_ids:
            return jsonify({'success': False, 'message': '未指定预警记录'}), 400
        
        deleted_count = 0
        for alert_id in alert_ids:
            alert = AlertRecord.query.filter_by(id=alert_id, user_id=user_id).first()
            if alert:
                # 删除关联的图像文件
                if alert.frame_image:
                    image_path = os.path.join('static', alert.frame_image)
                    if os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                        except:
                            pass
                
                db.session.delete(alert)
                deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'已删除 {deleted_count} 条预警记录',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500

@app.route('/api/alerts/stats/<int:user_id>')
def get_alert_stats(user_id):
    """获取预警统计信息"""
    try:
        # 总预警数量
        total_alerts = AlertRecord.query.filter_by(user_id=user_id).count()
        
        # 未处理预警数量
        unhandled_alerts = AlertRecord.query.filter_by(user_id=user_id, is_handled=False).count()
        
        # 今日预警数量
        today = datetime.now().date()
        today_alerts = AlertRecord.query.filter(
            AlertRecord.user_id == user_id,
            db.func.date(AlertRecord.created_at) == today
        ).count()
        
        # 按类别统计
        class_stats = db.session.query(
            AlertRecord.target_class,
            db.func.count(AlertRecord.id).label('count')
        ).filter_by(user_id=user_id).group_by(AlertRecord.target_class).all()
        
        class_counts = {stat[0]: stat[1] for stat in class_stats}
        
        return jsonify({
            'success': True,
            'stats': {
                'total_alerts': total_alerts,
                'unhandled_alerts': unhandled_alerts,
                'today_alerts': today_alerts,
                'class_counts': class_counts
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取统计信息失败: {str(e)}'}), 500

# 水印去除相关API
@app.route('/api/watermark/remove', methods=['POST'])
def remove_watermark_image():
    """图片水印去除接口"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400
    
    file = request.files['file']
    user_id = request.form.get('user_id', 1)
    detection_mode = request.form.get('detection_mode', 'auto')
    watermark_class = request.form.get('watermark_class', '')
    removal_strength = int(request.form.get('removal_strength', 3))
    edge_repair = request.form.get('edge_repair', 'true').lower() == 'true'
    quality_optimization = request.form.get('quality_optimization', 'true').lower() == 'true'
    
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # 模拟水印检测和去除过程
            processing_result = process_watermark_removal(
                filepath, 
                detection_mode, 
                watermark_class, 
                removal_strength,
                edge_repair,
                quality_optimization
            )
            
            return jsonify(processing_result)
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'水印去除失败: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': '不支持的文件格式'}), 400

@app.route('/api/watermark/remove_video', methods=['POST'])
def remove_watermark_video():
    """视频水印去除接口"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400
    
    file = request.files['file']
    user_id = request.form.get('user_id', 1)
    detection_mode = request.form.get('detection_mode', 'auto')
    watermark_class = request.form.get('watermark_class', '')
    removal_strength = int(request.form.get('removal_strength', 3))
    edge_repair = request.form.get('edge_repair', 'true').lower() == 'true'
    quality_optimization = request.form.get('quality_optimization', 'true').lower() == 'true'
    
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    if file and allowed_video_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        original_name, original_ext = os.path.splitext(filename)
        input_filename = timestamp + filename
        output_filename = 'watermark_removed_' + timestamp + original_name + '.mp4'
        
        input_filepath = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        output_filepath = os.path.join('static', output_filename)
        
        file.save(input_filepath)
        
        try:
            # 模拟视频水印去除过程
            processing_result = process_video_watermark_removal(
                input_filepath,
                output_filepath,
                detection_mode,
                watermark_class,
                removal_strength,
                edge_repair,
                quality_optimization
            )
            
            return jsonify(processing_result)
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'视频水印去除失败: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': '不支持的视频格式'}), 400

# 水印检测模型管理API
@app.route('/api/watermark/model/load', methods=['POST'])
def load_watermark_model_api():
    """加载水印检测模型"""
    try:
        data = request.get_json()
        model_path = data.get('model_path')
        
        if not model_path:
            return jsonify({'success': False, 'message': '未指定模型路径'}), 400
        
        # 检查模型文件是否存在
        if not os.path.exists(model_path):
            return jsonify({'success': False, 'message': f'模型文件不存在: {model_path}'}), 404
        
        # 加载水印检测模型
        success = load_watermark_detector(model_path)
        
        if success:
            model_info = get_watermark_detector_info()
            return jsonify({
                'success': True,
                'message': f'水印检测模型加载成功: {model_path}',
                'model_info': model_info
            })
        else:
            return jsonify({'success': False, 'message': '水印检测模型加载失败'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'加载模型时出错: {str(e)}'}), 500

@app.route('/api/watermark/model/info', methods=['GET'])
def get_watermark_model_info():
    """获取当前水印检测模型信息"""
    try:
        model_info = get_watermark_detector_info()
        return jsonify({
            'success': True,
            'model_info': model_info
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取模型信息失败: {str(e)}'}), 500

@app.route('/api/watermark/models', methods=['GET'])
def get_watermark_models():
    """获取可用的水印检测模型列表"""
    try:
        # 扫描可能的水印模型文件
        watermark_models = []
        
        # 检查当前目录
        for file in os.listdir('.'):
            if file.endswith('.pt') and ('watermark' in file.lower() or 'xuesheng' in file.lower()):
                watermark_models.append({
                    'name': file,
                    'path': file,
                    'size_mb': round(os.path.getsize(file) / (1024 * 1024), 2),
                    'type': 'watermark_detection'
                })
        
        # 检查models目录
        models_dir = 'models'
        if os.path.exists(models_dir):
            for file in os.listdir(models_dir):
                if file.endswith('.pt'):
                    file_path = os.path.join(models_dir, file)
                    watermark_models.append({
                        'name': file,
                        'path': file_path,
                        'size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2),
                        'type': 'watermark_detection'
                    })
        
        # 获取当前加载的模型信息
        current_model = get_watermark_detector_info()
        
        return jsonify({
            'success': True,
            'models': watermark_models,
            'current_model': current_model
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取模型列表失败: {str(e)}'}), 500

@app.route('/static/<filename>')
def static_files(filename):
    return send_file(os.path.join('static', filename))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_video_file(filename):
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_model_file(filename):
    """检查是否为支持的模型文件格式"""
    ALLOWED_EXTENSIONS = {'pt', 'onnx', 'torchscript', 'engine'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_watermark_removal(image_path, detection_mode, watermark_class, removal_strength, edge_repair, quality_optimization):
    """
    处理图片水印去除
    这是一个模拟函数，实际应用中需要集成专门的水印去除算法
    """
    import time
    start_time = time.time()
    
    try:
        # 读取图像
        img = cv2.imread(image_path)
        height, width = img.shape[:2]
        
        # 基于模型的水印检测过程
        confidence_threshold = float(request.form.get('confidence_threshold', 0.25))
        print(f"📊 开始水印检测 - 模式: {detection_mode}, 置信度阈值: {confidence_threshold}")
        detected_watermarks = model_based_watermark_detection(img, detection_mode, watermark_class, confidence_threshold)
        print(f"🔍 检测完成，共发现 {len(detected_watermarks)} 个水印区域")
        
        # 检查是否有检测结果
        if len(detected_watermarks) == 0:
            print("⚠️  未检测到任何水印，请检查:")
            print("   1. 置信度阈值是否过高")
            print("   2. 模型是否正确加载")
            print("   3. 图像中是否真的存在水印")
            
            return jsonify({
                'success': False,
                'message': '未检测到水印区域，请降低置信度阈值或检查模型设置',
                'watermarks_detected': [],
                'watermarks_removed': 0,
                'processing_stats': {
                    'processing_time': 0,
                    'detection_accuracy': 0,
                    'removal_success_rate': 0,
                    'image_quality': 0
                }
            })
        
        # 先进的水印去除过程
        print(f"🔧 开始去除 {len(detected_watermarks)} 个检测到的水印...")
        processed_img, removed_count = advanced_watermark_removal(
            img, detected_watermarks, removal_strength, edge_repair, quality_optimization
        )
        
        # 保存处理后的图像
        result_filename = 'watermark_removed_' + os.path.basename(image_path)
        result_path = os.path.join('static', result_filename)
        cv2.imwrite(result_path, processed_img)
        
        processing_time = time.time() - start_time
        
        return {
            'success': True,
            'message': '水印去除完成',
            'result_file': f'/static/{result_filename}',
            'watermarks_detected': detected_watermarks,
            'watermarks_removed': removed_count,
            'processing_stats': {
                'processing_time': round(processing_time, 2),
                'detection_accuracy': 95,  # 模拟数据
                'removal_success_rate': 88,  # 模拟数据
                'image_quality': 92  # 模拟数据
            }
        }
        
    except Exception as e:
        raise Exception(f"图片处理失败: {str(e)}")

def process_video_watermark_removal(input_path, output_path, detection_mode, watermark_class, removal_strength, edge_repair, quality_optimization):
    """
    处理视频水印去除
    这是一个模拟函数，实际应用中需要集成专门的水印去除算法
    """
    import time
    start_time = time.time()
    
    try:
        cap = cv2.VideoCapture(input_path)
        
        if not cap.isOpened():
            raise Exception('无法打开视频文件')
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if fps <= 0:
            fps = 25.0
        
        # 创建视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'H264')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            raise Exception('无法创建输出视频文件')
        
        frame_count = 0
        total_watermarks_detected = 0
        total_watermarks_removed = 0
        
        print(f"📹 开始处理视频水印去除: {total_frames} 帧")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 每10帧检测一次水印（优化性能）
            if frame_count % 10 == 0:
                detected_watermarks = model_based_watermark_detection(frame, detection_mode, watermark_class, 0.25)
                total_watermarks_detected += len(detected_watermarks)
                
                if detected_watermarks:
                    processed_frame, removed_count = advanced_watermark_removal(
                        frame, detected_watermarks, removal_strength, edge_repair, quality_optimization
                    )
                    total_watermarks_removed += removed_count
                    frame = processed_frame
            
            out.write(frame)
            frame_count += 1
            
            # 每100帧打印一次进度
            if frame_count % 100 == 0:
                progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                print(f"🎬 水印去除进度: {progress:.1f}% ({frame_count}/{total_frames})")
        
        cap.release()
        out.release()
        
        processing_time = time.time() - start_time
        
        return {
            'success': True,
            'message': f'视频水印去除完成！处理了 {frame_count} 帧',
            'result_file': f'/static/{os.path.basename(output_path)}',
            'watermarks_detected': [{'total_count': total_watermarks_detected}],
            'watermarks_removed': total_watermarks_removed,
            'processing_stats': {
                'processing_time': round(processing_time, 2),
                'detection_accuracy': 93,  # 模拟数据
                'removal_success_rate': 85,  # 模拟数据
                'image_quality': 90  # 模拟数据
            },
            'processed_frames': frame_count
        }
        
    except Exception as e:
        raise Exception(f"视频处理失败: {str(e)}")

def model_based_watermark_detection(img, detection_mode, watermark_class, confidence_threshold=0.25):
    """
    基于本地水印检测模型的检测算法
    使用您本地训练的YOLO水印检测模型
    """
    global watermark_detector
    
    detected_watermarks = []
    
    try:
        if watermark_detector is None:
            print("⚠️  水印检测模型未加载，使用备用检测方法")
            return fallback_watermark_detection(img, detection_mode, watermark_class)
        
        # 使用本地水印检测模型进行检测
        watermarks = detect_watermarks_in_image(img, confidence_threshold)
        
        # 转换为统一格式
        for wm in watermarks:
            detected_watermarks.append({
                'type': wm['type'],
                'confidence': wm['confidence'],
                'location': wm['bbox'],  # [x1, y1, x2, y2]
                'class_id': wm.get('class_id', 0),
                'area': wm.get('area', 0),
                'removed': False,
                'method': 'yolo_model_detection'
            })
        
        print(f"🎯 使用本地模型检测到 {len(detected_watermarks)} 个水印")
        
        # 如果指定了特定水印类别，只返回该类别的检测结果
        if detection_mode == 'manual' and watermark_class:
            detected_watermarks = [wm for wm in detected_watermarks 
                                 if wm['type'].lower() == watermark_class.lower()]
            print(f"🔍 筛选类别 '{watermark_class}': {len(detected_watermarks)} 个结果")
        
        return detected_watermarks
        
    except Exception as e:
        print(f"❌ 模型检测失败: {e}")
        return fallback_watermark_detection(img, detection_mode, watermark_class)

def fallback_watermark_detection(img, detection_mode, watermark_class):
    """
    备用水印检测方法（当模型不可用时使用）
    """
    print("🔄 使用备用检测方法")
    height, width = img.shape[:2]
    detected_watermarks = []
    
    if detection_mode == 'auto':
        # 简化的角落检测
        corner_regions = [
            {'type': 'text', 'region': (width-200, height-80, width-20, height-10)},
            {'type': 'logo', 'region': (width-150, 10, width-10, 80)},
        ]
        
        for corner in corner_regions:
            x1, y1, x2, y2 = corner['region']
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
            
            if x2 > x1 and y2 > y1:
                detected_watermarks.append({
                    'type': corner['type'],
                    'confidence': 0.75,
                    'location': [x1, y1, x2, y2],
                    'removed': False,
                    'method': 'fallback_detection'
                })
    
    elif detection_mode == 'manual' and watermark_class:
        detected_watermarks.append({
            'type': watermark_class,
            'confidence': 0.95,
            'location': [width - 200, height - 80, width - 20, height - 10],
            'removed': False,
            'method': 'manual_selection'
        })
    
    return detected_watermarks

def advanced_watermark_removal(img, watermarks, removal_strength, edge_repair, quality_optimization):
    """
    改进的水印去除算法
    针对YOLO检测结果进行精确去除
    """
    processed_img = img.copy()
    removed_count = 0
    
    print(f"🔧 开始处理 {len(watermarks)} 个检测到的水印")
    
    for i, watermark in enumerate(watermarks):
        try:
            # 获取水印位置
            x1, y1, x2, y2 = watermark['location']
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            print(f"   水印 {i+1}: {watermark['type']} at ({x1},{y1})-({x2},{y2}), 置信度: {watermark['confidence']:.2f}")
            
            # 确保坐标在图像范围内
            h, w = img.shape[:2]
            x1 = max(0, min(x1, w-1))
            y1 = max(0, min(y1, h-1))
            x2 = max(x1+1, min(x2, w))
            y2 = max(y1+1, min(y2, h))
            
            # 检查水印区域大小
            watermark_width = x2 - x1
            watermark_height = y2 - y1
            
            if watermark_width < 5 or watermark_height < 5:
                print(f"   ⚠️  水印区域太小，跳过处理")
                continue
            
            # 根据水印大小和强度决定处理方法
            watermark_area = watermark_width * watermark_height
            image_area = h * w
            area_ratio = watermark_area / image_area
            
            print(f"   📏 水印尺寸: {watermark_width}x{watermark_height}, 占比: {area_ratio:.3f}")
            
            # 选择最适合的去除方法
            success = False
            watermark_type = watermark.get('type', 'unknown').lower()
            
            if area_ratio < 0.01:  # 小水印：直接修复
                success = remove_small_watermark(processed_img, x1, y1, x2, y2, removal_strength)
            elif 'text' in watermark_type or 'logo' in watermark_type:
                success = remove_text_logo_watermark(processed_img, x1, y1, x2, y2, removal_strength, edge_repair)
            else:
                success = remove_general_watermark(processed_img, x1, y1, x2, y2, removal_strength, edge_repair)
            
            if success:
                watermark['removed'] = True
                removed_count += 1
                print(f"   ✅ 水印去除成功")
            else:
                print(f"   ❌ 水印去除失败")
                
        except Exception as e:
            print(f"   ❌ 处理水印时出错: {e}")
            continue
    
    # 全局质量优化
    if quality_optimization and removed_count > 0:
        print("🎨 应用全局质量优化...")
        processed_img = apply_quality_enhancement(processed_img)
    
    print(f"✅ 完成处理，成功去除 {removed_count}/{len(watermarks)} 个水印")
    
    return processed_img, removed_count

def remove_small_watermark(img, x1, y1, x2, y2, strength):
    """
    去除小尺寸水印（如小logo、文字）
    使用精确的图像修复
    """
    try:
        h, w = img.shape[:2]
        
        # 扩展修复区域以获取足够的上下文
        expand = max(10, min(20, min(x2-x1, y2-y1)//2))
        
        ex1 = max(0, x1 - expand)
        ey1 = max(0, y1 - expand) 
        ex2 = min(w, x2 + expand)
        ey2 = min(h, y2 + expand)
        
        # 提取工作区域
        work_region = img[ey1:ey2, ex1:ex2].copy()
        
        # 创建精确的掩码
        mask = np.zeros((ey2-ey1, ex2-ex1), dtype=np.uint8)
        mask_x1, mask_y1 = x1-ex1, y1-ey1
        mask_x2, mask_y2 = x2-ex1, y2-ey1
        mask[mask_y1:mask_y2, mask_x1:mask_x2] = 255
        
        # 扩展掩码边缘以获得更好的融合效果
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)
        
        # 选择修复算法
        if strength >= 4:
            repaired = cv2.inpaint(work_region, mask, 15, cv2.INPAINT_NS)
        else:
            repaired = cv2.inpaint(work_region, mask, 10, cv2.INPAINT_TELEA)
        
        # 应用羽化效果避免边缘痕迹
        mask_blurred = cv2.GaussianBlur(mask.astype(np.float32), (11, 11), 0) / 255.0
        mask_3d = np.stack([mask_blurred] * 3, axis=2)
        
        final_region = work_region * (1 - mask_3d) + repaired * mask_3d
        
        # 放回原图
        img[ey1:ey2, ex1:ex2] = final_region.astype(np.uint8)
        
        return True
        
    except Exception as e:
        print(f"小水印去除失败: {e}")
        return False

def remove_text_logo_watermark(img, x1, y1, x2, y2, strength, edge_repair):
    """
    去除文字和Logo水印
    使用多层修复技术
    """
    try:
        h, w = img.shape[:2]
        
        # 适度扩展区域
        expand = max(15, min(30, min(x2-x1, y2-y1)//3))
        
        ex1 = max(0, x1 - expand)
        ey1 = max(0, y1 - expand)
        ex2 = min(w, x2 + expand)
        ey2 = min(h, y2 + expand)
        
        work_region = img[ey1:ey2, ex1:ex2].copy()
        
        # 创建掩码
        mask = np.zeros((ey2-ey1, ex2-ex1), dtype=np.uint8)
        mask_x1, mask_y1 = x1-ex1, y1-ey1
        mask_x2, mask_y2 = x2-ex1, y2-ey1
        mask[mask_y1:mask_y2, mask_x1:mask_x2] = 255
        
        # 第一步：图像修复
        repaired1 = cv2.inpaint(work_region, mask, 20, cv2.INPAINT_NS)
        
        # 第二步：纹理填充
        repaired2 = apply_texture_filling(work_region, mask)
        
        # 混合两种方法的结果
        alpha = 0.7 if strength >= 3 else 0.5
        combined = alpha * repaired1 + (1-alpha) * repaired2
        
        # 边缘平滑处理
        if edge_repair:
            # 创建羽化掩码
            mask_blur = cv2.GaussianBlur(mask.astype(np.float32), (15, 15), 0) / 255.0
            mask_3d = np.stack([mask_blur] * 3, axis=2)
            
            # 应用平滑过渡
            final_region = work_region * (1 - mask_3d) + combined * mask_3d
        else:
            mask_3d = np.stack([mask.astype(np.float32)/255.0] * 3, axis=2)
            final_region = work_region * (1 - mask_3d) + combined * mask_3d
        
        # 放回原图
        img[ey1:ey2, ex1:ex2] = final_region.astype(np.uint8)
        
        return True
        
    except Exception as e:
        print(f"文字/Logo水印去除失败: {e}")
        return False

def remove_general_watermark(img, x1, y1, x2, y2, strength, edge_repair):
    """
    去除一般水印
    使用综合方法
    """
    try:
        h, w = img.shape[:2]
        
        # 较大的扩展区域
        expand = max(20, min(40, min(x2-x1, y2-y1)//2))
        
        ex1 = max(0, x1 - expand)
        ey1 = max(0, y1 - expand)
        ex2 = min(w, x2 + expand)
        ey2 = min(h, y2 + expand)
        
        work_region = img[ey1:ey2, ex1:ex2].copy()
        
        # 创建掩码
        mask = np.zeros((ey2-ey1, ex2-ex1), dtype=np.uint8)
        mask_x1, mask_y1 = x1-ex1, y1-ey1
        mask_x2, mask_y2 = x2-ex1, y2-ey1
        mask[mask_y1:mask_y2, mask_x1:mask_x2] = 255
        
        # 方法1：标准修复
        method1 = cv2.inpaint(work_region, mask, 25, cv2.INPAINT_TELEA)
        
        # 方法2：基于补丁的修复
        method2 = apply_patch_based_repair(work_region, mask)
        
        # 方法3：统计方法填充
        method3 = apply_statistical_filling(work_region, mask)
        
        # 根据强度组合不同方法
        if strength >= 4:
            combined = 0.5 * method1 + 0.3 * method2 + 0.2 * method3
        elif strength >= 3:
            combined = 0.4 * method1 + 0.4 * method2 + 0.2 * method3
        else:
            combined = 0.3 * method1 + 0.4 * method2 + 0.3 * method3
        
        # 边缘处理
        if edge_repair:
            # 多级羽化
            mask_s = cv2.GaussianBlur(mask.astype(np.float32), (21, 21), 0) / 255.0
            mask_3d = np.stack([mask_s] * 3, axis=2)
            
            # 额外的平滑步骤
            smoothed = cv2.bilateralFilter(combined.astype(np.uint8), 9, 75, 75)
            final_region = work_region * (1 - mask_3d) + smoothed * mask_3d
        else:
            mask_3d = np.stack([mask.astype(np.float32)/255.0] * 3, axis=2)
            final_region = work_region * (1 - mask_3d) + combined * mask_3d
        
        # 放回原图
        img[ey1:ey2, ex1:ex2] = final_region.astype(np.uint8)
        
        return True
        
    except Exception as e:
        print(f"一般水印去除失败: {e}")
        return False

def apply_texture_filling(img, mask):
    """
    纹理填充算法
    """
    try:
        result = img.copy()
        h, w = mask.shape
        
        # 找到掩码区域和周围区域
        mask_pixels = np.where(mask == 255)
        
        # 获取掩码周围的有效像素作为纹理源
        kernel = np.ones((7, 7), np.uint8)
        expanded = cv2.dilate(mask, kernel, iterations=2)
        border_region = expanded - mask
        border_pixels = np.where(border_region == 255)
        
        if len(border_pixels[0]) > 0:
            # 为每个掩码像素寻找最相似的边界像素
            for i, j in zip(mask_pixels[0], mask_pixels[1]):
                # 找到距离最近的几个边界像素
                distances = np.sqrt((border_pixels[0] - i)**2 + (border_pixels[1] - j)**2)
                nearest_indices = np.argsort(distances)[:5]  # 取前5个最近的
                
                # 计算加权平均
                weights = 1.0 / (distances[nearest_indices] + 1e-6)
                weights = weights / np.sum(weights)
                
                # 填充像素值
                new_pixel = np.zeros(3)
                for idx, weight in zip(nearest_indices, weights):
                    bi, bj = border_pixels[0][idx], border_pixels[1][idx]
                    new_pixel += weight * img[bi, bj]
                
                result[i, j] = new_pixel.astype(np.uint8)
        
        return result
        
    except Exception as e:
        print(f"纹理填充失败: {e}")
        return img

def apply_patch_based_repair(img, mask):
    """
    基于补丁的修复
    """
    try:
        result = img.copy()
        h, w = mask.shape
        
        # 简化的补丁修复：使用周围区域的平均值
        mask_pixels = np.where(mask == 255)
        
        for i, j in zip(mask_pixels[0], mask_pixels[1]):
            # 定义搜索窗口
            win_size = 5
            y1 = max(0, i - win_size)
            y2 = min(h, i + win_size + 1)
            x1 = max(0, j - win_size)
            x2 = min(w, j + win_size + 1)
            
            # 获取窗口内的非掩码像素
            window_mask = mask[y1:y2, x1:x2]
            window_img = img[y1:y2, x1:x2]
            
            valid_pixels = window_img[window_mask == 0]
            
            if len(valid_pixels) > 0:
                result[i, j] = np.mean(valid_pixels, axis=0)
            else:
                # 如果窗口内没有有效像素，使用全局均值
                result[i, j] = np.mean(img[mask == 0], axis=0)
        
        return result
        
    except Exception as e:
        print(f"补丁修复失败: {e}")
        return img

def apply_statistical_filling(img, mask):
    """
    统计方法填充
    """
    try:
        result = img.copy()
        
        # 获取非掩码区域的统计信息
        valid_region = img[mask == 0]
        
        if len(valid_region) > 0:
            # 计算均值和标准差
            mean_color = np.mean(valid_region, axis=0)
            std_color = np.std(valid_region, axis=0)
            
            # 用统计信息填充掩码区域
            mask_pixels = np.where(mask == 255)
            for i, j in zip(mask_pixels[0], mask_pixels[1]):
                # 添加一些随机性以避免均匀填充
                noise = np.random.normal(0, std_color * 0.3)
                new_value = mean_color + noise
                result[i, j] = np.clip(new_value, 0, 255)
        
        return result
        
    except Exception as e:
        print(f"统计填充失败: {e}")
        return img

def apply_quality_enhancement(img):
    """
    质量增强函数
    """
    try:
        # 1. 轻微降噪
        denoised = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
        
        # 2. 锐化
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        # 3. 对比度调整
        enhanced = cv2.convertScaleAbs(sharpened, alpha=1.05, beta=5)
        
        return enhanced
        
    except Exception as e:
        print(f"质量增强失败: {e}")
        return img

def apply_inpainting_removal(img, mask, strength):
    """
    使用图像修复技术去除水印
    适用于文字和Logo水印
    """
    try:
        # 使用OpenCV的快速行进算法进行图像修复
        if strength >= 4:
            # 高强度：使用Navier-Stokes方法（更慢但效果更好）
            inpainted = cv2.inpaint(img, mask, 15, cv2.INPAINT_NS)
        elif strength >= 3:
            # 中等强度：使用快速行进算法
            inpainted = cv2.inpaint(img, mask, 10, cv2.INPAINT_TELEA)
        else:
            # 低强度：使用基础修复
            inpainted = cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA)
        
        # 进一步优化：使用双边滤波平滑结果
        if strength >= 3:
            inpainted = cv2.bilateralFilter(inpainted, 9, 75, 75)
        
        return inpainted
        
    except Exception as e:
        print(f"修复算法失败，使用备用方法: {e}")
        # 备用方法：高级高斯模糊
        kernel_size = min(15, max(3, strength * 3))
        return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)

def apply_frequency_domain_removal(img, mask, strength):
    """
    使用频域方法去除半透明水印
    """
    try:
        # 转换为灰度进行频域处理
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 进行傅里叶变换
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        
        # 创建频域滤波器
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2
        
        # 根据强度调整滤波器参数
        filter_radius = max(10, strength * 20)
        
        # 创建带通滤波器
        mask_freq = np.ones((rows, cols), np.uint8)
        y, x = np.ogrid[:rows, :cols]
        center_mask = (x - ccol) ** 2 + (y - crow) ** 2 <= filter_radius ** 2
        mask_freq[center_mask] = 0
        
        # 应用滤波器
        f_shift_filtered = f_shift * mask_freq
        
        # 逆变换
        f_ishift = np.fft.ifftshift(f_shift_filtered)
        img_back = np.fft.ifft2(f_ishift)
        img_back = np.abs(img_back)
        
        # 归一化到0-255
        img_back = np.uint8(255 * img_back / np.max(img_back))
        
        # 转换回彩色
        result = cv2.cvtColor(img_back, cv2.COLOR_GRAY2BGR)
        
        # 只在掩码区域应用处理结果
        mask_3d = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) / 255.0
        result = img * (1 - mask_3d) + result * mask_3d
        
        return result.astype(np.uint8)
        
    except Exception as e:
        print(f"频域处理失败，使用备用方法: {e}")
        return apply_inpainting_removal(img, mask, strength)

def apply_hybrid_removal(img, mask, strength):
    """
    混合方法去除水印
    结合多种技术
    """
    try:
        # 方法1：图像修复
        inpainted = apply_inpainting_removal(img, mask, strength)
        
        # 方法2：纹理合成（使用周围区域的纹理）
        texture_synthesized = apply_texture_synthesis(img, mask, strength)
        
        # 方法3：基于梯度的修复
        gradient_repaired = apply_gradient_repair(img, mask, strength)
        
        # 根据强度混合不同方法的结果
        if strength >= 4:
            # 高强度：主要使用修复算法，辅以纹理合成
            result = 0.6 * inpainted + 0.3 * texture_synthesized + 0.1 * gradient_repaired
        elif strength >= 3:
            # 中等强度：平衡使用
            result = 0.5 * inpainted + 0.3 * texture_synthesized + 0.2 * gradient_repaired
        else:
            # 低强度：主要使用梯度修复
            result = 0.3 * inpainted + 0.2 * texture_synthesized + 0.5 * gradient_repaired
        
        return result.astype(np.uint8)
        
    except Exception as e:
        print(f"混合处理失败，使用基础方法: {e}")
        return apply_inpainting_removal(img, mask, strength)

def apply_texture_synthesis(img, mask, strength):
    """
    基于周围纹理的合成修复
    """
    try:
        # 获取非掩码区域作为纹理源
        h, w = mask.shape
        
        # 使用形态学操作扩展掩码，获取边界纹理
        kernel = np.ones((5, 5), np.uint8)
        expanded_mask = cv2.dilate(mask, kernel, iterations=2)
        texture_region = expanded_mask - mask
        
        # 在纹理区域进行随机采样和混合
        result = img.copy()
        
        if np.sum(texture_region) > 0:
            # 找到掩码区域的像素
            mask_pixels = np.where(mask == 255)
            texture_pixels = np.where(texture_region == 255)
            
            if len(texture_pixels[0]) > 0:
                # 为每个掩码像素随机选择纹理像素
                for i, j in zip(mask_pixels[0], mask_pixels[1]):
                    # 随机选择一个纹理像素
                    rand_idx = np.random.randint(0, len(texture_pixels[0]))
                    src_i, src_j = texture_pixels[0][rand_idx], texture_pixels[1][rand_idx]
                    
                    # 复制纹理像素，并添加一些噪声使其更自然
                    noise = np.random.normal(0, 5, 3)  # 小量噪声
                    result[i, j] = np.clip(img[src_i, src_j] + noise, 0, 255)
        
        return result
        
    except Exception as e:
        print(f"纹理合成失败: {e}")
        return img

def apply_gradient_repair(img, mask, strength):
    """
    基于梯度的修复方法
    """
    try:
        result = img.copy()
        
        # 计算图像梯度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        
        # 在掩码区域应用梯度平滑
        mask_3d = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        
        # 使用高斯模糊平滑梯度
        smoothed = cv2.GaussianBlur(result, (2*strength+1, 2*strength+1), 0)
        
        # 只在掩码区域应用平滑
        mask_norm = mask_3d / 255.0
        result = result * (1 - mask_norm) + smoothed * mask_norm
        
        return result.astype(np.uint8)
        
    except Exception as e:
        print(f"梯度修复失败: {e}")
        return img

def apply_edge_blending(original, processed, mask):
    """
    边缘融合，使修复区域与周围自然过渡
    """
    try:
        # 创建羽化掩码
        kernel = np.ones((5, 5), np.uint8)
        feathered_mask = cv2.erode(mask, kernel, iterations=1)
        feathered_mask = cv2.GaussianBlur(feathered_mask, (15, 15), 0)
        
        # 归一化掩码
        feathered_mask_3d = cv2.cvtColor(feathered_mask, cv2.COLOR_GRAY2BGR) / 255.0
        
        # 融合原图和处理后的图像
        result = original * (1 - feathered_mask_3d) + processed * feathered_mask_3d
        
        return result.astype(np.uint8)
        
    except Exception as e:
        print(f"边缘融合失败: {e}")
        return processed

def apply_global_enhancement(img):
    """
    全局图像质量增强
    """
    try:
        # 1. 降噪
        denoised = cv2.bilateralFilter(img, 9, 75, 75)
        
        # 2. 锐化
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        # 3. 对比度增强
        enhanced = cv2.convertScaleAbs(sharpened, alpha=1.1, beta=10)
        
        # 4. 颜色平衡
        lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # 应用CLAHE到L通道
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        l = clahe.apply(l)
        
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        
        return enhanced
        
    except Exception as e:
        print(f"全局增强失败: {e}")
        return img

if __name__ == '__main__':
    # 创建数据库表和初始数据
    with app.app_context():
        db.create_all()
        
        # 创建默认管理员用户
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password='admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("✅ 创建默认管理员用户: admin / admin123")
    
    # 加载YOLO模型
    load_yolo_model()
    
    print("🚀 启动YOLO检测识别系统...")
    print("📊 数据库: SQLite (yolo_detection.db)")
    print("🌐 访问地址: http://localhost:5000")
    print("👤 默认账号: admin / admin123")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 