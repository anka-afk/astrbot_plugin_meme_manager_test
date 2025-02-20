import aiohttp
import random
import string
import socket
from typing import Optional


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
