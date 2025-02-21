from flask import Blueprint, jsonify, request, current_app
from .models import (
    scan_emoji_folder,
    get_emoji_by_category,
    add_emoji_to_category,
    delete_emoji_from_category,
)
from ..image_host.img_sync import ImageSync  # 导入 ImageSync 类
import os
import traceback
from ..config import MEMES_DIR


api = Blueprint("api", __name__)


@api.route("/emoji", methods=["GET"])
def get_all_emojis():
    """获取所有表情包（按类别分组）"""
    emoji_data = scan_emoji_folder()
    # 确保每个类别的表情包数据都是数组
    for category in emoji_data:
        if not isinstance(emoji_data[category], list):
            emoji_data[category] = []  # 如果不是列表，设置为空列表
    return jsonify(emoji_data)


@api.route("/emoji/<category>", methods=["GET"])
def get_emojis_by_category(category):
    """获取指定类别的表情包"""
    emojis = get_emoji_by_category(category)
    if emojis is None:
        return jsonify({"message": "Category not found"}), 404
    return jsonify(emojis if isinstance(emojis, list) else []), 200  # 确保返回数组


@api.route("/emoji/add", methods=["POST"])
def add_emoji():
    """添加表情包到指定类别"""
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

    try:
        result_path = add_emoji_to_category(category, image_file)
        
        # 添加成功后同步配置
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        category_manager = plugin_config.get("category_manager")
        if category_manager:
            category_manager.sync_with_filesystem()
            
        return jsonify({"message": "Emoji added successfully", "path": result_path, "category": category, "filename": image_file.filename}), 201
    except Exception as e:
        return jsonify({"message": f"添加表情包失败: {str(e)}"}), 500


@api.route("/emoji/delete", methods=["POST"])
def delete_emoji():
    """删除指定类别的表情包"""
    data = request.get_json()
    category = data.get("category")
    image_file = data.get("image_file")
    if not category or not image_file:
        return jsonify({"message": "Category and image file are required"}), 400

    if delete_emoji_from_category(category, image_file):
        return jsonify({"message": "Emoji deleted successfully", "category": category, "filename": image_file}), 200
    else:
        return jsonify({"message": "Emoji not found"}), 404


