#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU模式启动脚本
专门用于在CPU环境下运行YOLO检测系统，避免CUDA相关问题
"""

import os
import sys

# 强制设置环境变量，确保使用CPU
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['TORCH_DEVICE'] = 'cpu'
os.environ['YOLO_DEVICE'] = 'cpu'

# 设置OpenCV优化
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'

print("🚀 启动CPU模式YOLO检测系统...")
print("📋 环境配置:")
print(f"   - CUDA设备: {os.environ.get('CUDA_VISIBLE_DEVICES', '未设置')}")
print(f"   - Python版本: {sys.version}")

try:
    import torch
    print(f"   - PyTorch版本: {torch.__version__}")
    print(f"   - CUDA可用: {torch.cuda.is_available()}")
    print(f"   - 设备: CPU (强制)")
    
    # 强制设置CPU
    torch.set_num_threads(4)
    torch.set_num_interop_threads(2)
    
except ImportError:
    print("   - PyTorch: 未安装")

try:
    import cv2
    print(f"   - OpenCV版本: {cv2.__version__}")
    
    # 优化OpenCV CPU性能
    cv2.setNumThreads(4)
    cv2.setUseOptimized(True)
    
except ImportError:
    print("   - OpenCV: 未安装")

try:
    from ultralytics import YOLO
    print("   - YOLO: 已安装")
except ImportError:
    print("   - YOLO: 未安装")

print("\n💡 提示:")
print("   - 系统将使用CPU进行推理，速度相对较慢但稳定")
print("   - 建议使用较小的模型文件（如yolov8n.pt）以获得更好的性能")
print("   - 水印去除功能已优化，使用先进的图像处理算法")

# 检查端口是否可用
import socket

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

if not check_port(5000):
    print("\n⚠️  警告: 端口5000已被占用，可能需要修改端口或停止其他服务")
else:
    print("\n✅ 端口5000可用")

print("\n" + "="*50)
print("启动Flask应用...")
print("="*50)

# 导入并启动应用
if __name__ == '__main__':
    try:
        from app import app, load_yolo_model
        
        # 强制加载CPU版本的模型
        print("\n🔄 加载YOLO检测模型（CPU模式）...")
        success = load_yolo_model('yolov8n.pt')  # 使用最小的模型
        
        if success:
            print("✅ YOLO检测模型加载成功")
        else:
            print("⚠️  YOLO检测模型加载失败，但系统仍可运行基础功能")
        
        # 尝试加载水印检测模型
        print("\n🔍 查找水印检测模型...")
        watermark_model_candidates = [
            'xueshengxingwei_yolov8n.pt',
            'watermark_detection.pt',
            'watermark.pt'
        ]
        
        watermark_model_loaded = False
        for model_file in watermark_model_candidates:
            if os.path.exists(model_file):
                print(f"🔄 加载水印检测模型: {model_file}")
                from watermark_detector import load_watermark_detector
                
                try:
                    success = load_watermark_detector(model_file)
                    if success:
                        print(f"✅ 水印检测模型加载成功: {model_file}")
                        watermark_model_loaded = True
                        break
                    else:
                        print(f"❌ 水印检测模型加载失败: {model_file}")
                except Exception as e:
                    print(f"❌ 加载水印检测模型时出错: {e}")
        
        if not watermark_model_loaded:
            print("⚠️  未找到水印检测模型，将使用备用检测方法")
            print("   提示：将您的水印检测模型文件命名为以下之一并放在项目根目录：")
            for candidate in watermark_model_candidates:
                print(f"   - {candidate}")
        else:
            print("💡 水印去除功能将使用您的本地模型进行精确检测")
        
        print("\n🌐 访问地址:")
        print("   http://localhost:5000")
        print("   http://127.0.0.1:5000")
        print("\n👤 默认账号: admin / admin123")
        print("\n按 Ctrl+C 停止服务")
        print("-" * 50)
        
        # 启动Flask应用
        app.run(
            debug=False,  # 生产模式，避免额外的内存占用
            host='0.0.0.0',
            port=5000,
            threaded=True,  # 启用多线程
            use_reloader=False  # 避免重新加载导致的问题
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    except ImportError as e:
        print(f"\n❌ 导入错误: {e}")
        print("请确保所有依赖已正确安装")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("请检查配置和依赖") 