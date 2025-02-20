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
import traceback


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


# 获取标签描述映射
@api.route("/emotions", methods=["GET"])
def get_emotions():
    """获取标签描述映射"""
    try:
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        current_app.logger.debug(f"plugin_config: {plugin_config}")
        
        # 获取 emotion_map
        emotion_map = plugin_config.get("emotion_map", {})
        current_app.logger.debug(f"emotion_map: {emotion_map}")
        
        # 构建标签描述映射
        tag_descriptions = {}
        for chinese, english in emotion_map.items():
            # 去掉中文名称中的"未命名_"前缀
            clean_chinese = chinese.replace("未命名_", "")
            # 构建描述
            tag_descriptions[english] = f"表达{clean_chinese}的场景"
            
        current_app.logger.debug(f"生成的 tag_descriptions: {tag_descriptions}")
        return jsonify(tag_descriptions)
    except Exception as e:
        current_app.logger.error(f"获取标签描述失败: {str(e)}")
        current_app.logger.error(f"错误详情: {traceback.format_exc()}")
        return jsonify({"message": f"无法读取标签描述: {str(e)}"}), 500


def update_emotion_map(new_map):
    """更新配置中的 emotion_map"""
    try:
        # 获取 Flask 应用配置中的完整配置对象
        config = current_app.config.get("PLUGIN_CONFIG", {}).get("config")
        if not config:
            raise ValueError("未找到配置对象")
        
        # 更新 emotion_map
        config["emotion_map"] = new_map
        # 保存配置
        config.save_config()
        
        return True
    except Exception as e:
        current_app.logger.error(f"更新配置失败: {str(e)}")
        raise

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
        try:
            if os.path.exists(category_path):
                shutil.rmtree(category_path)
        except Exception as e:
            current_app.logger.error(f"删除文件夹失败: {str(e)}")
            return jsonify({"message": f"删除文件夹失败: {str(e)}"}), 500

        # 更新配置
        try:
            # 获取配置对象
            plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
            bot_config = plugin_config.get("bot_config")
            
            if not bot_config:
                raise ValueError("未找到配置对象")

            # 更新 emotion_map
            emotion_map = bot_config.get("emotion_map", {}).copy()
            # 找到并删除对应的中文-英文映射
            for chinese, english in list(emotion_map.items()):
                if english == category:
                    del emotion_map[chinese]
            
            # 更新配置
            bot_config["emotion_map"] = emotion_map
            bot_config.save_config()  # 保存配置
            
            # 同时更新 Flask 应用配置中的 emotion_map
            plugin_config["emotion_map"] = emotion_map

        except Exception as e:
            current_app.logger.error(f"更新配置失败: {str(e)}")
            return jsonify({
                "message": f"删除文件夹成功，但更新配置失败: {str(e)}",
                "detail": traceback.format_exc()
            }), 500

        return jsonify({"message": "Category deleted successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"删除分类失败: {str(e)}")
        return jsonify({
            "message": f"删除分类失败: {str(e)}",
            "detail": traceback.format_exc()
        }), 500

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

        # 更新配置
        bot_config = current_app.config.get("PLUGIN_CONFIG", {}).get("bot_config")
        if not bot_config:
            raise ValueError("未找到配置对象")

        emotion_map = bot_config.get("emotion_map", {}).copy()
        emotion_map[chinese] = english
        bot_config["emotion_map"] = emotion_map
        bot_config.save_config()

        # 同时更新 Flask 应用配置
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        plugin_config["emotion_map"] = emotion_map

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

        # 更新配置
        config = current_app.config.get("PLUGIN_CONFIG", {}).get("config")
        emotion_map = config.get("emotion_map", {}).copy()
        emotion_map[chinese] = english
        config["emotion_map"] = emotion_map
        config.save_config()

        return jsonify({"message": "Category mapping updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to update category mapping: {str(e)}"}), 500

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

def sync_emotion_map():
    """同步表情包文件夹结构和配置"""
    try:
        # 获取配置对象
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        bot_config = plugin_config.get("bot_config")
        if not bot_config:
            raise ValueError("未找到配置对象")

        # 获取当前的 emotion_map
        emotion_map = bot_config.get("emotion_map", {}).copy()
        
        # 获取表情包文件夹下的所有目录
        memes_dir = current_app.config["MEMES_DIR"]
        existing_categories = set(
            d for d in os.listdir(memes_dir) 
            if os.path.isdir(os.path.join(memes_dir, d))
        )
        
        # 获取当前配置中的所有英文分类
        configured_english = set(emotion_map.values())
        
        # 删除多余的映射（配置中有但文件夹中没有的）
        for chinese, english in list(emotion_map.items()):
            if english not in existing_categories:
                del emotion_map[chinese]
        
        # 添加缺失的映射（文件夹中有但配置中没有的）
        for category in existing_categories:
            if category not in configured_english:
                # 检查是否已经有这个英文名称的映射
                has_mapping = False
                for chinese, english in emotion_map.items():
                    if english == category:
                        has_mapping = True
                        break
                if not has_mapping:
                    emotion_map[category] = category  # 使用英文名作为临时中文名
        
        # 更新配置
        bot_config["emotion_map"] = emotion_map
        bot_config.save_config()
        
        # 同时更新 Flask 应用配置
        plugin_config["emotion_map"] = emotion_map
        
        return True
    except Exception as e:
        current_app.logger.error(f"同步配置失败: {str(e)}")
        raise

# 添加同步配置的 API 端点
@api.route("/sync/config", methods=["POST"])
def sync_config():
    """同步配置与文件夹结构"""
    try:
        sync_emotion_map()
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
        tag = data.get("tag")
        description = data.get("description")
        if not tag or not description:
            return jsonify({"message": "Tag and description are required"}), 400

        # 获取配置
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        emotion_map = plugin_config.get("emotion_map", {})
        
        # 找到对应的中文键
        chinese_key = None
        for key, value in emotion_map.items():
            if value == tag:
                chinese_key = key
                break
                
        if not chinese_key:
            return jsonify({"message": "Tag not found in emotion_map"}), 404
            
        # 更新描述
        emotion_map[chinese_key] = tag
        plugin_config["emotion_map"] = emotion_map
        
        return jsonify({"message": "Category description updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to update category description: {str(e)}"}), 500

def sync_tag_descriptions():
    """同步表情包文件夹结构和配置"""
    try:
        # 获取配置对象
        plugin_config = current_app.config.get("PLUGIN_CONFIG", {})
        bot_config = plugin_config.get("bot_config")
        if not bot_config:
            raise ValueError("未找到配置对象")

        # 获取当前的标签描述映射
        tag_descriptions = bot_config.get("tag_descriptions", {}).copy()
        
        # 获取表情包文件夹下的所有目录
        memes_dir = current_app.config["MEMES_DIR"]
        existing_categories = set(
            d for d in os.listdir(memes_dir) 
            if os.path.isdir(os.path.join(memes_dir, d))
        )
        
        # 删除多余的映射（配置中有但文件夹中没有的）
        for tag in list(tag_descriptions.keys()):
            if tag not in existing_categories:
                del tag_descriptions[tag]
        
        # 添加缺失的映射（文件夹中有但配置中没有的）
        for category in existing_categories:
            if category not in tag_descriptions:
                tag_descriptions[category] = f"未添加描述的{category}类别"
        
        # 更新配置
        bot_config["tag_descriptions"] = tag_descriptions
        bot_config.save_config()
        
        # 同时更新 Flask 应用配置
        plugin_config["tag_descriptions"] = tag_descriptions
        
        return True
    except Exception as e:
        current_app.logger.error(f"同步配置失败: {str(e)}")
        raise


