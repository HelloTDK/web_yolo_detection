import cv2
import threading
import time
import queue
import json
import numpy as np
from ultralytics import YOLO
from datetime import datetime
from collections import defaultdict, deque
import base64
import io
from PIL import Image
import os

class ObjectTracker:
    """目标跟踪器（每个RTSP流独立的跟踪器）"""
    def __init__(self):
        self.tracks = {}
        self.next_id = 1
        self.max_disappeared = 10  # RTSP流模式下，增加消失帧数
        self.max_distance = 100  # 适中的距离阈值
        self.detection_history = []
        
        # 累积计数功能
        self.cumulative_ids = set()
        self.cumulative_counts_by_class = defaultdict(set)
        
        # 预警功能
        self.alert_enabled = False
        self.new_targets_this_frame = []
        
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
    
    def update(self, detections, frame_height):
        """更新跟踪器"""
        self.new_targets_this_frame = []
        
        # 清理消失太久的轨迹
        self._cleanup_disappeared_tracks()
        
        # 过滤稳定的检测结果
        stable_detections = self._filter_stable_detections(detections)
        
        if not stable_detections:
            for track_id in self.tracks:
                self.tracks[track_id]['disappeared'] += 1
            return self.get_current_tracks()
        
        # 计算中心点
        detection_centroids = []
        for detection in stable_detections:
            centroid = self.calculate_centroid(detection['bbox'])
            detection_centroids.append({
                'centroid': centroid,
                'detection': detection
            })
        
        if not self.tracks:
            for detection_info in detection_centroids:
                self._create_new_track(detection_info)
        else:
            self._match_detections_to_tracks(detection_centroids, frame_height)
        
        return self.get_current_tracks()
    
    def _filter_stable_detections(self, detections):
        """过滤稳定的检测结果"""
        if not detections:
            return detections
            
        filtered_detections = []
        for detection in detections:
            bbox = detection['bbox']
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            area = width * height
            
            if (detection['confidence'] >= 0.4 and 
                area >= 800 and  # 适当降低最小面积阈值
                width >= 15 and height >= 15):
                filtered_detections.append(detection)
                
        return filtered_detections
    
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
        
        if len(self.tracks) >= 100:  # RTSP流模式下可以跟踪更多目标
            return
        
        track_id = self.next_id
        self.tracks[track_id] = {
            'centroid': centroid,
            'disappeared': 0,
            'bbox': detection['bbox'],
            'class': detection['class'],
            'confidence': detection['confidence'],
            'history': deque([centroid], maxlen=20)  # 保留更长的历史轨迹
        }
        
        self.cumulative_ids.add(track_id)
        self.cumulative_counts_by_class[detection['class']].add(track_id)
        
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
        
        track_centroids = []
        track_ids = []
        
        for track_id, track in self.tracks.items():
            track_centroids.append(track['centroid'])
            track_ids.append(track_id)
        
        distance_matrix = np.zeros((len(track_centroids), len(detection_centroids)))
        
        for i, track_centroid in enumerate(track_centroids):
            for j, detection_info in enumerate(detection_centroids):
                distance = self.calculate_distance(track_centroid, detection_info['centroid'])
                distance_matrix[i][j] = distance
        
        used_detection_indices = set()
        used_track_indices = set()
        
        matches = []
        for i in range(len(track_centroids)):
            for j in range(len(detection_centroids)):
                if distance_matrix[i][j] < self.max_distance:
                    matches.append((i, j, distance_matrix[i][j]))
        
        matches.sort(key=lambda x: x[2])
        
        for track_idx, detection_idx, distance in matches:
            if track_idx not in used_track_indices and detection_idx not in used_detection_indices:
                track_id = track_ids[track_idx]
                detection_info = detection_centroids[detection_idx]
                detection = detection_info['detection']
                centroid = detection_info['centroid']
                
                self.tracks[track_id]['centroid'] = centroid
                self.tracks[track_id]['disappeared'] = 0
                self.tracks[track_id]['bbox'] = detection['bbox']
                self.tracks[track_id]['class'] = detection['class']
                self.tracks[track_id]['confidence'] = detection['confidence']
                self.tracks[track_id]['history'].append(centroid)
                
                self.cumulative_ids.add(track_id)
                self.cumulative_counts_by_class[detection['class']].add(track_id)
                
                used_track_indices.add(track_idx)
                used_detection_indices.add(detection_idx)
        
        for j, detection_info in enumerate(detection_centroids):
            if j not in used_detection_indices:
                self._create_new_track(detection_info)
        
        for i, track_id in enumerate(track_ids):
            if i not in used_track_indices:
                self.tracks[track_id]['disappeared'] += 1
    
    def get_current_tracks(self):
        """获取当前活跃的轨迹"""
        tracking_results = []
        for track_id, track in self.tracks.items():
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
            if track['disappeared'] == 0:
                counts[track['class']] += 1
        return dict(counts)
    
    def get_cumulative_counts(self):
        """获取累积计数统计"""
        counts = {}
        for class_name, id_set in self.cumulative_counts_by_class.items():
            counts[class_name] = len(id_set)
        return counts
    
    def reset(self):
        """重置跟踪器"""
        self.tracks = {}
        self.next_id = 1
        self.cumulative_ids = set()
        self.cumulative_counts_by_class = defaultdict(set)
        self.new_targets_this_frame = []

