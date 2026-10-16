"""Capylulu 启动入口：python run.py → 监听 0.0.0.0:6661

一键启动生产模式：FastAPI(REST API) + Vue 构建产物(web/dist)。
前端源码在 web/，改动前端后需先 npm run build，再运行本入口生效。
"""
import os
import sys

# 确保项目根目录在模块搜索路径（供 capylulu.* 包导入）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("capylulu.server_api.main:app", host="0.0.0.0", port=6661)
