# client_config.py
import os

from pyupdater.client import Client
from pyupdater.utils.config import Config

APP_NAME = "jigger"
APP_VERSION = "1.0.0"
COMPANY_NAME = "wuyun"

# 更新服务器URL
UPDATE_URLS = ["https://3qk8.com/"]

def get_client_config():
    config = Config()
    
    # 应用信息
    config.APP_NAME = APP_NAME
    config.APP_VERSION = APP_VERSION
    config.COMPANY_NAME = COMPANY_NAME
    
    # 更新服务器
    config.UPDATE_URLS = UPDATE_URLS
    
    # 其他配置
    config.MAX_DOWNLOAD_RETRIES = 3
    config.SHOW_UPDATE_PROGRESS = True
    
    return config