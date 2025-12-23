# AWS Terraform生成スキル

このスキルは、ユーザーの要望からAWSインフラのTerraformコードを生成します。

## 基本原則

1. **動作するコードを生成する**: 構文エラーのない、`terraform validate`が通るコードを出力
2. **ベストプラクティスに従う**: AWSのWell-Architected Frameworkに沿った設計
3. **変数化**: ハードコーディングを避け、適切に変数化する
4. **モジュール構造**: 再利用可能な構造を維持
5. **適切なリソース選択**: 要件に最適なAWSサービスとリソースを選択

## 出力形式

以下のファイルを生成:
- `main.tf`: メインリソース定義
- `variables.tf`: 入力変数
- `outputs.tf`: 出力値
- `providers.tf`: プロバイダー設定

## 要件判定フローチャート

### Step 1: アーキテクチャタイプの判定
```
要件分析 → キーワード判定
├─ "サーバーレス" / "Lambda" / "API" → サーバーレスパターン
├─ "Web" / "3層" / "EC2" / "ALB" → Web3層パターン  
├─ "コンテナ" / "ECS" / "Docker" → コンテナパターン
└─ その他 → 個別分析
```

### Step 2: サーバーレス要件の詳細判定
```
サーバーレス確定 → API要件確認
├─ シンプルなHTTP API要件 → **HTTP API (v2) パターン**
├─ 複雑な変換・バリデーション → REST API (v1) パターン
└─ API不要 → Lambda単体パターン
```

### Step 3: 必須リソースの確定
判定されたパターンに基づいて、後述の「アーキテクチャパターンと必須リソース」から適切なリソースセットを選択

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

## AWSサービス選択ガイドライン

### API Gateway選択基準（重要）
- **HTTP API (v2)を優先使用する場合**: 
  - サーバーレスアプリケーション（**デフォルト選択**）
  - 単純なProxy統合
  - 低レイテンシが重要
  - コストを抑えたい場合
  - **キーワード**: "サーバーレス", "Lambda API", "HTTP API"

- **REST API (v1)を使用する場合のみ**:
  - 明示的にREST APIが指定された場合
  - 詳細なリクエスト/レスポンス変換が必要
  - API Keyやリクエストバリデーションが必要
  - **キーワード**: "REST API", "複雑な変換", "API Key"

### IAM設定ガイドライン
- **Inline Policy (`aws_iam_role_policy`)を使用（推奨）**: 
  - そのロール専用のポリシー
  - 小規模で単純な権限設定
  - **サーバーレス構成ではこれを使用**

- **Managed Policyを使用**:
  - 複数のロールで共有する権限
  - 複雑な権限設定
  - AWSマネージドポリシーを基盤とする場合

## アーキテクチャパターンと必須リソース

### Web3層アーキテクチャ
**必須リソース:**
- VPC関連: `aws_vpc`, `aws_subnet`, `aws_internet_gateway`, `aws_route_table`, `aws_route_table_association`
- セキュリティ: `aws_security_group`
- ロードバランサー: `aws_lb`, `aws_lb_target_group`, `aws_lb_listener`
- コンピュート: `aws_launch_template`, `aws_autoscaling_group`
- データベース: `aws_db_instance`, `aws_db_subnet_group`

### サーバーレス (HTTP API) - **デフォルトパターン**
**必須リソースセット（すべて含める）:**
- **API Gateway v2**: `aws_apigatewayv2_api`, `aws_apigatewayv2_stage`, `aws_apigatewayv2_route`, `aws_apigatewayv2_integration`
- **Lambda**: `aws_lambda_function`, `aws_lambda_permission`
- **IAM**: `aws_iam_role`, `aws_iam_role_policy` (インラインポリシー)
- **ログ**: `aws_cloudwatch_log_group`
- **ストレージ**: `aws_dynamodb_table` (必要に応じて)

**除外するリソース:**
- API Gateway v1関連: `aws_api_gateway_rest_api`, `aws_api_gateway_resource`, `aws_api_gateway_method`, `aws_api_gateway_integration`, `aws_api_gateway_deployment`, `aws_api_gateway_stage`
- Managed Policy: `aws_iam_policy`, `aws_iam_role_policy_attachment`

### サーバーレス (REST API) - 明示指定時のみ
**必須リソース:**
- API Gateway v1: `aws_api_gateway_rest_api`, `aws_api_gateway_resource`, `aws_api_gateway_method`, `aws_api_gateway_integration`, `aws_api_gateway_deployment`, `aws_api_gateway_stage`
- Lambda: `aws_lambda_function`, `aws_lambda_permission`
- IAM: `aws_iam_role`, `aws_iam_role_policy_attachment` with `aws_iam_policy`
- ログ: `aws_cloudwatch_log_group`

