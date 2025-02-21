from pathlib import Path
from typing import Dict, List, Optional, Union
from .core.sync_manager import SyncManager
from .providers.stardots_provider import StarDotsProvider
import multiprocessing
import sys
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

class ImageSync:
    """图片同步客户端

    用于在本地目录和远程图床之间同步图片文件。支持目录结构，
    可以保持本地目录分类在远程图床中。

    基本用法:
        sync = ImageSync(config={
            "key": "your_key",
            "secret": "your_secret",
            "space": "your_space"
        }, local_dir="path/to/images")

        # 检查同步状态
        status = sync.check_status()

        # 上传本地新文件到远程
        sync.upload_to_remote()

        # 下载远程新文件到本地
        sync.download_to_local()

        # 完全同步（双向）
        sync.sync_all()
    """

    def __init__(self, config: Dict[str, str], local_dir: Union[str, Path]):
        """
        初始化同步客户端

        Args:
            config: 包含图床配置信息的字典，必须包含 key、secret 和 space
            local_dir: 本地图片目录的路径
        """
        self.config = config  # 保存完整配置
        self.local_dir = Path(local_dir)  # 保存本地目录路径
        self.provider = self._initialize_provider(config)
        self.sync_manager = SyncManager(
            image_host=self.provider, 
            local_dir=self.local_dir
        )
        self.sync_process = None
        self._sync_task = None

    def _initialize_provider(self, config):
        # 初始化图床提供者
        if config.get("key") and config.get("secret"):
            # 假设你有一个名为 StarDotsProvider 的提供者
            return StarDotsProvider(config)
        else:
            logger.error("图床服务配置不完整，缺少 key 或 secret")
            return None

    def check_status(self) -> Dict[str, List[Dict[str, str]]]:
        """
        检查同步状态

        Returns:
            包含需要上传和下载的文件信息的字典:
            {
                "to_upload": [{"filename": "1.jpg", "category": "cats"}],
                "to_download": [{"filename": "2.jpg", "category": "dogs"}]
            }
        """
        return self.sync_manager.check_sync_status()

    async def start_sync(self, task: str) -> bool:
        """
        启动同步任务并异步等待完成
        
        Args:
            task: 同步任务类型 ('upload', 'download', 'sync_all')
            
        Returns:
            同步是否成功
        """
        # 如果已有正在运行的同步任务，先停止它
        if self.sync_process and self.sync_process.is_alive():
            logger.warning("已有正在运行的同步任务，将先停止它")
            self.stop_sync()

        # 检查是否需要同步
        status = self.check_status()
        if task == 'upload' and not status.get("to_upload"):
            logger.info("没有文件需要上传")
            return True
        elif task == 'download' and not status.get("to_download"):
            logger.info("没有文件需要下载")
            return True

        # 创建并启动进程，使用 self.local_dir 而不是 sync_manager.local_dir
        self.sync_process = multiprocessing.Process(
            target=run_sync_process,
            args=(self.config, str(self.local_dir), task)  # 使用字符串形式的路径
        )
        self.sync_process.start()

        # 创建异步任务来等待进程完成
        loop = asyncio.get_event_loop()
        self._sync_task = loop.run_in_executor(None, self.sync_process.join)
        
        try:
            # 等待进程完成
            await self._sync_task
            return self.sync_process.exitcode == 0
        except Exception as e:
            logger.error(f"同步任务异常: {str(e)}")
            self.stop_sync()
            return False

    def stop_sync(self):
        """停止当前正在运行的同步任务"""
        if self.sync_process and self.sync_process.is_alive():
            self.sync_process.terminate()
            self.sync_process.join(timeout=5)
            if self.sync_process.is_alive():
                self.sync_process.kill()
            self.sync_process = None
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            self._sync_task = None

    def upload_to_remote(self) -> multiprocessing.Process:
        """
        在独立进程中将本地新文件上传到远程
        
        Returns:
            同步进程对象
        """
        # 总是返回进程对象，让进程内部处理是否需要同步
        self.sync_process = self._start_sync_process('upload')
        return self.sync_process

    def download_to_local(self) -> multiprocessing.Process:
        """
        在独立进程中将远程新文件下载到本地
        
        Returns:
            同步进程对象
        """
        # 总是返回进程对象，让进程内部处理是否需要同步
        self.sync_process = self._start_sync_process('download')
        return self.sync_process

    def sync_all(self) -> bool:
        """
        执行完整的双向同步

        先上传本地新文件，再下载远程新文件

        Returns:
            同步是否成功
        """
        upload_success = self.upload_to_remote()
        download_success = self.download_to_local()
        return upload_success and download_success

    def get_remote_files(self) -> List[Dict[str, str]]:
        """
        获取远程文件列表

        Returns:
            远程文件信息列表:
            [
                {
                    "filename": "1.jpg",
                    "category": "cats",
                    "url": "https://..."
                }
            ]
        """
        return self.provider.get_image_list()

    def delete_remote_file(self, filename: str) -> bool:
        """
        删除远程文件

        Args:
            filename: 要删除的文件名

        Returns:
            删除是否成功
        """
        return self.provider.delete_image(filename)

    def _start_sync_process(self, task: str) -> multiprocessing.Process:
        """
        在独立进程中运行同步任务
        """
        # 创建进程对象
        process = multiprocessing.Process(
            target=run_sync_process,
            args=(self.config, str(self.local_dir), task)
        )
        
        # 启动进程
        process.start()
        return process

    def get_files_to_upload(self) -> List[Dict[str, str]]:
        """获取待上传的文件列表"""
        local_files = set(os.listdir(self.local_dir))
        remote_files = set(self.provider.get_image_list())  # 假设这个方法返回远程文件名列表
        to_upload = local_files - remote_files
        return [{"filename": file} for file in to_upload]

    def get_files_to_download(self) -> List[Dict[str, str]]:
        """获取待下载的文件列表"""
        remote_files = self.provider.get_image_list()  # 获取远程文件列表
        local_files = set(os.listdir(self.local_dir))
        to_download = set(remote_files) - local_files
        return [{"filename": file} for file in to_download]

def run_sync_process(config: Dict[str, str], local_dir: str, task: str):
    """
    在独立进程中运行同步任务
    """
    sync = ImageSync(config, local_dir)
    
    if task == 'upload':
        success = sync.sync_manager.sync_to_remote()
        sys.exit(0 if success else 1)
    elif task == 'download':
        success = sync.sync_manager.sync_from_remote()
        sys.exit(0 if success else 1)
    elif task == 'sync_all':
        upload_success = sync.sync_manager.sync_to_remote()
        download_success = sync.sync_manager.sync_from_remote()
        sys.exit(0 if upload_success and download_success else 1)
