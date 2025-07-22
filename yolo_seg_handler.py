import cv2
import numpy as np
from ultralytics import YOLO
import torch
import json
import colorsys
from typing import List, Dict, Any, Tuple, Optional

class YOLOSegmentationHandler:
    """YOLO分割算法处理器"""
    
    def __init__(self, model_path: str = None):
        """
        初始化YOLO分割处理器
        
        Args:
            model_path: 模型路径，如果为None则使用默认的YOLOv8n-seg模型
        """
        self.model = None
        self.model_path = model_path or 'yolov8n-seg.pt'
        self.class_colors = {}  # 存储每个类别的颜色
        self.load_model()
        
    def load_model(self) -> bool:
        """
        加载YOLO分割模型
        
        Returns:
            bool: 加载成功返回True，失败返回False
        """
        try:
            print(f"🔄 正在加载YOLO分割模型: {self.model_path}")
            self.model = YOLO(self.model_path)
            print(f"✅ YOLO分割模型加载成功: {self.model_path}")
            
            # 为每个类别生成颜色
            self._generate_class_colors()
            return True
        except Exception as e:
            print(f"❌ YOLO分割模型加载失败: {e}")
            return False
    
    def _generate_class_colors(self):
        """为每个类别生成不同的颜色"""
        if not self.model or not hasattr(self.model, 'names'):
            return
            
        num_classes = len(self.model.names)
        for i, class_name in self.model.names.items():
            # 使用HSV色彩空间生成均匀分布的颜色
            hue = i / num_classes
            saturation = 0.8
            value = 0.9
            rgb = colorsys.hsv_to_rgb(hue, saturation, value)
            # 转换为BGR格式 (OpenCV使用BGR)
            bgr = (int(rgb[2] * 255), int(rgb[1] * 255), int(rgb[0] * 255))
            self.class_colors[i] = bgr
    
    def predict(self, source, conf: float = 0.25, iou: float = 0.45, **kwargs) -> List[Dict[str, Any]]:
        """
        执行分割预测
        
        Args:
            source: 输入源（图片路径、numpy数组等）
            conf: 置信度阈值
            iou: IoU阈值
            **kwargs: 其他参数
            
        Returns:
            List[Dict]: 预测结果列表
        """
        if not self.model:
            raise ValueError("模型未加载，请先调用load_model()")
        
        try:
            # 执行推理
            results = self.model(source, conf=conf, iou=iou, **kwargs)
            
            # 解析结果
            parsed_results = []
            for result in results:
                parsed_result = self._parse_result(result)
                parsed_results.append(parsed_result)
            
            return parsed_results
        except Exception as e:
            print(f"❌ 分割预测失败: {e}")
            return []
    
    def _parse_result(self, result) -> Dict[str, Any]:
        """
        解析单个预测结果
        
        Args:
            result: YOLO预测结果
            
        Returns:
            Dict: 解析后的结果
        """
        parsed = {
            'boxes': [],
            'masks': [],
            'segments': [],
            'confidences': [],
            'classes': [],
            'class_names': []
        }
        
        # 处理检测框
        if hasattr(result, 'boxes') and result.boxes is not None:
            boxes = result.boxes
            if len(boxes) > 0:
                parsed['boxes'] = boxes.xyxy.cpu().numpy().tolist()
                parsed['confidences'] = boxes.conf.cpu().numpy().tolist()
                parsed['classes'] = boxes.cls.cpu().numpy().tolist()
                parsed['class_names'] = [self.model.names[int(cls)] for cls in parsed['classes']]
        
        # 处理分割掩码
        if hasattr(result, 'masks') and result.masks is not None:
            masks = result.masks
            if len(masks) > 0:
                # 获取掩码数据
                masks_data = masks.data.cpu().numpy()
                parsed['masks'] = masks_data
                
                # 如果有xy坐标，也保存
                if hasattr(masks, 'xy') and masks.xy is not None:
                    parsed['segments'] = [seg.tolist() for seg in masks.xy]
        
        return parsed
    
    def visualize_segmentation(self, image: np.ndarray, results: Dict[str, Any], 
                             show_boxes: bool = True, show_masks: bool = True,
                             show_labels: bool = True, mask_alpha: float = 0.4) -> np.ndarray:
        """
        可视化分割结果
        
        Args:
            image: 原始图像
            results: 预测结果
            show_boxes: 是否显示检测框
            show_masks: 是否显示分割掩码
            show_labels: 是否显示标签
            mask_alpha: 掩码透明度
            
        Returns:
            np.ndarray: 可视化后的图像
        """
        if not results:
            return image
        
        vis_image = image.copy()
        
        # 创建掩码叠加层
        if show_masks and 'masks' in results and len(results['masks']) > 0:
            vis_image = self._draw_masks(vis_image, results, mask_alpha)
        
        # 绘制检测框和标签
        if (show_boxes or show_labels) and 'boxes' in results:
            vis_image = self._draw_boxes_and_labels(vis_image, results, show_boxes, show_labels)
        
        return vis_image
    
    def _draw_masks(self, image: np.ndarray, results: Dict[str, Any], alpha: float = 0.4) -> np.ndarray:
        """绘制分割掩码"""
        if 'masks' not in results or len(results['masks']) == 0:
            return image
        
        masks = results['masks']
        classes = results.get('classes', [])
        
        # 创建彩色掩码图层
        overlay = image.copy()
        
        for i, mask in enumerate(masks):
            if i >= len(classes):
                continue
                
            class_id = int(classes[i])
            color = self.class_colors.get(class_id, (0, 255, 0))
            
            # 调整掩码尺寸到图像尺寸
            if mask.shape != image.shape[:2]:
                mask_resized = cv2.resize(mask.astype(np.uint8), 
                                        (image.shape[1], image.shape[0]), 
                                        interpolation=cv2.INTER_NEAREST)
            else:
                mask_resized = mask.astype(np.uint8)
            
            # 创建彩色掩码
            colored_mask = np.zeros_like(image)
            colored_mask[mask_resized > 0] = color
            
            # 混合掩码
            overlay = cv2.addWeighted(overlay, 1 - alpha, colored_mask, alpha, 0)
        
        return overlay
    
    def _draw_boxes_and_labels(self, image: np.ndarray, results: Dict[str, Any], 
                              show_boxes: bool = True, show_labels: bool = True) -> np.ndarray:
        """绘制检测框和标签"""
        if 'boxes' not in results or len(results['boxes']) == 0:
            return image
        
        boxes = results['boxes']
        confidences = results.get('confidences', [])
        class_names = results.get('class_names', [])
        classes = results.get('classes', [])
        
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box)
            
            # 获取类别信息
            class_id = int(classes[i]) if i < len(classes) else 0
            color = self.class_colors.get(class_id, (0, 255, 0))
            confidence = confidences[i] if i < len(confidences) else 0.0
            class_name = class_names[i] if i < len(class_names) else 'Unknown'
            
            # 绘制检测框
            if show_boxes:
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签
            if show_labels:
                label = f'{class_name}: {confidence:.2f}'
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                
                # 标签背景
                cv2.rectangle(image, (x1, y1 - label_size[1] - 10), 
                            (x1 + label_size[0] + 10, y1), color, -1)
                
                # 标签文字
                cv2.putText(image, label, (x1 + 5, y1 - 5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return image
    
    def process_video_segmentation(self, input_path: str, output_path: str, 
                                 conf: float = 0.25, iou: float = 0.45,
                                 show_boxes: bool = True, show_masks: bool = True,
                                 show_labels: bool = True, mask_alpha: float = 0.4,
                                 progress_callback=None) -> Dict[str, Any]:
        """
        处理视频分割
        
        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            conf: 置信度阈值
            iou: IoU阈值
            show_boxes: 是否显示检测框
            show_masks: 是否显示分割掩码
            show_labels: 是否显示标签
            mask_alpha: 掩码透明度
            progress_callback: 进度回调函数
            
        Returns:
            Dict: 处理结果统计
        """
        if not self.model:
            raise ValueError("模型未加载")
        
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频文件: {input_path}")
        
        # 获取视频属性
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 设置视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        all_results = []
        frame_count = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 执行分割
                results = self.predict(frame, conf=conf, iou=iou)
                
                if results:
                    result = results[0]  # 取第一个结果
                    all_results.append({
                        'frame': frame_count,
                        'detections': len(result.get('boxes', [])),
                        'masks': len(result.get('masks', [])),
                        'result': result
                    })
                    
                    # 可视化
                    vis_frame = self.visualize_segmentation(
                        frame, result, show_boxes, show_masks, show_labels, mask_alpha
                    )
                else:
                    vis_frame = frame
                    all_results.append({
                        'frame': frame_count,
                        'detections': 0,
                        'masks': 0,
                        'result': {}
                    })
                
                # 写入帧
                out.write(vis_frame)
                frame_count += 1
                
                # 回调进度
                if progress_callback:
                    progress = frame_count / total_frames * 100
                    progress_callback(progress, frame_count, total_frames)
        
        finally:
            cap.release()
            out.release()
        
        # 统计结果
        total_detections = sum(r['detections'] for r in all_results)
        total_masks = sum(r['masks'] for r in all_results)
        
        return {
            'total_frames': frame_count,
            'total_detections': total_detections,
            'total_masks': total_masks,
            'results': all_results,
            'average_detections_per_frame': total_detections / frame_count if frame_count > 0 else 0
        }
    
    def get_supported_models(self) -> List[str]:
        """获取支持的分割模型列表"""
        return [
            'yolov8n-seg.pt',
            'yolov8s-seg.pt', 
            'yolov8m-seg.pt',
            'yolov8l-seg.pt',
            'yolov8x-seg.pt',
            'yolov9c-seg.pt',
            'yolov9e-seg.pt',
            'yolov10n-seg.pt',
            'yolov10s-seg.pt',
            'yolov10m-seg.pt',
            'yolov10l-seg.pt',
            'yolov10x-seg.pt',
        ]
    
    def export_segmentation_results(self, results: List[Dict[str, Any]], 
                                  format: str = 'json') -> str:
        """
        导出分割结果
        
        Args:
            results: 分割结果列表
            format: 导出格式 ('json', 'csv')
            
        Returns:
            str: 导出的数据字符串
        """
        if format.lower() == 'json':
            return json.dumps(results, indent=2, ensure_ascii=False)
        elif format.lower() == 'csv':
            # 简化的CSV导出
            import csv
            import io
            
            output = io.StringIO()
            if results:
                fieldnames = ['frame', 'detections', 'masks']
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    writer.writerow({
                        'frame': result.get('frame', 0),
                        'detections': result.get('detections', 0), 
                        'masks': result.get('masks', 0)
                    })
            
            return output.getvalue()
        else:
            raise ValueError(f"不支持的导出格式: {format}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        if not self.model:
            return {'loaded': False}
        
        return {
            'loaded': True,
            'model_path': self.model_path,
            'task': 'segment',
            'classes': dict(self.model.names) if hasattr(self.model, 'names') else {},
            'num_classes': len(self.model.names) if hasattr(self.model, 'names') else 0
        } 