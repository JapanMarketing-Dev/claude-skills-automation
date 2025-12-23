FROM python:3.12-slim

# Terraformのインストール
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Terraform最新版をインストール
RUN wget -q https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip \
    && unzip terraform_1.6.6_linux_amd64.zip \
    && mv terraform /usr/local/bin/ \
    && rm terraform_1.6.6_linux_amd64.zip

# uvのインストール
RUN pip install uv

WORKDIR /app

# 依存関係のコピーとインストール
COPY pyproject.toml .
RUN uv pip install --system -e .

# ソースコードのコピー
COPY . .

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "src.web:app", "--host", "0.0.0.0", "--port", "8080"]

