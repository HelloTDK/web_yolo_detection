from flask import Blueprint, request, jsonify
import json
from models.database import db, RTSPStream, ModelPollingConfig
from services.rtsp_handler import rtsp_manager

rtsp_bp = Blueprint('rtsp', __name__, url_prefix='/api/rtsp')

@rtsp_bp.route('/streams', methods=['GET'])
def get_streams():
    """获取用户的RTSP流列表"""
    try:
        user_id = request.args.get('user_id', 1)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # 分页查询
        streams = RTSPStream.query.filter_by(user_id=user_id).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        stream_list = []
        for stream in streams.items:
            # 获取流状态
            status = rtsp_manager.get_stream_status(stream.id)
            
            stream_data = {
                'id': stream.id,
                'name': stream.name,
                'url': stream.url,
                'username': stream.username,
                'is_active': stream.is_active,
                'detection_enabled': stream.detection_enabled,
                'model_path': stream.model_path,
                'tracking_enabled': stream.tracking_enabled,
                'counting_enabled': stream.counting_enabled,
                'alert_enabled': stream.alert_enabled,
                'position_x': stream.position_x,
                'position_y': stream.position_y,
                'created_at': stream.created_at.isoformat(),
                'status': status,
                # 新增轮询相关字段
                'polling_enabled': stream.polling_enabled,
                'polling_config_id': stream.polling_config_id,
                'polling_type': stream.polling_type,
                'polling_interval': stream.polling_interval,
                'polling_models': json.loads(stream.polling_models) if stream.polling_models else [],
                'polling_order': json.loads(stream.polling_order) if stream.polling_order else []
            }
            
            # 如果有关联的轮询配置，添加配置信息
            if stream.polling_config:
                stream_data['polling_config'] = {
                    'id': stream.polling_config.id,
                    'name': stream.polling_config.name,
                    'is_active': stream.polling_config.is_active
                }
            
            stream_list.append(stream_data)
        
        return jsonify({
            'success': True,
            'streams': stream_list,
            'pagination': {
                'page': streams.page,
                'pages': streams.pages,
                'per_page': streams.per_page,
                'total': streams.total,
                'has_next': streams.has_next,
                'has_prev': streams.has_prev
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取流列表失败: {str(e)}'}), 500

@rtsp_bp.route('/streams', methods=['POST'])
def create_stream():
    """创建RTSP流"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 1)
        
        # 验证必要字段
        required_fields = ['name', 'url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'缺少必要字段: {field}'}), 400
        
        # 检查同名流是否存在
        existing = RTSPStream.query.filter_by(user_id=user_id, name=data['name']).first()
        if existing:
            return jsonify({'success': False, 'message': '同名流已存在'}), 400
        
        # 自动分配位置（四宫格）
        existing_streams = RTSPStream.query.filter_by(user_id=user_id, is_active=True).all()
        position_x, position_y = _find_available_position(existing_streams)
        
        # 处理轮询配置
        polling_enabled = data.get('polling_enabled', False)
        polling_config_id = data.get('polling_config_id')
        
        # 如果启用轮询且指定了配置ID，验证配置是否存在
        if polling_enabled and polling_config_id:
            polling_config = ModelPollingConfig.query.filter_by(
                id=polling_config_id, user_id=user_id, is_active=True
            ).first()
            if not polling_config:
                return jsonify({'success': False, 'message': '指定的轮询配置不存在或不可用'}), 400
            
            # 从配置中获取轮询参数
            polling_type = polling_config.polling_type
            polling_interval = polling_config.interval_value
            # 确保数据类型一致，都转换为JSON字符串
            polling_models = json.dumps(polling_config.model_paths) if isinstance(polling_config.model_paths, list) else polling_config.model_paths
            polling_order = json.dumps(polling_config.model_order) if isinstance(polling_config.model_order, list) else polling_config.model_order
        else:
            # 使用自定义轮询参数
            polling_config_id = None
            polling_type = data.get('polling_type', 'frame')
            polling_interval = data.get('polling_interval', 10)
            polling_models = json.dumps(data.get('polling_models', []))
            polling_order = json.dumps(data.get('polling_order', []))
        
        # 创建流记录
        stream = RTSPStream(
            user_id=user_id,
            name=data['name'],
            url=data['url'],
            username=data.get('username', ''),
            password=data.get('password', ''),
            is_active=data.get('is_active', True),
            detection_enabled=data.get('detection_enabled', True),
            model_path=data.get('model_path', 'yolov8n.pt'),
            tracking_enabled=data.get('tracking_enabled', False),
            counting_enabled=data.get('counting_enabled', False),
            alert_enabled=data.get('alert_enabled', False),
            position_x=position_x,
            position_y=position_y,
            # 轮询相关字段
            polling_enabled=polling_enabled,
            polling_config_id=polling_config_id,
            polling_type=polling_type,
            polling_interval=polling_interval,
            polling_models=polling_models,
            polling_order=polling_order
        )
        
        db.session.add(stream)
        db.session.commit()
        
        # 添加到RTSP管理器
        stream_config = {
            'id': stream.id,
            'name': stream.name,
            'url': stream.url,
            'username': stream.username,
            'password': stream.password,
            'detection_enabled': stream.detection_enabled,
            'model_path': stream.model_path,
            'tracking_enabled': stream.tracking_enabled,
            'counting_enabled': stream.counting_enabled,
            'alert_enabled': stream.alert_enabled,
            # 轮询配置
            'polling_enabled': stream.polling_enabled,
            'polling_type': stream.polling_type,
            'polling_interval': stream.polling_interval,
            'polling_models': stream.polling_models,
            'polling_order': stream.polling_order
        }
        
        if rtsp_manager.add_stream(stream_config):
            return jsonify({
                'success': True,
                'message': 'RTSP流创建成功',
                'stream': {
                    'id': stream.id,
                    'name': stream.name,
                    'position_x': stream.position_x,
                    'position_y': stream.position_y,
                    'polling_enabled': stream.polling_enabled
                }
            })
        else:
            # 如果添加失败，删除数据库记录
            db.session.delete(stream)
            db.session.commit()
            return jsonify({'success': False, 'message': 'RTSP流添加失败'}), 500
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'创建流失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>', methods=['PUT'])
def update_stream(stream_id):
    """更新RTSP流配置"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 1)
        
        stream = RTSPStream.query.filter_by(id=stream_id, user_id=user_id).first()
        if not stream:
            return jsonify({'success': False, 'message': '流不存在'}), 404
        
        # 更新字段
        if 'name' in data:
            # 检查同名流
            existing = RTSPStream.query.filter_by(user_id=user_id, name=data['name']).first()
            if existing and existing.id != stream_id:
                return jsonify({'success': False, 'message': '同名流已存在'}), 400
            stream.name = data['name']
        
        update_fields = ['url', 'username', 'password', 'is_active', 'detection_enabled', 
                        'model_path', 'tracking_enabled', 'counting_enabled', 'alert_enabled']
        
        for field in update_fields:
            if field in data:
                setattr(stream, field, data[field])
        
        # 处理轮询配置更新
        if 'polling_enabled' in data:
            stream.polling_enabled = data['polling_enabled']
            
            if stream.polling_enabled:
                # 如果启用轮询，更新相关配置
                if 'polling_config_id' in data and data['polling_config_id']:
                    # 使用预设配置
                    polling_config = ModelPollingConfig.query.filter_by(
                        id=data['polling_config_id'], user_id=user_id, is_active=True
                    ).first()
                    if not polling_config:
                        return jsonify({'success': False, 'message': '指定的轮询配置不存在或不可用'}), 400
                    
                    stream.polling_config_id = polling_config.id
                    stream.polling_type = polling_config.polling_type
                    stream.polling_interval = polling_config.interval_value
                    # 确保数据类型一致，都转换为JSON字符串
                    stream.polling_models = json.dumps(polling_config.model_paths) if isinstance(polling_config.model_paths, list) else polling_config.model_paths
                    stream.polling_order = json.dumps(polling_config.model_order) if isinstance(polling_config.model_order, list) else polling_config.model_order
                else:
                    # 使用自定义配置
                    stream.polling_config_id = None
                    if 'polling_type' in data:
                        stream.polling_type = data['polling_type']
                    if 'polling_interval' in data:
                        stream.polling_interval = data['polling_interval']
                    if 'polling_models' in data:
                        stream.polling_models = json.dumps(data['polling_models'])
                    if 'polling_order' in data:
                        stream.polling_order = json.dumps(data['polling_order'])
            else:
                # 禁用轮询
                stream.polling_config_id = None
        
        db.session.commit()
        
        # 更新RTSP管理器配置
        stream_config = {
            'id': stream.id,
            'name': stream.name,
            'url': stream.url,
            'username': stream.username,
            'password': stream.password,
            'detection_enabled': stream.detection_enabled,
            'model_path': stream.model_path,
            'tracking_enabled': stream.tracking_enabled,
            'counting_enabled': stream.counting_enabled,
            'alert_enabled': stream.alert_enabled,
            'polling_enabled': stream.polling_enabled,
            'polling_type': stream.polling_type,
            'polling_interval': stream.polling_interval,
            'polling_models': stream.polling_models,
            'polling_order': stream.polling_order
        }
        
        rtsp_manager.update_stream_config(stream_id, stream_config)
        
        return jsonify({
            'success': True,
            'message': 'RTSP流更新成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新流失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>', methods=['DELETE'])
def delete_stream(stream_id):
    """删除RTSP流"""
    try:
        user_id = request.args.get('user_id', 1)
        print(f"🗑️ 请求删除流: ID={stream_id}, User={user_id}")
        
        stream = RTSPStream.query.filter_by(id=stream_id, user_id=user_id).first()
        if not stream:
            print(f"❌ 流不存在: ID={stream_id}, User={user_id}")
            return jsonify({'success': False, 'message': '流不存在'}), 404
        
        stream_name = stream.name
        print(f"🔍 找到流: {stream_name} (ID={stream_id})")
        
        # 停止并移除流
        print(f"⏹️ 停止并移除流管理器中的流...")
        rtsp_manager.remove_stream(stream_id)
        
        # 删除数据库记录
        print(f"🗄️ 删除数据库记录...")
        db.session.delete(stream)
        db.session.commit()
        
        print(f"✅ 流 '{stream_name}' 删除成功")
        return jsonify({
            'success': True,
            'message': f'RTSP流 "{stream_name}" 删除成功'
        })
        
    except Exception as e:
        print(f"❌ 删除流异常: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除流失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>/start', methods=['POST'])
def start_stream(stream_id):
    """启动RTSP流"""
    try:
        user_id = request.get_json().get('user_id', 1)
        
        stream = RTSPStream.query.filter_by(id=stream_id, user_id=user_id).first()
        if not stream:
            return jsonify({'success': False, 'message': '流不存在'}), 404
        
        if rtsp_manager.start_stream(stream_id):
            return jsonify({
                'success': True,
                'message': f'RTSP流 {stream.name} 启动成功'
            })
        else:
            return jsonify({'success': False, 'message': '启动流失败'}), 500
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动流失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>/stop', methods=['POST'])
def stop_stream(stream_id):
    """停止RTSP流"""
    try:
        user_id = request.get_json().get('user_id', 1)
        
        stream = RTSPStream.query.filter_by(id=stream_id, user_id=user_id).first()
        if not stream:
            return jsonify({'success': False, 'message': '流不存在'}), 404
        
        rtsp_manager.stop_stream(stream_id)
        
        return jsonify({
            'success': True,
            'message': f'RTSP流 {stream.name} 已停止'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止流失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/start-all', methods=['POST'])
def start_all_streams():
    """启动所有活跃的RTSP流"""
    try:
        user_id = request.get_json().get('user_id', 1)
        
        streams = RTSPStream.query.filter_by(user_id=user_id, is_active=True).all()
        
        results = rtsp_manager.start_all_streams()
        
        success_count = sum(1 for success in results.values() if success)
        
        return jsonify({
            'success': True,
            'message': f'启动了 {success_count}/{len(streams)} 个流',
            'results': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动所有流失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/stop-all', methods=['POST'])
def stop_all_streams():
    """停止所有RTSP流"""
    try:
        rtsp_manager.stop_all_streams()
        
        return jsonify({
            'success': True,
            'message': '所有RTSP流已停止'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止所有流失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>/frame', methods=['GET'])
def get_stream_frame(stream_id):
    """获取RTSP流的最新帧"""
    try:
        print(f"🌐 API请求获取流 {stream_id} 的帧")
        frame_base64 = rtsp_manager.get_stream_frame(stream_id)
        
        if frame_base64:
            print(f"✅ API成功返回流 {stream_id} 的帧")
            return jsonify({
                'success': True,
                'frame': frame_base64
            })
        else:
            print(f"❌ API无法获取流 {stream_id} 的帧")
            return jsonify({'success': False, 'message': '获取帧失败'}), 404
        
    except Exception as e:
        print(f"❌ API获取流 {stream_id} 帧时异常: {e}")
        return jsonify({'success': False, 'message': f'获取帧失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>/detections', methods=['GET'])
def get_stream_detections(stream_id):
    """获取RTSP流的检测结果"""
    try:
        detections = rtsp_manager.get_stream_detections(stream_id)
        
        if detections is not None:
            return jsonify({
                'success': True,
                'detections': detections
            })
        else:
            return jsonify({'success': False, 'message': '获取检测结果失败'}), 404
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取检测结果失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>/reset-tracker', methods=['POST'])
def reset_stream_tracker(stream_id):
    """重置RTSP流的跟踪器"""
    try:
        if rtsp_manager.reset_stream_tracker(stream_id):
            return jsonify({
                'success': True,
                'message': '跟踪器重置成功'
            })
        else:
            return jsonify({'success': False, 'message': '重置跟踪器失败'}), 404
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置跟踪器失败: {str(e)}'}), 500

# 新增轮询相关API
@rtsp_bp.route('/streams/<int:stream_id>/polling/status', methods=['GET'])
def get_stream_polling_status(stream_id):
    """获取RTSP流的轮询状态"""
    try:
        from services.model_polling import polling_manager
        
        user_id = request.args.get('user_id', 1, type=int)
        
        stream = RTSPStream.query.filter_by(id=stream_id, user_id=user_id).first()
        if not stream:
            return jsonify({'success': False, 'message': '流不存在'}), 404
        
        if not stream.polling_enabled:
            return jsonify({
                'success': True,
                'polling_enabled': False,
                'message': '该流未启用模型轮询'
            })
        
        # 获取轮询状态
        polling_info = polling_manager.get_polling_info(stream_id)
        
        return jsonify({
            'success': True,
            'polling_enabled': True,
            'polling_info': polling_info,
            'stream_config': {
                'polling_type': stream.polling_type,
                'polling_interval': stream.polling_interval,
                'models': json.loads(stream.polling_models) if stream.polling_models else [],
                'order': json.loads(stream.polling_order) if stream.polling_order else []
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取轮询状态失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>/polling/reset', methods=['POST'])
def reset_stream_polling(stream_id):
    """重置RTSP流的轮询状态"""
    try:
        from services.model_polling import polling_manager
        
        user_id = request.get_json().get('user_id', 1)
        
        stream = RTSPStream.query.filter_by(id=stream_id, user_id=user_id).first()
        if not stream:
            return jsonify({'success': False, 'message': '流不存在'}), 404
        
        if not stream.polling_enabled:
            return jsonify({'success': False, 'message': '该流未启用模型轮询'}), 400
        
        polling_manager.reset_polling(stream_id)
        
        return jsonify({
            'success': True,
            'message': f'流 {stream.name} 的轮询状态已重置'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置轮询状态失败: {str(e)}'}), 500

@rtsp_bp.route('/streams/<int:stream_id>/polling/update', methods=['POST'])
def update_stream_polling_config(stream_id):
    """更新RTSP流的轮询配置"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 1)
        
        stream = RTSPStream.query.filter_by(id=stream_id, user_id=user_id).first()
        if not stream:
            return jsonify({'success': False, 'message': '流不存在'}), 404
        
        # 更新数据库中的轮询配置
        if 'polling_enabled' in data:
            stream.polling_enabled = data['polling_enabled']
        
        if stream.polling_enabled:
            if 'polling_type' in data:
                stream.polling_type = data['polling_type']
            if 'polling_interval' in data:
                stream.polling_interval = data['polling_interval']
            if 'polling_models' in data:
                stream.polling_models = json.dumps(data['polling_models'])
            if 'polling_order' in data:
                stream.polling_order = json.dumps(data['polling_order'])
        
        db.session.commit()
        
        # 更新RTSP处理器的轮询配置
        if stream_id in rtsp_manager.handlers:
            handler = rtsp_manager.handlers[stream_id]
            polling_config = {
                'enabled': stream.polling_enabled,
                'type': stream.polling_type,
                'interval': stream.polling_interval,
                'models': json.loads(stream.polling_models) if stream.polling_models else [],
                'order': json.loads(stream.polling_order) if stream.polling_order else []
            }
            handler.update_polling_config(polling_config)
        
        return jsonify({
            'success': True,
            'message': f'流 {stream.name} 的轮询配置已更新'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新轮询配置失败: {str(e)}'}), 500

@rtsp_bp.route('/status', methods=['GET'])
def get_all_status():
    """获取所有RTSP流的状态"""
    try:
        user_id = request.args.get('user_id', 1)
        
        # 获取用户的所有流
        streams = RTSPStream.query.filter_by(user_id=user_id).all()
        
        status_data = {}
        for stream in streams:
            status = rtsp_manager.get_stream_status(stream.id)
            status_data[stream.id] = {
                'name': stream.name,
                'position_x': stream.position_x,
                'position_y': stream.position_y,
                'is_active': stream.is_active,
                'status': status
            }
        
        return jsonify({
            'success': True,
            'streams_status': status_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取状态失败: {str(e)}'}), 500

@rtsp_bp.route('/debug', methods=['GET'])
def get_debug_info():
    """获取调试信息"""
    try:
        # 获取所有流的详细信息
        streams = RTSPStream.query.all()
        handlers = list(rtsp_manager.handlers.keys())
        
        debug_info = {
            'database_streams': [{'id': s.id, 'name': s.name, 'url': s.url} for s in streams],
            'active_handlers': handlers,
            'handler_details': {}
        }
        
        # 获取每个处理器的详细信息
        for stream_id in handlers:
            handler = rtsp_manager.handlers[stream_id]
            debug_info['handler_details'][stream_id] = {
                'is_running': handler.is_running,
                'has_frame': handler.latest_frame is not None,
                'frame_count': handler.frame_count,
                'fps': handler.fps,
                'detection_count': len(handler.latest_detections)
            }
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取调试信息失败: {str(e)}'}), 500

def _find_available_position(existing_streams):
    """查找可用的四宫格位置"""
    # 四宫格位置 (x, y): (0,0), (1,0), (0,1), (1,1)
    positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
    used_positions = {(stream.position_x, stream.position_y) for stream in existing_streams}
    
    for pos in positions:
        if pos not in used_positions:
            return pos
    
    # 如果四宫格都满了，返回 (0, 0) 并提示用户
    return (0, 0) 