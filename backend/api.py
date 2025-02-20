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
import traceback


api = Blueprint("api", __name__)


@api.route("/emoji", methods=["GET"])
def get_all_emojis():
    """获取所有表情包（按类别分组）"""
    emoji_data = scan_emoji_folder()
    return jsonify(emoji_data)


@api.route("/emoji/<category>", methods=["GET"])
def get_emojis_by_category(category):
    """获取指定类别的表情包"""
    emojis = get_emoji_by_category(category)
    if emojis is None:
        return jsonify({"message": "Category not found"}), 404
    return jsonify(emojis)


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
        sync_config()
        return jsonify({"message": "Emoji added successfully", "path": result_path}), 201
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
        return jsonify({"message": "Emoji deleted successfully"}), 200
    else:
        return jsonify({"message": "Emoji not found"}), 404


@api.route("/emotions", methods=["GET"])
def get_emotions():
    """获取标签描述映射"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        config = plugin_config.get("config")
        
        # 获取配置中的标签描述
        tag_descriptions = config.get("tag_descriptions", {}) if config else {}
        current_app.logger.debug(f"从配置获取的 tag_descriptions: {tag_descriptions}")
        
        return jsonify(tag_descriptions)
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

        # 删除文件夹
        category_path = os.path.join(current_app.config["MEMES_DIR"], category)
        if os.path.exists(category_path):
            shutil.rmtree(category_path)

        # 更新配置
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        config = plugin_config.get("config")
        if config:
            # 从 tag_descriptions 中移除
            tag_descriptions = config.get("tag_descriptions", {})
            if category in tag_descriptions:
                del tag_descriptions[category]
                config["tag_descriptions"] = tag_descriptions
                config.save_config()

        # 删除成功后同步配置
        sync_config()
        return jsonify({"message": "Category deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to delete category: {str(e)}"}), 500


@api.route("/sync/config", methods=["POST"])
def sync_config():
    """同步配置与文件夹结构的 API 端点"""
    try:
        sync_config_internal()
        return jsonify({"message": "配置同步成功"}), 200
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

        # 获取配置
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        config = plugin_config.get("config")
        if not config:
            return jsonify({"message": "Config not found"}), 404
            
        # 更新描述
        tag_descriptions = config.get("tag_descriptions", {})
        tag_descriptions[category] = description
        config["tag_descriptions"] = tag_descriptions
        
        # 保存配置
        config.save_config()
        
        return jsonify({"message": "Category description updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to update category description: {str(e)}"}), 500


def sync_config_internal():
    """同步配置与文件夹结构的内部函数"""
    # 获取配置对象
    plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
    config = plugin_config.get("config")
    if not config:
        raise ValueError("未找到配置对象")

    # 获取表情包文件夹下的所有目录
    memes_dir = current_app.config["MEMES_DIR"]
    categories = set(
        d for d in os.listdir(memes_dir) 
        if os.path.isdir(os.path.join(memes_dir, d))
    )
    
    # 更新标签描述
    tag_descriptions = config.get("tag_descriptions", {}).copy()
    
    # 删除不存在的类别
    for tag in list(tag_descriptions.keys()):
        if tag not in categories:
            del tag_descriptions[tag]
    
    # 添加新类别
    for category in categories:
        if category not in tag_descriptions:
            tag_descriptions[category] = f"表达{category}的场景"
    
    # 更新并保存配置
    config["tag_descriptions"] = tag_descriptions
    config.save_config()


