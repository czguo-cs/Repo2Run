FROM python:3.10

# optional, setup your docker proxy here
ENV http_proxy="http://iJbVyX:mJ8eR9tU6%5Bs@10.251.112.51:8799"
ENV https_proxy="http://iJbVyX:mJ8eR9tU6%5Bs@10.251.112.51:8799"
ENV no_proxy="localhost,127.0.0.1,::1,10.0.0.0/8,192.168.0.0/16,172.16.0.0/12,*.lan,.baidu.com,.baidu-int.com,baidu.com,baidu-int.com"
ENV NO_PROXY="$no_proxy"

# 安装必要的系统依赖
RUN apt-get update && apt-get install -y curl

# 安装 Poetry
RUN curl -sSL https://install.python-poetry.org | python -

# 将 Poetry 的 bin 目录添加到 PATH 环境变量
ENV PATH="/root/.local/bin:$PATH"

RUN pip install pytest

RUN pip install pipdeptree
        