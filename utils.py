import os
import json
import logging
import aiohttp
import random
import string
import socket
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def ensure_dir_exists(path: str) -> None:
    """确保目录存在，不存在则创建"""
    if not os.path.exists(path):
        os.makedirs(path)

def save_json(data: Dict[str, Any], filepath: str) -> bool:
    """保存 JSON 数据到文件"""
    try:
        ensure_dir_exists(os.path.dirname(filepath))
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存 JSON 文件失败 {filepath}: {e}")
        return False

def load_json(filepath: str, default: Dict = None) -> Dict:
    """从文件加载 JSON 数据"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载 JSON 文件失败 {filepath}: {e}")
        return default if default is not None else {}

def generate_secret_key(length=8):
    """生成随机秘钥"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

async def get_public_ip():
    """异步获取公网IP"""
    ip_apis = [
        'http://api.ipify.org',
        'http://ip.42.pl/raw',
        'http://ifconfig.me/ip',
        'http://ipecho.net/plain'
    ]
    
    async with aiohttp.ClientSession() as session:
        for api in ip_apis:
            try:
                async with session.get(api, timeout=5) as response:
                    if response.status == 200:
                        return await response.text()
            except:
                continue
    
    return "127.0.0.1"  # 如果所有API都失败，返回本地地址
