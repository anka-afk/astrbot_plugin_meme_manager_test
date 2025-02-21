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
        astr_config = plugin_config.get("astr_config")
        
        if not astr_config:
            raise ValueError("未找到配置对象")
        
        # 直接从 astr_config 对象获取描述
        category_descriptions = astr_config.get("category_descriptions", {})
        
        # 添加简短的调试日志
        angry_desc = category_descriptions.get("angry", "未找到")
        current_app.logger.debug(f"[DEBUG] /emotions API - angry 的描述: {angry_desc}")
        
        return jsonify(category_descriptions)
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
        astr_config = plugin_config.get("astr_config")
        if astr_config:
            # 从配置中移除
            descriptions = astr_config.get("category_descriptions", {})
            if category in descriptions:
                del descriptions[category]
                astr_config["category_descriptions"] = descriptions
                astr_config.save_config()

        return jsonify({"message": "Category deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to delete category: {str(e)}"}), 500


@api.route("/sync/status", methods=["GET"])
def get_sync_status():
    """获取同步状态"""
    try:
        # 获取表情包文件夹下的所有目录
        memes_dir = current_app.config["MEMES_DIR"]
        local_categories = set(
            d for d in os.listdir(memes_dir) 
            if os.path.isdir(os.path.join(memes_dir, d))
        )
        
        # 获取配置中的类别
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        astr_config = plugin_config.get("astr_config")
        if not astr_config:
            raise ValueError("未找到配置对象")
            
        # 这里修改为 category_descriptions
        config_categories = set(astr_config.get("category_descriptions", {}).keys())
        
        # 比较差异
        missing_in_config = list(local_categories - config_categories)  # 本地有但配置没有
        deleted_categories = list(config_categories - local_categories)  # 配置有但本地没有
        
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
        sync_config_internal()
        return jsonify({"message": "配置同步成功"}), 200
    except Exception as e:
        current_app.logger.error(f"同步配置失败: {str(e)}")
        current_app.logger.error(f"错误详情: {traceback.format_exc()}")
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
        astr_config = plugin_config.get("astr_config")
        if not astr_config:
            return jsonify({"message": "Config not found"}), 404
            
        # 更新描述
        descriptions = astr_config.get("category_descriptions", {})
        descriptions[category] = description
        astr_config["category_descriptions"] = descriptions
        
        # 保存配置
        astr_config.save_config()  # 确保调用 save_config
        
        return jsonify({"message": "Category description updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to update category description: {str(e)}"}), 500


@api.route("/category/restore", methods=["POST"])
def restore_category():
    """恢复已删除的类别"""
    try:
        data = request.get_json()
        category = data.get("category")
        if not category:
            return jsonify({"message": "Category is required"}), 400

        # 获取配置
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        astr_config = plugin_config.get("astr_config")
        if not astr_config:
            return jsonify({"message": "Config not found"}), 404

        # 创建类别目录
        category_path = os.path.join(current_app.config["MEMES_DIR"], category)
        os.makedirs(category_path, exist_ok=True)

        # 确保配置中有该类别
        descriptions = astr_config.get("category_descriptions", {})
        if category not in descriptions:
            descriptions[category] = "请添加描述"
            astr_config["category_descriptions"] = descriptions
            astr_config.save_config()

        return jsonify({"message": "Category restored successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to restore category: {str(e)}"}), 500


@api.route("/category/remove_from_config", methods=["POST"])
def remove_from_config():
    """从配置中删除类别"""
    try:
        data = request.get_json()
        category = data.get("category")
        if not category:
            return jsonify({"message": "Category is required"}), 400

        # 获取配置
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        astr_config = plugin_config.get("astr_config")
        if not astr_config:
            return jsonify({"message": "Config not found"}), 404

        # 从配置中删除类别
        category_descriptions = astr_config.get("category_descriptions", {})
        if category in category_descriptions:
            del category_descriptions[category]
            astr_config["category_descriptions"] = category_descriptions
            astr_config.save_config()

        return jsonify({"message": "Category removed from config successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to remove category from config: {str(e)}"}), 500


@api.route("/category/rename", methods=["POST"])
def rename_category():
    """重命名类别"""
    try:
        data = request.get_json()
        old_name = data.get("old_name")
        new_name = data.get("new_name")
        if not old_name or not new_name:
            return jsonify({"message": "Old and new category names are required"}), 400

        # 获取配置
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        astr_config = plugin_config.get("astr_config")
        if not astr_config:
            return jsonify({"message": "Config not found"}), 404

        # 检查旧文件夹是否存在
        old_path = os.path.join(current_app.config["MEMES_DIR"], old_name)
        if not os.path.exists(old_path):
            return jsonify({"message": "Category not found"}), 404

        # 检查新名称是否已存在
        new_path = os.path.join(current_app.config["MEMES_DIR"], new_name)
        if os.path.exists(new_path):
            return jsonify({"message": "New category name already exists"}), 400
        
        try:
            # 更新配置（在重命名文件夹之前）
            descriptions = astr_config.get("category_descriptions", {})
            if old_name in descriptions:
                description = descriptions[old_name]
                del descriptions[old_name]  # 删除旧的键
                descriptions[new_name] = description  # 添加新的键
                astr_config["category_descriptions"] = descriptions
                astr_config.save_config()  # 保存配置

            # 重命名文件夹
            os.rename(old_path, new_path)
            
            return jsonify({"message": "Category renamed successfully"}), 200
        except Exception as e:
            # 如果重命名过程中出错，尝试回滚配置
            if new_name in descriptions and old_name not in descriptions:
                descriptions[old_name] = descriptions[new_name]
                del descriptions[new_name]
                astr_config["category_descriptions"] = descriptions
                astr_config.save_config()
            raise e

    except Exception as e:
        return jsonify({"message": f"Failed to rename category: {str(e)}"}), 500


def sync_config_internal():
    """同步配置与文件夹结构的内部函数"""
    plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
    astr_config = plugin_config.get("astr_config")
    
    if not astr_config:
        raise ValueError("未找到配置对象")

    # 获取表情包文件夹下的所有目录
    memes_dir = current_app.config["MEMES_DIR"]
    local_categories = set(
        d for d in os.listdir(memes_dir) 
        if os.path.isdir(os.path.join(memes_dir, d))
    )
    
    # 获取当前配置
    descriptions = astr_config.get("category_descriptions", {})
    changed = False
    
    # 仅为新类别生成默认描述
    for category in local_categories:
        if category not in descriptions:
            descriptions[category] = f"请添加描述"
            changed = True
    
    # 只有在有变化时才保存配置
    if changed:
        astr_config["category_descriptions"] = descriptions
        astr_config.save_config()  # 确保调用 save_config


