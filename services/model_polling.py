import json
import time
from typing import List, Dict, Optional
from ultralytics import YOLO
import threading

class ModelPolling:
    """模型轮询管理器"""
    
    def __init__(self, polling_config: dict):
        """
        初始化模型轮询器
        
        Args:
            polling_config: {
                'type': 'frame' or 'time',  # 轮询类型
                'interval': int,  # 间隔值（帧数或秒数）
                'models': ['model1.pt', 'model2.pt', ...],  # 模型路径列表
                'order': [0, 1, 2, ...] or None  # 自定义轮询顺序，None表示按模型列表顺序
            }
        """
        self.polling_type = polling_config.get('type', 'frame')
        self.interval = polling_config.get('interval', 10)
        self.model_paths = polling_config.get('models', [])
        self.order = polling_config.get('order') or list(range(len(self.model_paths)))
        
        # 状态变量
        self.current_index = 0  # 当前模型索引
        self.frame_counter = 0  # 帧计数器
        self.last_switch_time = time.time()  # 上次切换时间
        self.loaded_models = {}  # 已加载的模型缓存
        self.lock = threading.Lock()  # 线程锁
        
        # 验证配置
        self._validate_config()
        
        # 预加载所有模型
        self._preload_models()
    
    def _validate_config(self):
        """验证轮询配置"""
        if not self.model_paths:
            raise ValueError("模型路径列表不能为空")
        
        if len(self.model_paths) > 10:
            raise ValueError("最多支持10个模型")
        
        if self.polling_type not in ['frame', 'time']:
            raise ValueError("轮询类型必须是 'frame' 或 'time'")
        
        if self.interval <= 0:
            raise ValueError("轮询间隔必须大于0")
        
        # 验证轮询顺序
        if len(self.order) != len(self.model_paths):
            self.order = list(range(len(self.model_paths)))
        
        # 确保顺序索引在有效范围内
        for idx in self.order:
            if idx < 0 or idx >= len(self.model_paths):
                raise ValueError(f"轮询顺序索引 {idx} 超出模型列表范围")
    
    def _preload_models(self):
        """预加载所有模型"""
        print(f"🔄 开始预加载 {len(self.model_paths)} 个模型...")
        
        for i, model_path in enumerate(self.model_paths):
            try:
                print(f"⏳ 加载模型 {i+1}/{len(self.model_paths)}: {model_path}")
                model = YOLO(model_path)
                self.loaded_models[model_path] = model
                print(f"✅ 模型加载成功: {model_path}")
            except Exception as e:
                print(f"❌ 模型加载失败: {model_path}, 错误: {e}")
                # 如果某个模型加载失败，从列表中移除
                self.model_paths.remove(model_path)
                self.order = [idx for idx in self.order if idx < len(self.model_paths)]
        
        if not self.loaded_models:
            raise RuntimeError("没有成功加载任何模型")
        
        print(f"✅ 模型预加载完成，成功加载 {len(self.loaded_models)} 个模型")
    
    def get_current_model(self) -> Optional[YOLO]:
        """获取当前应该使用的模型"""
        with self.lock:
            if not self.model_paths:
                return None
            
            # 根据轮询类型检查是否需要切换模型
            should_switch = False
            
            if self.polling_type == 'frame':
                if self.frame_counter >= self.interval:
                    should_switch = True
                    self.frame_counter = 0  # 重置帧计数器
            
            elif self.polling_type == 'time':
                current_time = time.time()
                if current_time - self.last_switch_time >= self.interval:
                    should_switch = True
                    self.last_switch_time = current_time  # 重置时间
            
            # 切换到下一个模型
            if should_switch:
                self._switch_to_next_model()
            
            # 增加帧计数器（只有在按帧轮询时才有意义）
            if self.polling_type == 'frame':
                self.frame_counter += 1
            
            # 返回当前模型
            current_model_index = self.order[self.current_index]
            current_model_path = self.model_paths[current_model_index]
            return self.loaded_models.get(current_model_path)
    
    def _switch_to_next_model(self):
        """切换到下一个模型"""
        if len(self.order) > 1:
            self.current_index = (self.current_index + 1) % len(self.order)
            current_model_index = self.order[self.current_index]
            current_model_path = self.model_paths[current_model_index]
            print(f"🔄 模型轮询切换: 切换到模型 {current_model_index + 1} ({current_model_path})")
    
    def get_current_model_info(self) -> Dict:
        """获取当前模型信息"""
        with self.lock:
            if not self.model_paths:
                return {}
            
            current_model_index = self.order[self.current_index]
            current_model_path = self.model_paths[current_model_index]
            
            return {
                'current_index': self.current_index,
                'current_model_index': current_model_index,
                'current_model_path': current_model_path,
                'total_models': len(self.model_paths),
                'polling_type': self.polling_type,
                'interval': self.interval,
                'frame_counter': self.frame_counter if self.polling_type == 'frame' else None,
                'time_since_last_switch': time.time() - self.last_switch_time if self.polling_type == 'time' else None
            }
    
    def reset(self):
        """重置轮询状态"""
        with self.lock:
            self.current_index = 0
            self.frame_counter = 0
            self.last_switch_time = time.time()
            print("🔄 模型轮询状态已重置")
    
    def update_config(self, new_config: dict):
        """更新轮询配置"""
        with self.lock:
            # 保存旧配置
            old_models = self.model_paths.copy()
            
            # 更新配置
            self.polling_type = new_config.get('type', self.polling_type)
            self.interval = new_config.get('interval', self.interval)
            new_models = new_config.get('models', self.model_paths)
            self.order = new_config.get('order') or list(range(len(new_models)))
            
            # 验证新配置
            temp_models = self.model_paths
            self.model_paths = new_models
            try:
                self._validate_config()
            except ValueError as e:
                # 配置无效，恢复旧配置
                self.model_paths = temp_models
                raise e
            
            # 如果模型列表发生变化，重新加载模型
            if set(new_models) != set(old_models):
                # 清理不需要的模型
                for model_path in old_models:
                    if model_path not in new_models and model_path in self.loaded_models:
                        del self.loaded_models[model_path]
                
                # 加载新模型
                for model_path in new_models:
                    if model_path not in self.loaded_models:
                        try:
                            self.loaded_models[model_path] = YOLO(model_path)
                            print(f"✅ 新模型加载成功: {model_path}")
                        except Exception as e:
                            print(f"❌ 新模型加载失败: {model_path}, 错误: {e}")
            
            # 重置状态
            self.reset()
            print("✅ 模型轮询配置已更新")


