from pathlib import Path
from typing import Dict, List, Optional, Union
from .core.sync_manager import SyncManager
from .providers.stardots_provider import StarDotsProvider
import multiprocessing
import sys


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
        self.provider = StarDotsProvider(
            {
                "key": config["key"],
                "secret": config["secret"],
                "space": config["space"],
                "local_dir": str(local_dir),
            }
        )
        self.sync_manager = SyncManager(
            image_host=self.provider, local_dir=Path(local_dir)
        )

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
        sync = ImageSync(self.provider.config, self.sync_manager.local_dir)
        
        if task == 'upload':
            status = sync.check_status()
            if not status.get("to_upload"):
                return multiprocessing.Process()  # 没有文件需要上传，返回空进程
            success = sync.upload_to_remote()
            return success.get_process()
        elif task == 'download':
            status = sync.check_status()
            if not status.get("to_download"):
                return multiprocessing.Process()  # 没有文件需要下载，返回空进程
            success = sync.download_to_local()
            return success.get_process()
        elif task == 'sync_all':
            success = sync.sync_all()
            return success.get_process()

def run_sync_process(config: Dict[str, str], local_dir: Union[str, Path], task: str):
    """
    在独立进程中运行同步任务
    """
    sync = ImageSync(config, local_dir)
    
    if task == 'upload':
        status = sync.check_status()
        if not status.get("to_upload"):
            return 0  # 没有文件需要上传，返回成功状态码
        success = sync.upload_to_remote()
        sys.exit(0 if success else 1)
    elif task == 'download':
        status = sync.check_status()
        if not status.get("to_download"):
            return 0  # 没有文件需要下载，返回成功状态码
        success = sync.download_to_local()
        sys.exit(0 if success else 1)
    elif task == 'sync_all':
        success = sync.sync_all()
        sys.exit(0 if success else 1)
