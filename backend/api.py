from flask import Blueprint, jsonify, request, current_app
from .models import (
    scan_emoji_folder,
    get_emoji_by_category,
    add_emoji_to_category,
    delete_emoji_from_category,
    update_emoji_in_category,
    get_base_dir,
)
import os
import shutil
import asyncio


api = Blueprint("api", __name__)


# 获取所有表情包（按类别分组）
@api.route("/emoji", methods=["GET"])
def get_all_emojis():
    emoji_data = scan_emoji_folder()
    return jsonify(emoji_data)


# 获取指定类别的表情包
@api.route("/emoji/<category>", methods=["GET"])
def get_emojis_by_category(category):
    emojis = get_emoji_by_category(category)
    if emojis is None:
        return jsonify({"message": "Category not found"}), 404
    return jsonify(emojis)


# 添加表情包到指定类别
@api.route("/emoji/add", methods=["POST"])
def add_emoji():
    # 支持 JSON 和 multipart/form-data 两种请求方式
    category = None
    image_file = None
    if "image_file" in request.files:
        image_file = request.files["image_file"]
        category = request.form.get("category")
    else:
        data = request.get_json()
        if data:
            category = data.get("category")
            image_file = data.get("image_file")
    if not category or not image_file:
        return jsonify({"message": "Category and image file are required"}), 400

    # 添加表情包
    try:
        result_path = add_emoji_to_category(category, image_file)
    except Exception as e:
        return jsonify({"message": f"添加表情包失败: {str(e)}"}), 500

    return jsonify({"message": "Emoji added successfully", "path": result_path}), 201


# 删除指定类别的表情包
@api.route("/emoji/delete", methods=["POST"])
def delete_emoji():
    data = request.get_json()
    category = data.get("category")
    image_file = data.get("image_file")
    if not category or not image_file:
        return jsonify({"message": "Category and image file are required"}), 400

    if delete_emoji_from_category(category, image_file):
        return jsonify({"message": "Emoji deleted successfully"}), 200
    else:
        return jsonify({"message": "Emoji not found"}), 404


# 更新指定类别下的表情包
@api.route("/emoji/update", methods=["POST"])
def update_emoji():
    data = request.get_json()
    category = data.get("category")
    old_image_file = data.get("old_image_file")
    new_image_file = data.get("new_image_file")
    if not category or not old_image_file or not new_image_file:
        return (
            jsonify({"message": "Category, old and new image files are required"}),
            400,
        )

    if update_emoji_in_category(category, old_image_file, new_image_file):
        return jsonify({"message": "Emoji updated successfully"}), 200
    else:
        return jsonify({"message": "Emoji not found or update failed"}), 404


# 获取表情包映射的中文-英文名
@api.route("/emotions", methods=["GET"])
def get_emotions():
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        emotion_map = plugin_config.get("emotion_map", {})
        return jsonify(emotion_map)
    except Exception as e:
        return jsonify({"message": f"无法读取 emotion_map: {str(e)}"}), 500


# 添加分类：输入中文键和英文值，同时更新配置中 PLUGIN_CONFIG 的 emotion_map 并创建对应目录
@api.route("/category/add", methods=["POST"])
def add_category():
    data = request.get_json()
    chinese = data.get("chinese")
    english = data.get("english")
    if not chinese or not english:
        return jsonify({"message": "中文名称和英文名称均为必填项"}), 400

    # 从 Flask 应用配置中获取 PLUGIN_CONFIG 下的 emotion_map
    plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
    emotion_map = plugin_config.get("emotion_map", {})

    # 添加或更新新的分类映射
    emotion_map[chinese] = english
    plugin_config["emotion_map"] = emotion_map
    current_app.config["PLUGIN_CONFIG"] = plugin_config

    # 创建对应的表情包目录（以英文名称作为文件夹名）
    from .models import get_base_dir

    category_path = os.path.join(get_base_dir(), english)
    if not os.path.exists(category_path):
        os.makedirs(category_path)

    return jsonify({"message": "Category added successfully"}), 201


# 删除分类：删除配置中 emotion_map 的映射以及对应的表情包目录
@api.route("/category/delete", methods=["POST"])
def delete_category():
    data = request.get_json()
    category = data.get("category")  # 此处 category 为英文名称
    if not category:
        return jsonify({"message": "Category is required"}), 400

    # 从 Flask 应用配置中获取 PLUGIN_CONFIG 下的 emotion_map
    plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
    emotion_map = plugin_config.get("emotion_map", {})

    # 移除映射中对应的条目（如果存在）
    removed = False
    for key in list(emotion_map.keys()):
        if emotion_map[key] == category:
            del emotion_map[key]
            removed = True

    if not removed:
        return jsonify({"message": "Category not found in configuration"}), 404

    plugin_config["emotion_map"] = emotion_map
    current_app.config["PLUGIN_CONFIG"] = plugin_config

    # 删除对应的表情包目录（以英文名称作为文件夹名）
    from .models import get_base_dir

    category_path = os.path.join(get_base_dir(), category)
    if os.path.exists(category_path):
        try:
            shutil.rmtree(category_path)
        except Exception as e:
            return jsonify({"message": f"删除类别目录失败: {str(e)}"}), 500

    return jsonify({"message": "Category deleted successfully"}), 200


# 添加新的同步相关 API 端点
@api.route("/sync/status", methods=["GET"])
def get_sync_status():
    """获取同步状态"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        img_sync = plugin_config.get("img_sync")
        if not img_sync:
            return jsonify({
                "error": "配置错误",
                "detail": "图床服务未配置",
                "config": str(plugin_config)  # 输出配置信息以便调试
            }), 400
            
        try:
            status = img_sync.check_status()
            return jsonify(status)
        except Exception as e:
            import traceback
            return jsonify({
                "error": "同步状态检查失败",
                "detail": str(e),
                "traceback": traceback.format_exc()
            }), 500
            
    except Exception as e:
        import traceback
        return jsonify({
            "error": "服务器错误",
            "detail": str(e),
            "traceback": traceback.format_exc()
        }), 500

@api.route("/sync/upload", methods=["POST"])
def sync_to_remote():
    """同步到云端"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        img_sync = plugin_config.get("img_sync")
        if not img_sync:
            return jsonify({"message": "图床服务未配置"}), 400
            
        # 启动同步进程，但不等待完成
        img_sync.sync_process = img_sync._start_sync_process('upload')
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@api.route("/sync/download", methods=["POST"]) 
def sync_from_remote():
    """从云端同步"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        img_sync = plugin_config.get("img_sync")
        if not img_sync:
            return jsonify({"message": "图床服务未配置"}), 400
            
        # 启动同步进程，但不等待完成
        img_sync.sync_process = img_sync._start_sync_process('download')
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# 添加一个检查同步进程状态的端点
@api.route("/sync/check_process", methods=["GET"])
def check_sync_process():
    """检查同步进程状态"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        img_sync = plugin_config.get("img_sync")
        if not img_sync or not img_sync.sync_process:
            return jsonify({"completed": True, "success": True})
            
        if not img_sync.sync_process.is_alive():
            success = img_sync.sync_process.exitcode == 0
            img_sync.sync_process = None
            return jsonify({"completed": True, "success": success})
            
        return jsonify({"completed": False})
    except Exception as e:
        return jsonify({"message": str(e)}), 500