class RTSPStreamHandler:
    """RTSP流处理器"""
    
    def __init__(self, stream_config):
        self.stream_config = stream_config
        self.is_running = False
        self.cap = None
        self.model = None
        self.tracker = ObjectTracker()
        self.thread = None
        self.frame_queue = queue.Queue(maxsize=5)  # 限制队列大小防止内存占用过多
        self.latest_frame = None
        self.latest_detections = []
        self.latest_tracking_results = []
        self.latest_counts = {}
        self.latest_alerts = []
        self.frame_count = 0
        self.fps = 0
        self.last_fps_time = time.time()
        self.last_fps_count = 0
        
        # 错误重连相关
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # 秒
        
    def load_model(self, model_path):
        """加载YOLO模型"""
        try:
            self.model = YOLO(model_path)
            print(f"✅ RTSP流 {self.stream_config['name']} 模型加载成功: {model_path}")
            return True
        except Exception as e:
            print(f"❌ RTSP流 {self.stream_config['name']} 模型加载失败: {e}")
            return False
    
    def start(self):
        """启动RTSP流处理"""
        if self.is_running:
            return False
        
        if not self.model:
            print(f"❌ RTSP流 {self.stream_config['name']} 未加载模型")
            return False
        
        self.is_running = True
        self.thread = threading.Thread(target=self._process_stream, daemon=True)
        self.thread.start()
        print(f"🚀 RTSP流 {self.stream_config['name']} 开始处理")
        return True
    
    def stop(self):
        """停止RTSP流处理"""
        self.is_running = False
        if self.cap:
            self.cap.release()
        if self.thread:
            self.thread.join(timeout=5)
        print(f"⏹️ RTSP流 {self.stream_config['name']} 已停止")
    
    def _connect_rtsp(self):
        """连接RTSP流或本地视频文件"""
        try:
            rtsp_url = self.stream_config['url']
            
            # 检查是否为本地文件路径
            if self._is_local_file(rtsp_url):
                print(f"📁 检测到本地文件: {rtsp_url}")
                if not os.path.exists(rtsp_url):
                    print(f"❌ RTSP流 {self.stream_config['name']} 本地文件不存在: {rtsp_url}")
                    return False
                
                self.cap = cv2.VideoCapture(rtsp_url)
                print(f"🎬 使用本地视频文件作为流源")
                
            else:
                # 处理RTSP URL
                # 如果有用户名和密码，构建认证URL
                if self.stream_config.get('username') and self.stream_config.get('password'):
                    # 解析URL并插入认证信息
                    if '://' in rtsp_url:
                        protocol, rest = rtsp_url.split('://', 1)
                        rtsp_url = f"{protocol}://{self.stream_config['username']}:{self.stream_config['password']}@{rest}"
                
                self.cap = cv2.VideoCapture(rtsp_url)
                # 设置缓冲区大小和参数优化（仅对RTSP流）
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 减少缓冲延迟
                self.cap.set(cv2.CAP_PROP_FPS, 15)  # 限制帧率降低计算负担
            
            if self.cap.isOpened():
                # 测试读取一帧
                ret, frame = self.cap.read()
                if ret:
                    print(f"✅ RTSP流 {self.stream_config['name']} 连接成功")
                    self.reconnect_attempts = 0
                    return True
                else:
                    print(f"❌ RTSP流 {self.stream_config['name']} 无法读取帧")
                    self.cap.release()
                    return False
            else:
                print(f"❌ RTSP流 {self.stream_config['name']} 连接失败")
                return False
        except Exception as e:
            print(f"❌ RTSP流 {self.stream_config['name']} 连接异常: {e}")
            return False
    
    def _is_local_file(self, url):
        """检查URL是否为本地文件路径"""
        # 检查是否为文件协议
        if url.startswith('file://'):
            return True
        
        # 检查是否为Windows绝对路径
        if len(url) > 1 and url[1] == ':' and url[0].isalpha():
            return True
        
        # 检查是否为Linux/Mac绝对路径
        if url.startswith('/'):
            return True
        
        # 检查是否为相对路径且存在对应文件
        if os.path.exists(url):
            return True
        
        # 检查常见视频文件扩展名
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
        if any(url.lower().endswith(ext) for ext in video_extensions):
            return True
        
        return False
    
    def _process_stream(self):
        """处理RTSP流的主循环"""
        while self.is_running:
            try:
                # 尝试连接RTSP流
                if not self._connect_rtsp():
                    self._handle_reconnect()
                    continue
                
                print(f"🎥 RTSP流 {self.stream_config['name']} 开始处理帧")
                
                while self.is_running and self.cap and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    
                    if not ret:
                        # 检查是否为本地文件，如果是则循环播放
                        if self._is_local_file(self.stream_config['url']):
                            print(f"🔄 本地视频文件播放完毕，重新开始循环播放...")
                            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 重置到第一帧
                            ret, frame = self.cap.read()
                            if not ret:
                                print(f"⚠️ RTSP流 {self.stream_config['name']} 重新读取帧失败")
                                break
                        else:
                            print(f"⚠️ RTSP流 {self.stream_config['name']} 读取帧失败")
                            break
                    
                    # 更新帧计数和FPS
                    self.frame_count += 1
                    self._update_fps()
                    
                    # 调整帧大小以提高处理速度
                    frame = self._resize_frame(frame)
                    
                    # 更新最新帧
                    self.latest_frame = frame.copy()
                    
                    # 每5帧进行一次检测（降低CPU负载）
                    if self.frame_count % 5 == 0 and self.stream_config.get('detection_enabled', True):
                        self._detect_frame(frame)
                    
                    # 短暂休眠避免过度占用CPU
                    time.sleep(0.033)  # 约30FPS
                
                # 如果退出循环，说明连接断开
                if self.is_running:
                    print(f"⚠️ RTSP流 {self.stream_config['name']} 连接断开，尝试重连")
                    self._handle_reconnect()
                
            except Exception as e:
                print(f"❌ RTSP流 {self.stream_config['name']} 处理异常: {e}")
                if self.is_running:
                    self._handle_reconnect()
                else:
                    break
        
        # 清理资源
        if self.cap:
            self.cap.release()
        print(f"🔚 RTSP流 {self.stream_config['name']} 处理线程结束")
    
    def _resize_frame(self, frame, max_width=640):
        """调整帧大小以提高处理速度"""
        height, width = frame.shape[:2]
        if width > max_width:
            ratio = max_width / width
            new_width = max_width
            new_height = int(height * ratio)
            frame = cv2.resize(frame, (new_width, new_height))
        return frame
    
    def _detect_frame(self, frame):
        """检测单帧"""
        try:
            if not self.model:
                return
            
            # YOLO检测
            results = self.model(frame)
            
            detections = []
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        cls = box.cls[0].cpu().numpy()
                        
                        if conf > 0.3:  # 置信度阈值
                            detections.append({
                                'class': self.model.names[int(cls)],
                                'confidence': float(conf),
                                'bbox': [float(x1), float(y1), float(x2), float(y2)]
                            })
            
            self.latest_detections = detections
            
            # 如果启用跟踪
            if self.stream_config.get('tracking_enabled', False):
                height, width = frame.shape[:2]
                
                # 设置预警
                if self.stream_config.get('alert_enabled', False):
                    self.tracker.set_alert_enabled(True)
                
                tracking_results = self.tracker.update(detections, height)
                self.latest_tracking_results = tracking_results
                
                # 获取计数
                if self.stream_config.get('counting_enabled', False):
                    self.latest_counts = self.tracker.get_current_counts()
                
                # 获取预警
                if self.stream_config.get('alert_enabled', False):
                    new_targets = self.tracker.get_new_targets()
                    if new_targets:
                        self.latest_alerts.extend(new_targets)
                        # 保存预警帧
                        self._save_alert_frames(frame, new_targets)
                        # 限制预警列表大小
                        if len(self.latest_alerts) > 50:
                            self.latest_alerts = self.latest_alerts[-50:]
            
        except Exception as e:
            print(f"❌ RTSP流 {self.stream_config['name']} 检测失败: {e}")
    
    def _save_alert_frames(self, frame, new_targets):
        """保存预警帧"""
        try:
            alert_dir = os.path.join('static', 'alerts', 'rtsp')
            os.makedirs(alert_dir, exist_ok=True)
            
            for target in new_targets:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                filename = f'rtsp_alert_{self.stream_config["id"]}_{timestamp}_id{target["id"]}.jpg'
                filepath = os.path.join(alert_dir, filename)
                
                # 在帧上绘制预警信息
                frame_copy = frame.copy()
                x1, y1, x2, y2 = target['bbox']
                
                cv2.rectangle(frame_copy, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 3)
                
                alert_label = f'ALERT! {target["class"]} ID:{target["id"]}'
                cv2.putText(frame_copy, alert_label, (int(x1), int(y1) - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                cv2.imwrite(filepath, frame_copy)
                
                # 更新target信息，添加图片路径
                target['alert_image'] = os.path.join('alerts', 'rtsp', filename)
                
        except Exception as e:
            print(f"❌ 保存RTSP预警帧失败: {e}")
    
    def _update_fps(self):
        """更新FPS统计"""
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:  # 每秒更新一次
            self.fps = self.frame_count - self.last_fps_count
            self.last_fps_count = self.frame_count
            self.last_fps_time = current_time
    
    def _handle_reconnect(self):
        """处理重连逻辑"""
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts <= self.max_reconnect_attempts:
            print(f"🔄 RTSP流 {self.stream_config['name']} 第 {self.reconnect_attempts} 次重连，等待 {self.reconnect_delay} 秒...")
            time.sleep(self.reconnect_delay)
        else:
            print(f"❌ RTSP流 {self.stream_config['name']} 重连次数达到上限，停止处理")
            self.is_running = False
    
    def get_latest_frame_base64(self):
        """获取最新帧的base64编码"""
        if self.latest_frame is None:
            return None
        
        try:
            # 编码为JPEG
            _, buffer = cv2.imencode('.jpg', self.latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{frame_base64}"
        except Exception as e:
            print(f"❌ 编码帧失败: {e}")
            return None
    
    def get_status(self):
        """获取流状态"""
        return {
            'is_running': self.is_running,
            'frame_count': self.frame_count,
            'fps': self.fps,
            'reconnect_attempts': self.reconnect_attempts,
            'detection_count': len(self.latest_detections),
            'tracking_count': len(self.latest_tracking_results),
            'alert_count': len(self.latest_alerts)
        }
    
    def get_detection_results(self):
        """获取最新的检测结果"""
        return {
            'detections': self.latest_detections.copy(),
            'tracking_results': self.latest_tracking_results.copy() if self.stream_config.get('tracking_enabled', False) else [],
            'counts': self.latest_counts.copy() if self.stream_config.get('counting_enabled', False) else {},
            'alerts': self.latest_alerts.copy() if self.stream_config.get('alert_enabled', False) else []
        }
    
    def reset_tracker(self):
        """重置跟踪器"""
        self.tracker.reset()
        self.latest_tracking_results = []
        self.latest_counts = {}
        self.latest_alerts = []

class RTSPManager:
    """RTSP流管理器"""
    
    def __init__(self):
        self.handlers = {}  # stream_id -> RTSPStreamHandler
        self.models = {}    # model_path -> YOLO model (模型缓存)
    
    def add_stream(self, stream_config):
        """添加RTSP流"""
        stream_id = stream_config['id']
        
        if stream_id in self.handlers:
            self.remove_stream(stream_id)
        
        handler = RTSPStreamHandler(stream_config)
        
        # 加载模型
        model_path = stream_config.get('model_path', 'yolov8n.pt')
        if model_path not in self.models:
            try:
                self.models[model_path] = YOLO(model_path)
                print(f"✅ 加载模型: {model_path}")
            except Exception as e:
                print(f"❌ 加载模型失败: {model_path}, {e}")
                return False
        
        handler.model = self.models[model_path]
        self.handlers[stream_id] = handler
        
        return True
    
    def remove_stream(self, stream_id):
        """移除RTSP流"""
        if stream_id in self.handlers:
            self.handlers[stream_id].stop()
            del self.handlers[stream_id]
            print(f"🗑️ 移除RTSP流: {stream_id}")
    
    def start_stream(self, stream_id):
        """启动指定流"""
        if stream_id in self.handlers:
            return self.handlers[stream_id].start()
        return False
    
    def stop_stream(self, stream_id):
        """停止指定流"""
        if stream_id in self.handlers:
            self.handlers[stream_id].stop()
    
    def start_all_streams(self):
        """启动所有流"""
        results = {}
        for stream_id, handler in self.handlers.items():
            results[stream_id] = handler.start()
        return results
    
    def stop_all_streams(self):
        """停止所有流"""
        for handler in self.handlers.values():
            handler.stop()
    
    def get_stream_frame(self, stream_id):
        """获取指定流的最新帧"""
        if stream_id in self.handlers:
            return self.handlers[stream_id].get_latest_frame_base64()
        return None
    
    def get_stream_status(self, stream_id):
        """获取指定流的状态"""
        if stream_id in self.handlers:
            return self.handlers[stream_id].get_status()
        return None
    
    def get_all_streams_status(self):
        """获取所有流的状态"""
        status = {}
        for stream_id, handler in self.handlers.items():
            status[stream_id] = handler.get_status()
        return status
    
    def get_stream_detections(self, stream_id):
        """获取指定流的检测结果"""
        if stream_id in self.handlers:
            return self.handlers[stream_id].get_detection_results()
        return None
    
    def update_stream_config(self, stream_id, new_config):
        """更新流配置"""
        if stream_id in self.handlers:
            handler = self.handlers[stream_id]
            handler.stream_config.update(new_config)
            
            # 如果模型路径变了，需要重新加载模型
            model_path = new_config.get('model_path')
            if model_path and model_path != handler.model:
                if model_path not in self.models:
                    try:
                        self.models[model_path] = YOLO(model_path)
                    except Exception as e:
                        print(f"❌ 更新模型失败: {model_path}, {e}")
                        return False
                handler.model = self.models[model_path]
            
            return True
        return False
    
    def reset_stream_tracker(self, stream_id):
        """重置指定流的跟踪器"""
        if stream_id in self.handlers:
            self.handlers[stream_id].reset_tracker()
            return True
        return False
    
    def cleanup(self):
        """清理所有资源"""
        self.stop_all_streams()
        self.handlers.clear()
        self.models.clear()

# 全局RTSP管理器实例
rtsp_manager = RTSPManager() 