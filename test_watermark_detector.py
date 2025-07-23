#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水印检测器测试脚本
用于验证水印检测模型是否正常工作
"""

import cv2
import numpy as np
import os
from watermark_detector import WatermarkDetector, load_watermark_detector, get_watermark_detector_info

def test_watermark_detector():
    """测试水印检测器功能"""
    
    print("🧪 开始测试水印检测器...")
    
    # 1. 查找可用的模型文件
    model_candidates = [
        'xueshengxingwei_yolov8n.pt',
        'watermark_detection.pt',
        'watermark.pt'
    ]
    
    model_path = None
    for candidate in model_candidates:
        if os.path.exists(candidate):
            model_path = candidate
            print(f"✅ 找到模型文件: {model_path}")
            break
    
    if model_path is None:
        print("❌ 未找到模型文件！")
        print("请将您的水印检测模型文件放在项目根目录，支持的文件名：")
        for candidate in model_candidates:
            print(f"   - {candidate}")
        return False
    
    # 2. 加载模型
    print(f"🔄 加载模型: {model_path}")
    success = load_watermark_detector(model_path)
    
    if not success:
        print("❌ 模型加载失败！")
        return False
    
    # 3. 获取模型信息
    model_info = get_watermark_detector_info()
    print("📋 模型信息:")
    print(f"   - 已加载: {model_info['loaded']}")
    print(f"   - 模型路径: {model_info['model_path']}")
    print(f"   - 支持类别数: {model_info['class_count']}")
    print(f"   - 类别列表: {model_info['classes']}")
    
    # 4. 创建测试图像（如果没有测试图像的话）
    test_image_path = create_test_image()
    
    # 5. 测试检测功能
    if os.path.exists(test_image_path):
        print(f"🖼️  测试图像: {test_image_path}")
        
        # 读取测试图像
        img = cv2.imread(test_image_path)
        if img is None:
            print("❌ 无法读取测试图像")
            return False
        
        print(f"📏 图像尺寸: {img.shape}")
        
        # 执行检测
        from watermark_detector import detect_watermarks_in_image
        
        print("🔍 开始检测...")
        watermarks = detect_watermarks_in_image(img, confidence_threshold=0.25)
        
        print(f"✅ 检测完成，发现 {len(watermarks)} 个水印")
        
        # 显示检测结果
        for i, wm in enumerate(watermarks):
            print(f"   水印 {i+1}:")
            print(f"     - 类型: {wm['type']}")
            print(f"     - 置信度: {wm['confidence']:.3f}")
            print(f"     - 位置: {wm['bbox']}")
            print(f"     - 面积: {wm.get('area', 0):.0f} 像素")
        
        # 可视化检测结果
        if len(watermarks) > 0:
            visualize_detections(img, watermarks, test_image_path)
        
        return len(watermarks) > 0
    
    else:
        print("❌ 测试图像不存在")
        return False

def create_test_image():
    """创建测试图像（如果没有的话）"""
    test_path = "test_watermark_image.jpg"
    
    if not os.path.exists(test_path):
        print("🎨 创建测试图像...")
        
        # 创建一个简单的测试图像
        img = np.ones((400, 600, 3), dtype=np.uint8) * 255
        
        # 添加一些背景纹理
        cv2.rectangle(img, (50, 50), (550, 350), (200, 200, 200), -1)
        cv2.rectangle(img, (100, 100), (500, 300), (150, 150, 150), -1)
        
        # 添加模拟水印文字
        cv2.putText(img, "WATERMARK", (200, 250), cv2.FONT_HERSHEY_SIMPLEX, 2, (100, 100, 100), 3)
        cv2.putText(img, "Sample Text", (400, 350), cv2.FONT_HERSHEY_SIMPLEX, 1, (120, 120, 120), 2)
        
        # 保存测试图像
        cv2.imwrite(test_path, img)
        print(f"✅ 测试图像已创建: {test_path}")
    
    return test_path

def visualize_detections(img, watermarks, original_path):
    """可视化检测结果"""
    try:
        from watermark_detector import watermark_detector
        
        if watermark_detector is not None:
            # 使用检测器的可视化方法
            result_img = watermark_detector.visualize_detections(img, watermarks)
            
            # 保存可视化结果
            result_path = "detection_result.jpg"
            cv2.imwrite(result_path, result_img)
            print(f"🎯 检测结果已保存: {result_path}")
        else:
            print("⚠️  无法可视化：检测器未初始化")
    
    except Exception as e:
        print(f"⚠️  可视化失败: {e}")

def test_removal_process():
    """测试完整的去除流程"""
    print("\n🧪 测试完整的去除流程...")
    
    # 使用测试图像
    test_image_path = "test_watermark_image.jpg"
    if not os.path.exists(test_image_path):
        test_image_path = create_test_image()
    
    img = cv2.imread(test_image_path)
    if img is None:
        print("❌ 无法读取测试图像")
        return False
    
    # 检测水印
    from watermark_detector import detect_watermarks_in_image
    watermarks = detect_watermarks_in_image(img, confidence_threshold=0.1)  # 降低阈值以获得更多检测
    
    if len(watermarks) == 0:
        print("⚠️  未检测到水印，创建模拟检测结果进行测试...")
        # 创建模拟检测结果
        watermarks = [{
            'type': 'text',
            'confidence': 0.95,
            'bbox': [200, 230, 450, 270],
            'class_id': 0,
            'removed': False,
            'method': 'simulated'
        }]
    
    print(f"🔍 检测到 {len(watermarks)} 个水印，开始去除...")
    
    # 导入去除函数
    import sys
    sys.path.append('.')
    from app import advanced_watermark_removal
    
    # 执行去除
    processed_img, removed_count = advanced_watermark_removal(
        img, watermarks, 
        removal_strength=3,
        edge_repair=True, 
        quality_optimization=True
    )
    
    # 保存结果
    result_path = "removal_test_result.jpg"
    cv2.imwrite(result_path, processed_img)
    
    print(f"✅ 去除测试完成，成功处理 {removed_count} 个水印")
    print(f"🖼️  结果已保存: {result_path}")
    
    return removed_count > 0

if __name__ == "__main__":
    print("🚀 水印检测器测试开始...")
    print("=" * 50)
    
    # 测试检测器
    detection_success = test_watermark_detector()
    
    if detection_success:
        print("\n" + "=" * 50)
        # 测试去除流程
        removal_success = test_removal_process()
        
        print("\n" + "=" * 50)
        if removal_success:
            print("🎉 所有测试通过！水印检测和去除功能正常")
        else:
            print("⚠️  去除功能测试失败")
    else:
        print("\n❌ 检测功能测试失败，请检查模型配置")
    
    print("🏁 测试完成") 