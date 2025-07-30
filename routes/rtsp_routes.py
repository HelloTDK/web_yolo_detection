from flask import Blueprint, request, jsonify
import json
from models.database import db, RTSPStream
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
                'status': status
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
            position_y=position_y
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
            'alert_enabled': stream.alert_enabled
        }
        
        if rtsp_manager.add_stream(stream_config):
            return jsonify({
                'success': True,
                'message': 'RTSP流创建成功',
                'stream': {
                    'id': stream.id,
                    'name': stream.name,
                    'position_x': stream.position_x,
                    'position_y': stream.position_y
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
            'alert_enabled': stream.alert_enabled
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