@api.route("/emotions", methods=["GET"])
def get_emotions():
    """获取标签描述映射"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        category_manager = plugin_config.get("category_manager")
        
        if not category_manager:
            raise ValueError("未找到类别管理器")
        
        return jsonify(category_manager.get_descriptions())
    except Exception as e:
        current_app.logger.error(f"获取标签描述失败: {str(e)}")
        current_app.logger.error(f"错误详情: {traceback.format_exc()}")
        return jsonify({"message": f"无法读取标签描述: {str(e)}"}), 500


@api.route("/category/delete", methods=["POST"])
def delete_category():
    """删除表情包类别"""
    try:
        data = request.get_json()
        category = data.get("category")
        if not category:
            return jsonify({"message": "Category is required"}), 400

        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        category_manager = plugin_config.get("category_manager")
        
        if not category_manager:
            return jsonify({"message": "Category manager not found"}), 404

        if category_manager.delete_category(category):
            return jsonify({"message": "Category deleted successfully"}), 200
        else:
            return jsonify({"message": "Failed to delete category"}), 500
    except Exception as e:
        return jsonify({"message": f"Failed to delete category: {str(e)}"}), 500


@api.route("/sync/status", methods=["GET"])
def get_sync_status():
    """获取同步状态"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        category_manager = plugin_config.get("category_manager")
        
        if not category_manager:
            raise ValueError("未找到类别管理器")
            
        missing_in_config, deleted_categories = category_manager.get_sync_status()
        
        return jsonify({
            "status": "ok",
            "differences": {
                "missing_in_config": missing_in_config,  # 需要添加到配置
                "deleted_categories": deleted_categories,  # 已删除的类别
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "detail": traceback.format_exc()
        }), 500


@api.route("/sync/config", methods=["POST"])
def sync_config():
    """同步配置与文件夹结构的 API 端点"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        category_manager = plugin_config.get("category_manager")
        
        if not category_manager:
            raise ValueError("未找到类别管理器")
            
        if category_manager.sync_with_filesystem():
            return jsonify({"message": "配置同步成功"}), 200
        else:
            return jsonify({"message": "配置同步失败"}), 500
    except Exception as e:
        return jsonify({
            "message": f"配置同步失败: {str(e)}",
            "detail": traceback.format_exc()
        }), 500


@api.route("/category/update_description", methods=["POST"])
def update_category_description():
    """更新类别的描述"""
    try:
        data = request.get_json()
        category = data.get("tag")
        description = data.get("description")
        if not category or not description:
            return jsonify({"message": "Category and description are required"}), 400

        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        category_manager = plugin_config.get("category_manager")
        
        if not category_manager:
            return jsonify({"message": "Category manager not found"}), 404
            
        if category_manager.update_description(category, description):
            return jsonify({"message": "Category description updated successfully"}), 200
        else:
            return jsonify({"message": "Failed to update category description"}), 500
    except Exception as e:
        return jsonify({"message": f"Failed to update category description: {str(e)}"}), 500


@api.route("/category/restore", methods=["POST"])
def restore_category():
    """恢复或创建新类别"""
    try:
        data = request.get_json()
        category = data.get("category")
        description = data.get("description", "请添加描述")
        
        if not category:
            return jsonify({"message": "Category is required"}), 400

        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        category_manager = plugin_config.get("category_manager")
        
        if not category_manager:
            return jsonify({"message": "Category manager not found"}), 404

        # 创建类别目录
        category_path = os.path.join(MEMES_DIR, category)
        os.makedirs(category_path, exist_ok=True)

        # 更新类别描述
        if category_manager.update_description(category, description):
            return jsonify({"message": "Category created successfully", "description": description}), 200
        else:
            return jsonify({"message": "Failed to create category"}), 500

    except Exception as e:
        return jsonify({"message": f"Failed to create category: {str(e)}"}), 500


@api.route("/category/rename", methods=["POST"])
def rename_category():
    """重命名类别"""
    try:
        data = request.get_json()
        old_name = data.get("old_name")
        new_name = data.get("new_name")
        if not old_name or not new_name:
            return jsonify({"message": "Old and new category names are required"}), 400

        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        category_manager = plugin_config.get("category_manager")
        
        if not category_manager:
            return jsonify({"message": "Category manager not found"}), 404

        if category_manager.rename_category(old_name, new_name):
            return jsonify({"message": "Category renamed successfully"}), 200
        else:
            return jsonify({"message": "Failed to rename category"}), 500
    except Exception as e:
        return jsonify({"message": f"Failed to rename category: {str(e)}"}), 500


@api.route("/sync/upload", methods=["POST"])
def sync_upload():
    """同步本地文件到云端"""
    try:
        # 调试信息
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        if "img_sync" not in plugin_config:
            return jsonify({"message": "配置中缺少 img_sync"}), 500
        
        sync = ImageSync(config=plugin_config["img_sync"], local_dir=MEMES_DIR)
        success = sync.upload_to_remote()
        if success:
            return jsonify({"message": "上传成功"}), 200
        else:
            return jsonify({"message": "上传失败"}), 500
    except Exception as e:
        return jsonify({"message": f"上传失败: {str(e)}"}), 500


@api.route("/sync/download", methods=["POST"])
def sync_download():
    """从云端下载文件到本地"""
    try:
        # 调试信息
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        if "img_sync" not in plugin_config:
            return jsonify({"message": "配置中缺少 img_sync"}), 500
        
        sync = ImageSync(config=plugin_config["img_sync"], local_dir=MEMES_DIR)
        success = sync.download_to_local()
        if success:
            return jsonify({"message": "下载成功"}), 200
        else:
            return jsonify({"message": "下载失败"}), 500
    except Exception as e:
        return jsonify({"message": f"下载失败: {str(e)}"}), 500


