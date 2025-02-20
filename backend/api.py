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
from functools import partial
import json
from pathlib import Path


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


# 获取配置文件路径
def get_config_path():
    """获取配置文件路径"""
    try:
        # 从 Flask 配置中获取插件文件夹名称
        plugin_dir = current_app.config.get("PLUGIN_CONFIG", {}).get("plugin_dir")
        if not plugin_dir:
            raise ValueError("未找到插件文件夹名称")
            
        # 获取当前文件所在目录
        current_dir = Path(__file__).parent.parent.parent
        # 配置文件路径
        return current_dir.parent.parent / "config" / f"{plugin_dir}_config.json"
    except Exception as e:
        current_app.logger.error(f"获取配置文件路径失败: {str(e)}")
        raise

# 读取配置文件
def read_config():
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 保存配置文件
def save_config(config):
    config_path = get_config_path()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

@api.route("/category/delete", methods=["POST"])
def delete_category():
    """删除分类及其配置"""
    try:
        data = request.get_json()
        category = data.get("category")
        if not category:
            return jsonify({"message": "Category is required"}), 400

        # 删除文件夹
        category_path = os.path.join(current_app.config["MEMES_DIR"], category)
        if os.path.exists(category_path):
            shutil.rmtree(category_path)

        try:
            # 更新配置文件
            config = read_config()
            emotion_map = config.get("emotion_map", {})
            # 找到并删除对应的中文-英文映射
            for chinese, english in list(emotion_map.items()):
                if english == category:
                    del emotion_map[chinese]
            config["emotion_map"] = emotion_map
            save_config(config)
        except Exception as e:
            current_app.logger.error(f"更新配置文件失败: {str(e)}")
            return jsonify({"message": f"删除文件夹成功，但更新配置文件失败: {str(e)}"}), 500

        return jsonify({"message": "Category deleted successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"删除分类失败: {str(e)}")
        return jsonify({"message": f"Failed to delete category: {str(e)}"}), 500

@api.route("/category/add", methods=["POST"])
def add_category():
    """添加新分类及其配置"""
    try:
        data = request.get_json()
        chinese = data.get("chinese")
        english = data.get("english")
        if not chinese or not english:
            return jsonify({"message": "Chinese and English names are required"}), 400

        # 创建文件夹
        category_path = os.path.join(current_app.config["MEMES_DIR"], english)
        if not os.path.exists(category_path):
            os.makedirs(category_path)

        # 更新配置文件
        config = read_config()
        emotion_map = config.get("emotion_map", {})
        emotion_map[chinese] = english
        config["emotion_map"] = emotion_map
        save_config(config)

        return jsonify({"message": "Category added successfully"}), 201
    except Exception as e:
        return jsonify({"message": f"Failed to add category: {str(e)}"}), 500

@api.route("/category/update_mapping", methods=["POST"])
def update_category_mapping():
    """更新类别的中文映射"""
    try:
        data = request.get_json()
        english = data.get("english")
        chinese = data.get("chinese")
        if not english or not chinese:
            return jsonify({"message": "English and Chinese names are required"}), 400

        # 更新配置文件
        config = read_config()
        emotion_map = config.get("emotion_map", {})
        emotion_map[chinese] = english
        config["emotion_map"] = emotion_map
        save_config(config)

        return jsonify({"message": "Category mapping updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to update category mapping: {str(e)}"}), 500

# 添加新的同步相关 API 端点
@api.route("/sync/status", methods=["GET"])
def get_sync_status():
    """获取同步状态"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        print("Debug - PLUGIN_CONFIG:", plugin_config)  # 调试输出
        img_sync = plugin_config.get("img_sync")
        print("Debug - img_sync:", img_sync)  # 调试输出
        if not img_sync:
            return jsonify({
                "error": "配置错误",
                "detail": "图床服务未配置",
                "config": str(plugin_config)
            }), 400
            
        try:
            # 添加超时处理
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


