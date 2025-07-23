#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水印检测模型处理器
专门用于加载和使用本地的水印检测模型
"""

import cv2
import numpy as np
from ultralytics import YOLO
import torch
import os
from typing import List, Dict, Any, Tuple, Optional

class WatermarkDetector:
    """水印检测器"""
    
    def __init__(self, model_path: str = None):
        """
        初始化水印检测器
        
        Args:
            model_path: 水印检测模型路径
        """
        self.model = None
        self.model_path = model_path
        self.supported_watermark_classes = []
        self.class_names = {}
        
        if model_path and os.path.exists(model_path):
            self.load_model()
    
    def load_model(self) -> bool:
        """
        加载水印检测模型
        
        Returns:
            bool: 加载成功返回True，失败返回False
        """
        try:
            print(f"🔄 正在加载水印检测模型: {self.model_path}")
            
            # 强制使用CPU避免CUDA问题
            self.model = YOLO(self.model_path)
            if hasattr(self.model, 'names'):
                self.class_names = self.model.names
                self.supported_watermark_classes = list(self.class_names.values())
                
            print(f"✅ 水印检测模型加载成功: {self.model_path}")
            print(f"📋 支持的水印类别: {self.supported_watermark_classes}")
            return True
            
        except Exception as e:
            print(f"❌ 水印检测模型加载失败: {e}")
            return False
    
    def detect_watermarks(self, image, confidence_threshold: float = 0.25) -> List[Dict]:
        """
        检测图像中的水印
        
        Args:
            image: 输入图像 (numpy array)
            confidence_threshold: 置信度阈值
            
        Returns:
            List[Dict]: 检测到的水印信息列表
        """
        if self.model is None:
            print("❌ 水印检测模型未加载")
            return []
        
        try:
            # 使用模型进行检测
            results = self.model(image, conf=confidence_threshold, verbose=False)
            
            watermarks = []
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        # 获取检测框信息
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0].cpu().numpy())
                        cls = int(box.cls[0].cpu().numpy())
                        
                        # 获取类别名称
                        class_name = self.class_names.get(cls, f'class_{cls}')
                        
                        watermark_info = {
                            'type': class_name,
                            'confidence': conf,
                            'bbox': [float(x1), float(y1), float(x2), float(y2)],
                            'class_id': cls,
                            'removed': False,
                            'method': 'yolo_detection',
                            'area': (x2 - x1) * (y2 - y1)
                        }
                        
                        watermarks.append(watermark_info)
            
            # 按置信度排序
            watermarks.sort(key=lambda x: x['confidence'], reverse=True)
            
            print(f"🔍 检测到 {len(watermarks)} 个水印区域")
            for wm in watermarks:
                print(f"   - {wm['type']}: {wm['confidence']:.2f} at {wm['bbox']}")
            
            return watermarks
            
        except Exception as e:
            print(f"❌ 水印检测失败: {e}")
            return []
    
    def visualize_detections(self, image, watermarks: List[Dict], 
                           show_labels: bool = True, 
                           box_color: Tuple[int, int, int] = (0, 255, 255)) -> np.ndarray:
        """
        可视化水印检测结果
        
        Args:
            image: 原始图像
            watermarks: 水印检测结果
            show_labels: 是否显示标签
            box_color: 检测框颜色 (B, G, R)
            
        Returns:
            np.ndarray: 带有检测框的图像
        """
        result_img = image.copy()
        
        for watermark in watermarks:
            bbox = watermark['bbox']
            x1, y1, x2, y2 = map(int, bbox)
            
            # 绘制检测框
            cv2.rectangle(result_img, (x1, y1), (x2, y2), box_color, 2)
            
            if show_labels:
                # 绘制标签
                label = f"{watermark['type']}: {watermark['confidence']:.2f}"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                
                # 标签背景
                cv2.rectangle(result_img, (x1, y1 - label_size[1] - 10), 
                            (x1 + label_size[0], y1), box_color, -1)
                
                # 标签文字
                cv2.putText(result_img, label, (x1, y1 - 5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return result_img
    
    def get_model_info(self) -> Dict:
        """
        获取模型信息
        
        Returns:
            Dict: 模型信息
        """
        if self.model is None:
            return {
                'loaded': False,
                'model_path': self.model_path,
                'classes': [],
                'class_count': 0
            }
        
        return {
            'loaded': True,
            'model_path': self.model_path,
            'classes': self.supported_watermark_classes,
            'class_count': len(self.supported_watermark_classes),
            'class_names': self.class_names
        }

# 全局水印检测器实例
watermark_detector = None

def load_watermark_detector(model_path: str) -> bool:
    """
    加载水印检测器
    
    Args:
        model_path: 模型文件路径
        
    Returns:
        bool: 加载成功返回True
    """
    global watermark_detector
    
    if not os.path.exists(model_path):
        print(f"❌ 水印检测模型文件不存在: {model_path}")
        return False
    
    watermark_detector = WatermarkDetector(model_path)
    return watermark_detector.model is not None

def detect_watermarks_in_image(image, confidence_threshold: float = 0.25) -> List[Dict]:
    """
    在图像中检测水印
    
    Args:
        image: 输入图像
        confidence_threshold: 置信度阈值
        
    Returns:
        List[Dict]: 检测结果
    """
    global watermark_detector
    
    if watermark_detector is None:
        print("❌ 水印检测器未初始化")
        return []
    
    return watermark_detector.detect_watermarks(image, confidence_threshold)

def get_watermark_detector_info() -> Dict:
    """
    获取水印检测器信息
    
    Returns:
        Dict: 检测器信息
    """
    global watermark_detector
    
    if watermark_detector is None:
        return {'loaded': False, 'model_path': None, 'classes': []}
    
    return watermark_detector.get_model_info()

if __name__ == "__main__":
    # 测试代码
    test_model_path = "xueshengxingwei_yolov8n.pt"  # 替换为您的模型路径
    
    if os.path.exists(test_model_path):
        detector = WatermarkDetector(test_model_path)
        print("测试完成")
    else:
        print(f"测试模型文件不存在: {test_model_path}") 