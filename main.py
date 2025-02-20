import re
import os
import io
import random
import logging
import json
import time
import aiohttp
import ssl
import imghdr
from PIL import Image
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.provider import LLMResponse
from astrbot.api.message_components import *
from astrbot.api.event.filter import EventMessageType
from astrbot.api.event import ResultContentType
from astrbot.core.message.components import Plain
from astrbot.api.all import *
from astrbot.core.message.message_event_result import MessageChain
from .webui import start_server, shutdown_server
from .utils import get_public_ip
from .image_host.img_sync import ImageSync


@register(
    "meme_manager_test", "anka", "anka - 表情包管理器 - 支持表情包发送及表情包上传", "2.0"
)
class MemeSender(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)

        # 加载配置
        self.config = config or {}
        self.emotion_map = self.config.get(
            "emotion_map",
            {
                "生气": "angry",
                "开心": "happy",
                "悲伤": "sad",
                "惊讶": "surprised",
                "疑惑": "confused",
                "色色": "color",
                "色": "color",
                "死机": "cpu",
                "笨蛋": "fool",
                "给钱": "givemoney",
                "喜欢": "like",
                "看": "see",
                "害羞": "shy",
                "下班": "work",
                "剪刀": "scissors",
                "不回我": "reply",
                "喵": "meow",
                "八嘎": "baka",
                "早": "morning",
                "睡觉": "sleep",
                "唉": "sigh",
            },
        )
        self.image_host = self.config.get("image_host", "stardots")
        self.image_host_key = self.config.get("image_host_key", "")
        self.image_host_secret = self.config.get("image_host_secret", "")

        self.found_emotions = []  # 存储找到的表情
        self.upload_states = (
            {}
        )  # 存储上传状态：{user_session: {"category": str, "expire_time": float}}
        self.pending_images = {}  # 存储待发送的图片

        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.meme_path = os.path.join(
            current_dir, self.config.get("memes_path", "memes")
        )

        # 设置日志
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        # 检查表情包目录
        self._check_meme_directories()
        # 用于保存服务器进程对象
        self.server_process = None

        # 初始化图床同步客户端
        self.img_sync = None
        if self.config.get("image_host") == "stardots":
            stardots_config = self.config.get("image_host_config", {}).get("stardots", {})
            if stardots_config.get("key") and stardots_config.get("secret"):
                self.img_sync = ImageSync(
                    config={
                        "key": stardots_config["key"],
                        "secret": stardots_config["secret"],
                        "space": stardots_config.get("space", "memes")
                    },
                    local_dir=self.meme_path
                )

    @filter.command("启动表情包管理服务器")
    async def start_server_command(self, event: AstrMessageEvent):
        """启动表情包管理服务器的指令，返回访问地址和当前秘钥"""
        yield event.plain_result("表情包管理服务器启动中，请稍候……")

        try:
            # 获取插件文件夹名称
            plugin_dir = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
            
            # 获取完整配置对象
            config = self.context.get_config()
            print("Debug - 获取到的配置对象:", config)  # 调试输出
            
            # 创建配置字典，包含 img_sync 实例和配置对象
            webui_config = {
                "emotion_map": self.emotion_map,
                "memes_path": self.meme_path,
                "webui_port": self.config.get("webui_port", 5000),
                "img_sync": self.img_sync,  # 传递 img_sync 实例
                "plugin_dir": plugin_dir,  # 传递插件文件夹名称
                "config": config,  # 传递完整配置对象
            }
            print("Debug - 创建的 webui_config:", webui_config)  # 调试输出

            # 启动服务器
            secret_key, process = start_server(webui_config)
            self.server_process = process

            # 获取公网 IP
            public_ip = await get_public_ip()

            yield event.plain_result(
                f"表情包管理服务器已启动！\n"
                f"访问地址：http://{public_ip}:5000\n"
                f"当前秘钥：{secret_key}"
            )
        except Exception as e:
            self.logger.error(f"启动表情包管理服务器失败: {str(e)}")
            yield event.plain_result(f"启动表情包管理服务器失败: {str(e)}")

    @filter.command("关闭表情包管理服务器")
    async def stop_server(self, event: AstrMessageEvent):
        """
        关闭表情包管理服务器的指令
        """
        if not self.server_process:
            yield event.plain_result("表情包管理服务器未启动或已关闭。")
            return

        yield event.plain_result("正在关闭表情包管理服务器……")
        shutdown_server(self.server_process)
        self.server_process = None
        yield event.plain_result("表情包管理服务器已关闭！")

    @filter.command("查看表情包")
    async def list_emotions(self, event: AstrMessageEvent):
        """查看所有可用表情包类别"""
        categories = "\n".join([f"- {emotion}" for emotion in self.emotion_map.keys()])
        yield event.plain_result(f"当前支持的表情包类别：\n{categories}")

    @filter.command("上传表情包")
    async def upload_meme(self, event: AstrMessageEvent, category: str = None):
        """上传表情包到指定类别"""
        if not category:
            yield event.plain_result(
                "请指定要上传的表情包类别，格式：/上传表情包 [类别名称]"
            )
            return

        if category not in self.emotion_map:
            yield event.plain_result(
                f"无效的表情包类别：{category}\n使用/查看表情包查看可用类别"
            )
            return

        user_key = f"{event.session_id}_{event.get_sender_id()}"
        self.upload_states[user_key] = {
            "category": category,
            "expire_time": time.time() + 30,
        }
        yield event.plain_result(
            f"请于30秒内发送要添加到【{category}】类别的图片（支持多图）"
        )

    @filter.event_message_type(EventMessageType.ALL)
    async def handle_upload_image(self, event: AstrMessageEvent):
        """处理用户上传的图片"""
        user_key = f"{event.session_id}_{event.get_sender_id()}"
        upload_state = self.upload_states.get(user_key)

        if not upload_state or time.time() > upload_state["expire_time"]:
            if user_key in self.upload_states:
                del self.upload_states[user_key]
            return

        images = [c for c in event.message_obj.message if isinstance(c, Image)]

        if not images:
            yield event.plain_result("请发送图片文件进行上传")
            return

        category_cn = upload_state["category"]
        category_en = self.emotion_map[category_cn]
        save_dir = os.path.join(self.meme_path, category_en)

        try:
            os.makedirs(save_dir, exist_ok=True)
            saved_files = []

            # 创建忽略 SSL 验证的上下文
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            for idx, img in enumerate(images, 1):
                timestamp = int(time.time())

                try:
                    # 特殊处理腾讯多媒体域名
                    if "multimedia.nt.qq.com.cn" in img.url:
                        insecure_url = img.url.replace("https://", "http://", 1)
                        self.logger.warning(
                            f"检测到腾讯多媒体域名，使用 HTTP 协议下载: {insecure_url}"
                        )
                        async with aiohttp.ClientSession() as session:
                            async with session.get(insecure_url) as resp:
                                content = await resp.read()
                    else:
                        async with aiohttp.ClientSession(
                            connector=aiohttp.TCPConnector(ssl=ssl_context)
                        ) as session:
                            async with session.get(img.url) as resp:
                                content = await resp.read()

                    file_type = imghdr.what(None, h=content)
                    if not file_type:
                        try:
                            with Image.open(io.BytesIO(content)) as temp_img:
                                temp_img.verify()  # 验证文件完整性
                                file_type = temp_img.format.lower()
                        except Exception as e:
                            self.logger.error(f"图片格式检测失败: {str(e)}")
                            file_type = "unknown"

                    ext_mapping = {
                        "jpeg": ".jpg",
                        "png": ".png",
                        "gif": ".gif",
                        "webp": ".webp",
                    }
                    ext = ext_mapping.get(file_type, ".bin")
                    filename = f"{timestamp}_{idx}{ext}"
                    save_path = os.path.join(save_dir, filename)

                    with open(save_path, "wb") as f:
                        f.write(content)
                    saved_files.append(filename)

                except Exception as e:
                    self.logger.error(f"下载图片失败: {str(e)}")
                    yield event.plain_result(f"文件 {img.url} 下载失败: {str(e)}")
                    continue

            del self.upload_states[user_key]
            result_msg = [
                Plain(f"成功添加 {len(saved_files)} 张图片到【{category_cn}】类别！")
            ]
            yield event.chain_result(result_msg)
            await self.reload_emotions()

        except Exception as e:
            self.logger.error(f"保存图片失败: {str(e)}")
            yield event.plain_result(f"保存失败：{str(e)}")

    async def reload_emotions(self):
        """动态加载表情配置"""
        config_path = os.path.join(self.meme_path, "emotions.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.emotion_map.update(json.load(f))

    def _check_meme_directories(self):
        """检查表情包目录是否存在并且包含图片"""
        self.logger.info(f"表情包根目录: {self.meme_path}")
        if not os.path.exists(self.meme_path):
            self.logger.error(f"表情包根目录不存在: {self.meme_path}")
            return

        for emotion in self.emotion_map.values():
            emotion_path = os.path.join(self.meme_path, emotion)
            if not os.path.exists(emotion_path):
                self.logger.error(f"表情目录不存在: {emotion_path}")
                continue

            memes = [
                f
                for f in os.listdir(emotion_path)
                if f.endswith((".jpg", ".png", ".gif"))
            ]
            if not memes:
                self.logger.error(f"表情目录为空: {emotion_path}")
            else:
                self.logger.info(f"表情目录 {emotion} 包含 {len(memes)} 个图片")

    @filter.on_llm_response(priority=90)
    async def resp(self, event: AstrMessageEvent, response: LLMResponse):
        """处理 LLM 响应，识别表情"""
        if not response or not response.completion_text:
            return

        text = response.completion_text
        self.found_emotions = []  # 重置表情列表

        # 定义表情正则模式
        patterns = [
            r"\[([^\]]+)\]",  # [生气]
            r"\(([^)]+)\)",  # (生气)
            r"（([^）]+)）",  # （生气）
        ]

        clean_text = text

        # 查找所有表情标记
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                emotion = match.group(1)
                if emotion in self.emotion_map:
                    self.found_emotions.append(emotion)
                    clean_text = clean_text.replace(match.group(0), "")

        # 去重并限制最多2个表情
        self.found_emotions = list(dict.fromkeys(self.found_emotions))[:2]

        if self.found_emotions:
            response.completion_text = clean_text.strip()

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        """在消息发送前处理文本部分"""
        if not self.found_emotions:
            return

        result = event.get_result()
        if not result:
            return

        try:
            chains = []
            original_chain = result.chain

            if original_chain:
                if isinstance(original_chain, str):
                    chains.append(Plain(original_chain))
                elif isinstance(original_chain, MessageChain):
                    chains.extend([c for c in original_chain if isinstance(c, Plain)])
                elif isinstance(original_chain, list):
                    chains.extend([c for c in original_chain if isinstance(c, Plain)])

            text_result = event.make_result().set_result_content_type(
                ResultContentType.LLM_RESULT
            )
            for component in chains:
                if isinstance(component, Plain):
                    text_result = text_result.message(component.text)

            event.set_result(text_result)

        except Exception as e:
            self.logger.error(f"处理文本失败: {str(e)}")
            import traceback

            self.logger.error(traceback.format_exc())

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent):
        """消息发送后处理图片部分"""
        if not self.found_emotions:
            return

        try:
            for emotion in self.found_emotions:
                emotion_en = self.emotion_map.get(emotion)
                if not emotion_en:
                    continue

                emotion_path = os.path.join(self.meme_path, emotion_en)
                if not os.path.exists(emotion_path):
                    continue

                memes = [
                    f
                    for f in os.listdir(emotion_path)
                    if f.endswith((".jpg", ".png", ".gif"))
                ]
                if not memes:
                    continue

                meme = random.choice(memes)
                meme_file = os.path.join(emotion_path, meme)

                await self.context.send_message(
                    event.unified_msg_origin,
                    MessageChain([Image.fromFileSystem(meme_file)]),
                )
            self.found_emotions = []

        except Exception as e:
            self.logger.error(f"发送表情图片失败: {str(e)}")
            import traceback

            self.logger.error(traceback.format_exc())
        finally:
            self.found_emotions = []

    @filter.command("检查同步状态")
    async def check_sync_status(self, event: AstrMessageEvent):
        """检查表情包与图床的同步状态"""
        if not self.img_sync:
            yield event.plain_result("图床服务未配置，请先在配置文件中完成图床配置。")
            return
        
        try:
            status = self.img_sync.check_status()
            to_upload = status.get("to_upload", [])
            to_download = status.get("to_download", [])
            
            result = ["同步状态检查结果："]
            if to_upload:
                result.append(f"\n需要上传的文件({len(to_upload)}):")
                for file in to_upload[:5]:  # 只显示前5个
                    result.append(f"\n- {file['category']}/{file['filename']}")
                if len(to_upload) > 5:
                    result.append("\n...")
                
            if to_download:
                result.append(f"\n需要下载的文件({len(to_download)}):")
                for file in to_download[:5]:  # 只显示前5个
                    result.append(f"\n- {file['category']}/{file['filename']}")
                if len(to_download) > 5:
                    result.append("\n...")
                
            if not to_upload and not to_download:
                result.append("\n所有文件已同步！")
            
            yield event.plain_result("".join(result))
        except Exception as e:
            self.logger.error(f"检查同步状态失败: {str(e)}")
            yield event.plain_result(f"检查同步状态失败: {str(e)}")

    @filter.command("同步到云端")
    async def sync_to_remote(self, event: AstrMessageEvent):
        """将本地表情包同步到云端"""
        if not self.img_sync:
            yield event.plain_result("图床服务未配置，请先在配置文件中完成图床配置。")
            return
        
        try:
            yield event.plain_result("开始同步到云端...")
            success = await self.img_sync.start_sync('upload')
            if success:
                yield event.plain_result("同步到云端完成！")
            else:
                yield event.plain_result("同步到云端失败，请检查日志。")
        except Exception as e:
            self.logger.error(f"同步到云端失败: {str(e)}")
            yield event.plain_result(f"同步到云端失败: {str(e)}")

    @filter.command("从云端同步")
    async def sync_from_remote(self, event: AstrMessageEvent):
        """从云端同步表情包到本地"""
        if not self.img_sync:
            yield event.plain_result("图床服务未配置，请先在配置文件中完成图床配置。")
            return
        
        try:
            yield event.plain_result("开始从云端同步...")
            success = await self.img_sync.start_sync('download')
            if success:
                yield event.plain_result("从云端同步完成！")
                # 重新加载表情配置
                await self.reload_emotions()
            else:
                yield event.plain_result("从云端同步失败，请检查日志。")
        except Exception as e:
            self.logger.error(f"从云端同步失败: {str(e)}")
            yield event.plain_result(f"从云端同步失败: {str(e)}")

    def __del__(self):
        """清理资源"""
        if self.img_sync:
            self.img_sync.stop_sync()
        if self.server_process:
            shutdown_server(self.server_process)
