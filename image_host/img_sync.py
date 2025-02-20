from pathlib import Path
from typing import Dict, List, Optional, Union
from .core.sync_manager import SyncManager
from .providers.stardots_provider import StarDotsProvider


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

    def upload_to_remote(self) -> bool:
        """
        将本地新文件上传到远程

        Returns:
            同步是否成功
        """
        return self.sync_manager.sync_to_remote()

    def download_to_local(self) -> bool:
        """
        将远程新文件下载到本地

        Returns:
            同步是否成功
        """
        return self.sync_manager.sync_from_remote()

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
