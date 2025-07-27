"""
腾讯云COS存储服务
"""
import os
import json
import logging
from typing import Optional, Dict, Any
from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosServiceError, CosClientError
import aiofiles

from src.config.settings import settings

logger = logging.getLogger(__name__)


class COSStorageService:
    """腾讯云COS存储服务"""
    
    def __init__(self):
        """初始化COS客户端"""
        config = CosConfig(
            Region=settings.tencent_cos_region,
            SecretId=settings.tencent_secret_id,
            SecretKey=settings.tencent_secret_key,
            Scheme='https'
        )
        self.client = CosS3Client(config)
        self.bucket_name = settings.cos_bucket_name
        
    def upload_file(self, local_path: str, cos_key: str) -> bool:
        """
        上传文件到COS
        
        Args:
            local_path: 本地文件路径
            cos_key: COS对象键
            
        Returns:
            bool: 上传是否成功
        """
        try:
            # 检查本地文件是否存在
            if not os.path.exists(local_path):
                logger.error(f"本地文件不存在: {local_path}")
                return False
            
            # 上传文件
            response = self.client.upload_file(
                Bucket=self.bucket_name,
                LocalFilePath=local_path,
                Key=cos_key,
                EnableMD5=True
            )
            
            logger.info(f"文件上传成功: {local_path} -> {cos_key}")
            return True
            
        except CosServiceError as e:
            logger.error(f"COS服务错误: {e}")
            return False
        except CosClientError as e:
            logger.error(f"COS客户端错误: {e}")
            return False
        except Exception as e:
            logger.error(f"上传文件失败: {e}")
            return False
    
    def download_file(self, cos_key: str, local_path: str) -> bool:
        """
        从COS下载文件
        
        Args:
            cos_key: COS对象键
            local_path: 本地保存路径
            
        Returns:
            bool: 下载是否成功
        """
        try:
            # 确保本地目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 下载文件
            response = self.client.download_file(
                Bucket=self.bucket_name,
                Key=cos_key,
                DestFilePath=local_path
            )
            
            logger.info(f"文件下载成功: {cos_key} -> {local_path}")
            return True
            
        except CosServiceError as e:
            logger.error(f"COS服务错误: {e}")
            return False
        except CosClientError as e:
            logger.error(f"COS客户端错误: {e}")
            return False
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return False
    
    def upload_json(self, data: Dict[Any, Any], cos_key: str) -> bool:
        """
        上传JSON数据到COS
        
        Args:
            data: 要上传的数据
            cos_key: COS对象键
            
        Returns:
            bool: 上传是否成功
        """
        try:
            # 转换为JSON字符串
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            
            # 直接上传内容
            response = self.client.put_object(
                Bucket=self.bucket_name,
                Body=json_content.encode('utf-8'),
                Key=cos_key,
                ContentType='application/json'
            )
            
            logger.info(f"JSON数据上传成功: {cos_key}")
            return True
            
        except CosServiceError as e:
            logger.error(f"COS服务错误: {e}")
            return False
        except CosClientError as e:
            logger.error(f"COS客户端错误: {e}")
            return False
        except Exception as e:
            logger.error(f"上传JSON数据失败: {e}")
            return False
    
    def upload_binary(self, data: bytes, cos_key: str, content_type: str = 'application/octet-stream') -> bool:
        """
        上传二进制数据到COS
        
        Args:
            data: 要上传的二进制数据
            cos_key: COS对象键
            content_type: MIME类型
            
        Returns:
            bool: 上传是否成功
        """
        try:
            # 直接上传二进制内容
            response = self.client.put_object(
                Bucket=self.bucket_name,
                Body=data,
                Key=cos_key,
                ContentType=content_type
            )
            
            logger.info(f"二进制数据上传成功: {cos_key} ({len(data)} bytes)")
            return True
            
        except CosServiceError as e:
            logger.error(f"COS服务错误: {e}")
            return False
        except CosClientError as e:
            logger.error(f"COS客户端错误: {e}")
            return False
        except Exception as e:
            logger.error(f"上传二进制数据失败: {e}")
            return False
    
    def download_json(self, cos_key: str) -> Optional[Dict[Any, Any]]:
        """
        从COS下载JSON数据
        
        Args:
            cos_key: COS对象键
            
        Returns:
            dict: JSON数据，失败返回None
        """
        try:
            # 获取对象
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=cos_key
            )
            
            # 读取内容
            content = response['Body'].read()
            
            # 解析JSON
            data = json.loads(content.decode('utf-8'))
            
            logger.info(f"JSON数据下载成功: {cos_key}")
            return data
            
        except CosServiceError as e:
            logger.error(f"COS服务错误: {e}")
            return None
        except CosClientError as e:
            logger.error(f"COS客户端错误: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"下载JSON数据失败: {e}")
            return None
    
    def delete_file(self, cos_key: str) -> bool:
        """
        删除COS文件
        
        Args:
            cos_key: COS对象键
            
        Returns:
            bool: 删除是否成功
        """
        try:
            response = self.client.delete_object(
                Bucket=self.bucket_name,
                Key=cos_key
            )
            
            logger.info(f"文件删除成功: {cos_key}")
            return True
            
        except CosServiceError as e:
            logger.error(f"COS服务错误: {e}")
            return False
        except CosClientError as e:
            logger.error(f"COS客户端错误: {e}")
            return False
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
    
    def file_exists(self, cos_key: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            cos_key: COS对象键
            
        Returns:
            bool: 文件是否存在
        """
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=cos_key
            )
            return True
            
        except CosServiceError as e:
            if e.get_error_code() == 'NoSuchKey':
                return False
            logger.error(f"COS服务错误: {e}")
            return False
        except CosClientError as e:
            logger.error(f"COS客户端错误: {e}")
            return False
        except Exception as e:
            logger.error(f"检查文件存在性失败: {e}")
            return False
    
    def get_file_url(self, cos_key: str, expires: int = 3600) -> Optional[str]:
        """
        获取文件的预签名URL
        
        Args:
            cos_key: COS对象键
            expires: 过期时间（秒）
            
        Returns:
            str: 预签名URL，失败返回None
        """
        try:
            url = self.client.get_presigned_url(
                Method='GET',
                Bucket=self.bucket_name,
                Key=cos_key,
                Expired=expires
            )
            
            logger.info(f"生成预签名URL成功: {cos_key}")
            return url
            
        except CosServiceError as e:
            logger.error(f"COS服务错误: {e}")
            return None
        except CosClientError as e:
            logger.error(f"COS客户端错误: {e}")
            return None
        except Exception as e:
            logger.error(f"生成预签名URL失败: {e}")
            return None


# 全局存储服务实例
storage_service = COSStorageService() 