class ModelPollingManager:
    """模型轮询管理器 - 管理多个流的轮询器"""
    
    def __init__(self):
        self.pollings = {}  # stream_id -> ModelPolling
        self.lock = threading.Lock()
    
    def create_polling(self, stream_id: int, polling_config: dict) -> bool:
        """为指定流创建模型轮询器"""
        try:
            with self.lock:
                if stream_id in self.pollings:
                    self.remove_polling(stream_id)
                
                polling = ModelPolling(polling_config)
                self.pollings[stream_id] = polling
                print(f"✅ 流 {stream_id} 的模型轮询器创建成功")
                return True
        except Exception as e:
            print(f"❌ 创建流 {stream_id} 的模型轮询器失败: {e}")
            return False
    
    def remove_polling(self, stream_id: int):
        """移除指定流的轮询器"""
        with self.lock:
            if stream_id in self.pollings:
                del self.pollings[stream_id]
                print(f"🗑️ 流 {stream_id} 的模型轮询器已移除")
    
    def get_model_for_stream(self, stream_id: int) -> Optional[YOLO]:
        """获取指定流当前应该使用的模型"""
        polling = self.pollings.get(stream_id)
        if polling:
            return polling.get_current_model()
        return None
    
    def get_polling_info(self, stream_id: int) -> Dict:
        """获取指定流的轮询信息"""
        polling = self.pollings.get(stream_id)
        if polling:
            return polling.get_current_model_info()
        return {}
    
    def reset_polling(self, stream_id: int):
        """重置指定流的轮询状态"""
        polling = self.pollings.get(stream_id)
        if polling:
            polling.reset()
    
    def update_polling_config(self, stream_id: int, new_config: dict) -> bool:
        """更新指定流的轮询配置"""
        try:
            polling = self.pollings.get(stream_id)
            if polling:
                polling.update_config(new_config)
                return True
            else:
                return self.create_polling(stream_id, new_config)
        except Exception as e:
            print(f"❌ 更新流 {stream_id} 的轮询配置失败: {e}")
            return False
    
    def cleanup(self):
        """清理所有轮询器"""
        with self.lock:
            self.pollings.clear()
            print("🧹 所有模型轮询器已清理")


# 全局模型轮询管理器实例
polling_manager = ModelPollingManager() 