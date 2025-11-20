# 字体文件使用说明

## 已下载的字体

此目录包含开源中文字体文件：

1. **wqy-microhei.ttc** (4.9MB) - 文泉驿微米黑
   - 轻量级中文字体
   - 适合嵌入Docker镜像

2. **wqy-zenhei.ttc** (285KB) - 文泉驿正黑
   - 超轻量级中文字体
   - 最适合Docker环境

## 在Docker中使用这些字体

### 方法1: 在Dockerfile中复制字体文件（推荐）

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装ffmpeg和fontconfig
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# 复制字体文件到容器
COPY fonts/*.ttc /usr/share/fonts/truetype/wqy/

# 更新字体缓存
RUN fc-cache -fv

# 复制应用代码
COPY . .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8201
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8201"]
```

### 方法2: 使用docker-compose挂载字体

```yaml
version: '3'
services:
  video-service:
    build: .
    volumes:
      - ./fonts:/usr/share/fonts/truetype/wqy:ro
    environment:
      - FONTCONFIG_PATH=/etc/fonts
    ports:
      - "8201:8201"
```

### 方法3: 运行时挂载

```bash
docker run -d \
  -p 8201:8201 \
  -v $(pwd)/fonts:/usr/share/fonts/truetype/wqy:ro \
  --name video-service \
  your-image:latest
```

## 验证字体安装

在容器内运行：

```bash
# 进入容器
docker exec -it <container_name> bash

# 列出中文字体
fc-list :lang=zh

# 查找默认中文字体
fc-match :lang=zh
```

## 字体文件路径

代码已更新，会自动查找以下路径：
- `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc`
- `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`

## 许可证

这些字体均为开源字体：
- WenQuanYi Micro Hei: GPL v3
- WenQuanYi Zen Hei: GPL v2

可以自由用于商业和非商业项目。