### コンテナ (ECS/Fargate)
**必須リソース:**
- ECS: `aws_ecs_cluster`, `aws_ecs_task_definition`, `aws_ecs_service`
- ネットワーク: VPC関連リソース, `aws_security_group`
- ロードバランサー: `aws_lb`, `aws_lb_target_group`, `aws_lb_listener`
- IAM: `aws_iam_role` (タスク実行用、タスク用)

## 実装時の注意点

### API Gateway v2 (HTTP API) 実装テンプレート
```hcl
# 基本構成 - この4つのリソースはセット
resource "aws_apigatewayv2_api" "api" {
  name          = var.api_name
  protocol_type = "HTTP"
  description   = var.api_description
  
  cors_configuration {
    allow_credentials = false
    allow_headers     = ["content-type", "x-amz-date", "authorization"]
    allow_methods     = ["*"]
    allow_origins     = ["*"]
  }
}

resource "aws_apigatewayv2_stage" "stage" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = var.stage_name
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id             = aws_apigatewayv2_api.api.id
  integration_type   = "AWS_PROXY"
  integration_method = "POST"
  integration_uri    = aws_lambda_function.function.invoke_arn
}

resource "aws_apigatewayv2_route" "route" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "${var.http_method} ${var.route_path}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}
```

### Lambda用IAM設定（インラインポリシー使用）
```hcl
resource "aws_iam_role" "lambda_role" {
  name = "${var.function_name}_role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# インラインポリシーを使用（サーバーレスではこちらを優先）
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.function_name}_policy"
  role = aws_iam_role.lambda_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}
```

## 誤選択防止チェックリスト

### 生成前チェック
1. **サーバーレス要件の場合**:
   - [ ] API Gateway v2 (HTTP API) を選択したか？
   - [ ] v1 (REST API) リソースを含めていないか？
   - [ ] 4つの必須リソース（api, stage, route, integration）をすべて含めたか？

2. **IAM設定の場合**:
   - [ ] サーバーレスでは `aws_iam_role_policy`（インライン）を使用したか？
   - [ ] 不要な `aws_iam_policy` や `aws_iam_role_policy_attachment` を含めていないか？

3. **不要リソース確認**:
   - [ ] 要件にないサービス（RDS、ECR等）を含めていないか？
   - [ ] アーキテクチャに関係ないリソースを生成していないか？

### 生成後チェック
1. **必須リソース漏れ確認**:
   - [ ] 選択したアーキテクチャパターンの必須リソースがすべて含まれているか？
   
2. **余分なリソース確認**:
   - [ ] 他のアーキテクチャパターンのリソースが混在していないか？
   - [ ] 要件に明記されていない機能のリソースを含めていないか？

## エラーパターン別対策

### Missing Resources対策
1. **API Gateway v2 関連漏れ**: 
   - `aws_apigatewayv2_stage`, `aws_apigatewayv2_route`, `aws_apigatewayv2_integration` が漏れやすい
   - 対策: HTTP APIでは4点セット（api, stage, route, integration）を必ずセット生成

2. **IAM Inline Policy漏れ**:
   - `aws_iam_role_policy` の生成忘れ
   - 対策: サーバーレスでは `aws_iam_role` と `aws_iam_role_policy` をペアで生成

### Extra Resources対策
1. **API Gateway v1/v2 混在**:
   - サーバーレス要件でv1リソースを生成してしまう
   - 対策: 要件判定フローチャートに従い、明示指定がない限りHTTP API (v2) を選択

2. **不要なAWSサービス**:
   - 要件にない RDS, ECR 等のリソース生成
   - 対策: 要件分析チェックリストで事前確認

3. **IAM設定の重複**:
   - Inline PolicyとManaged Policyの両方生成
   - 対策: サーバーレスではInline Policy（`aws_iam_role_policy`）のみ使用

## エラー回避

1. **循環参照を避ける**: depends_onを適切に使用
2. **必須属性を忘れない**: 特にセキュリティグループのegress
3. **データソースの活用**: 既存リソースの参照にはdata sourceを使う
4. **変数のデフォルト値**: 必要に応じてdefaultを設定
5. **API Gateway権限**: Lambdaとの統合時は`aws_lambda_permission`を必ず設定
6. **ログ設定**: CloudWatch Log Groupを事前に作成してLambda関数に関連付け

## 要件分析チェックリスト

要件を受け取った際は以下を確認:
1. **アーキテクチャタイプ**: Web3層 / サーバーレス / コンテナ / その他
2. **API要件**: シンプルなHTTP API（→v2） / 複雑なREST API（→v1） / API不要
3. **データストレージ**: RDS / DynamoDB / S3 / なし
4. **スケーリング要件**: Auto Scaling / 固定サイズ
5. **セキュリティ要件**: VPC / IAM / 暗号化
6. **明示的サービス指定**: 特定のAWSサービスが明記されているか