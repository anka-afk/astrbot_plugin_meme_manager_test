import os
import logging
from typing import Dict, Set, List, Tuple
from .config import MEMES_DIR, MEMES_DATA_PATH, DEFAULT_CATEGORY_DESCRIPTIONS
from .utils import ensure_dir_exists, save_json, load_json

logger = logging.getLogger(__name__)

class CategoryManager:
    def __init__(self):
        """初始化类别管理器"""
        ensure_dir_exists(MEMES_DIR)
        self._ensure_data_file()
        self.descriptions = self._load_descriptions()
        
    def _ensure_data_file(self) -> None:
        """确保 memes_data.json 文件存在，不存在则创建并写入默认数据"""
        if not os.path.exists(MEMES_DATA_PATH):
            save_json(DEFAULT_CATEGORY_DESCRIPTIONS, MEMES_DATA_PATH)
            logger.info(f"创建默认类别描述文件: {MEMES_DATA_PATH}")
            
    def _load_descriptions(self) -> Dict[str, str]:
        """加载类别描述配置"""
        return load_json(MEMES_DATA_PATH, DEFAULT_CATEGORY_DESCRIPTIONS)
    
    def get_local_categories(self) -> Set[str]:
        """获取本地文件夹中的类别"""
        try:
            return {d for d in os.listdir(MEMES_DIR) 
                   if os.path.isdir(os.path.join(MEMES_DIR, d))}
        except Exception as e:
            logger.error(f"获取本地类别失败: {e}")
            return set()
    
    def get_sync_status(self) -> Tuple[List[str], List[str]]:
        """获取同步状态
        返回: (missing_in_config, deleted_categories)
        """
        local_categories = self.get_local_categories()
        config_categories = set(self.descriptions.keys())
        
        return (
            list(local_categories - config_categories),  # 本地有但配置没有
            list(config_categories - local_categories)   # 配置有但本地没有
        )
    
    def sync_with_filesystem(self) -> bool:
        """同步文件系统和配置"""
        try:
            local_categories = self.get_local_categories()
            changed = False
            
            # 为新类别添加默认描述
            for category in local_categories:
                if category not in self.descriptions:
                    self.descriptions[category] = "请添加描述"
                    changed = True
            
            if changed:
                return save_json(self.descriptions, MEMES_DATA_PATH)
            return True
        except Exception as e:
            logger.error(f"同步文件系统失败: {e}")
            return False
    
    def update_description(self, category: str, description: str) -> bool:
        """更新类别描述"""
        try:
            self.descriptions[category] = description
            return save_json(self.descriptions, MEMES_DATA_PATH)
        except Exception as e:
            logger.error(f"更新类别描述失败: {e}")
            return False
    
    def rename_category(self, old_name: str, new_name: str) -> bool:
        """重命名类别"""
        try:
            if old_name not in self.descriptions:
                return False
                
            # 更新配置
            description = self.descriptions[old_name]
            del self.descriptions[old_name]
            self.descriptions[new_name] = description
            
            # 重命名文件夹
            old_path = os.path.join(MEMES_DIR, old_name)
            new_path = os.path.join(MEMES_DIR, new_name)
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
            
            return save_json(self.descriptions, MEMES_DATA_PATH)
        except Exception as e:
            logger.error(f"重命名类别失败: {e}")
            return False
    
    def delete_category(self, category: str) -> bool:
        """删除类别"""
        try:
            # 从配置中删除
            if category in self.descriptions:
                del self.descriptions[category]
                save_json(self.descriptions, MEMES_DATA_PATH)
            
            # 删除文件夹
            category_path = os.path.join(MEMES_DIR, category)
            if os.path.exists(category_path):
                import shutil
                shutil.rmtree(category_path)
            
            return True
        except Exception as e:
            logger.error(f"删除类别失败: {e}")
            return False
    
    def get_descriptions(self) -> Dict[str, str]:
        """获取所有类别描述"""
        return self.descriptions.copy() 