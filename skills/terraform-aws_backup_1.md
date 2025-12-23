# AWS Terraform生成スキル

このスキルは、ユーザーの要望からAWSインフラのTerraformコードを生成します。

## 基本原則

1. **動作するコードを生成する**: 構文エラーのない、`terraform validate`が通るコードを出力
2. **ベストプラクティスに従う**: AWSのWell-Architected Frameworkに沿った設計
3. **変数化**: ハードコーディングを避け、適切に変数化する
4. **モジュール構造**: 再利用可能な構造を維持

## 出力形式

以下のファイルを生成:
- `main.tf`: メインリソース定義
- `variables.tf`: 入力変数
- `outputs.tf`: 出力値
- `providers.tf`: プロバイダー設定

## Terraform記述ルール

### プロバイダー設定
```hcl
terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
```

### 命名規則
- リソース名: `aws_<service>_<purpose>`
- 変数名: snake_case
- タグ: 必ず`Name`タグを含める

### セキュリティ
- セキュリティグループは最小権限の原則
- IAMロールは必要最小限のポリシー
- 暗号化はデフォルトで有効化

### 可用性
- Multi-AZ構成を推奨
- Auto Scalingの考慮
- 適切なヘルスチェック設定

## よくあるパターン

### Web3層アーキテクチャ
- ALB + EC2 Auto Scaling + RDS Multi-AZ
- VPCはPublic/Private subnet構成

### サーバーレス
- API Gateway + Lambda + DynamoDB
- CloudWatch Logsの設定を含める

### コンテナ
- ECS/Fargate + ALB
- タスク定義にログ設定を含める

## エラー回避

1. **循環参照を避ける**: depends_onを適切に使用
2. **必須属性を忘れない**: 特にセキュリティグループのegress
3. **データソースの活用**: 既存リソースの参照にはdata sourceを使う
4. **変数のデフォルト値**: 必要に応じてdefaultを設定

