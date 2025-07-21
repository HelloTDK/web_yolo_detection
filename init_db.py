#!/usr/bin/env python3
"""
数据库初始化脚本 - SQLite版本
用于创建数据库表和初始数据
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, DetectionResult

def create_database():
    """创建数据库表"""
    print("🔨 创建数据库表...")
    
    with app.app_context():
        try:
            # 删除所有表（如果存在）
            db.drop_all()
            print("🗑️  删除旧表完成")
            
            # 创建所有表
            db.create_all()
            print("✅ 数据库表创建完成")
            
            return True
        except Exception as e:
            print(f"❌ 数据库表创建失败: {e}")
            return False

def create_initial_data():
    """创建初始数据"""
    print("📋 创建初始数据...")
    
    with app.app_context():
        try:
            # 检查是否已存在管理员用户
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                # 创建管理员用户
                admin_user = User(
                    username='admin',
                    password='admin123'  # 在实际应用中应该使用哈希密码
                )
                db.session.add(admin_user)
                print("👤 创建管理员用户: admin / admin123")
            else:
                print("👤 管理员用户已存在")
            
            # 创建测试用户
            test_user = User.query.filter_by(username='test').first()
            if not test_user:
                test_user = User(
                    username='test',
                    password='test123'
                )
                db.session.add(test_user)
                print("👤 创建测试用户: test / test123")
            else:
                print("👤 测试用户已存在")
            
            # 提交更改
            db.session.commit()
            print("✅ 初始数据创建完成")
            
            return True
        except Exception as e:
            print(f"❌ 初始数据创建失败: {e}")
            db.session.rollback()
            return False

def check_database_connection():
    """检查数据库连接 - SQLite版本"""
    print("🔍 检查数据库连接...")
    
    with app.app_context():
        try:
            # 尝试执行简单查询
            db.session.execute('SELECT 1')
            print("✅ SQLite数据库连接正常")
            return True
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            return False

def show_database_info():
    """显示数据库信息"""
    print("\n📊 数据库信息:")
    
    with app.app_context():
        try:
            # 显示数据库文件位置
            db_path = os.path.abspath('yolo_detection.db')
            print(f"📁 数据库文件: {db_path}")
            
            # 显示用户统计
            user_count = User.query.count()
            print(f"👥 用户总数: {user_count}")
            
            # 显示检测记录统计
            detection_count = DetectionResult.query.count()
            print(f"🔍 检测记录总数: {detection_count}")
            
            # 显示各类型检测统计
            image_count = DetectionResult.query.filter_by(detection_type='image').count()
            video_count = DetectionResult.query.filter_by(detection_type='video').count()
            camera_count = DetectionResult.query.filter_by(detection_type='camera').count()
            
            print(f"📷 图片检测: {image_count}")
            print(f"🎬 视频检测: {video_count}")
            print(f"📹 摄像头检测: {camera_count}")
            
        except Exception as e:
            print(f"❌ 获取数据库信息失败: {e}")

def main():
    """主函数"""
    print("=" * 50)
    print("🗄️  YOLO检测系统数据库初始化 (SQLite)")
    print("=" * 50)
    
    # SQLite不需要复杂的连接检查，直接创建
    print("📋 选择操作:")
    print("1. 完整初始化 (创建表 + 初始数据)")
    print("2. 仅创建数据库表")
    print("3. 仅创建初始数据")
    print("4. 查看数据库信息")
    print("5. 退出")
    
    while True:
        choice = input("\n请选择操作 (1-5): ").strip()
        
        if choice == "1":
            # 完整初始化
            print("\n🚀 开始完整初始化...")
            if create_database() and create_initial_data():
                print("\n🎉 数据库初始化完成!")
                show_database_info()
            else:
                print("\n❌ 数据库初始化失败")
            break
            
        elif choice == "2":
            # 仅创建表
            if create_database():
                print("\n🎉 数据库表创建完成!")
            else:
                print("\n❌ 数据库表创建失败")
            break
            
        elif choice == "3":
            # 仅创建初始数据
            if create_initial_data():
                print("\n🎉 初始数据创建完成!")
            else:
                print("\n❌ 初始数据创建失败")
            break
            
        elif choice == "4":
            # 查看数据库信息
            show_database_info()
            break
            
        elif choice == "5":
            print("👋 退出初始化程序")
            sys.exit(0)
            
        else:
            print("❌ 无效选择，请输入1-5")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，退出程序")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        sys.exit(1) 