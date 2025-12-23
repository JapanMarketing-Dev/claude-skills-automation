# AWS Terraform生成スキル

このスキルは、ユーザーの要望からAWSインフラのTerraformコードを生成します。

## 基本原則

1. **動作するコードを生成する**: 構文エラーのない、`terraform validate`が通るコードを出力
2. **ベストプラクティスに従う**: AWSのWell-Architected Frameworkに沿った設計
3. **変数化**: ハードコーディングを避け、適切に変数化する
4. **モジュール構造**: 再利用可能な構造を維持
5. **適切なリソース選択**: 要件に最適なAWSサービスとリソースを選択
6. **最小構成の原則**: 要件に明記されていない機能は追加しない

## 出力形式

以下のファイルを生成:
- `main.tf`: メインリソース定義
- `variables.tf`: 入力変数
- `outputs.tf`: 出力値
- `providers.tf`: プロバイダー設定

## アーキテクチャパターン判定フロー

### Step 1: 必須キーワードによる自動判定
```
要件テキスト解析 → キーワード検索
├─ "EC2" または "ALB" または "Auto Scaling" → **Web3層パターン確定**
├─ "Lambda" かつ API要件あり → **サーバーレスAPIパターン確定**
├─ "Lambda" かつ API要件なし → **Lambda単体パターン確定**
├─ "ECS" または "Fargate" または "Docker" → **コンテナパターン確定**
└─ 上記に該当しない → 詳細分析
```

### Step 2: サーバーレスAPI種別の判定
```
サーバーレスAPI確定 → API種別確認
├─ "REST API"の明示的記載 → REST API (v1) パターン
├─ "HTTP API"の明示的記載 → HTTP API (v2) パターン  
└─ API種別の明示なし → **HTTP API (v2) パターン（デフォルト）**
```

### Step 3: 禁止事項チェック
以下に該当する場合はリソース生成を行わない:
- 要件に明記されていないAWSサービス
- 指定されたパターン以外のアーキテクチャコンポーネント
- Auto ScalingやCloudWatchアラーム（明示的要求がない場合）

## アーキテクチャパターンと厳密リソース定義

### 1. Web3層アーキテクチャ
**必須リソース（すべて含める）:**
```
- VPC関連: aws_vpc, aws_subnet, aws_internet_gateway, aws_route_table, aws_route_table_association
- セキュリティ: aws_security_group  
- ロードバランサー: aws_lb, aws_lb_target_group, aws_lb_listener
- コンピュート: aws_launch_template, aws_autoscaling_group
- データベース: aws_db_instance, aws_db_subnet_group
- IAM: aws_iam_role, aws_iam_role_policy_attachment, aws_iam_policy
```

**条件付きリソース（明示的要求がある場合のみ）:**
```
- aws_autoscaling_policy
- aws_cloudwatch_metric_alarm
```

### 2. サーバーレス HTTP API パターン（デフォルト）
**必須リソース4点セット（すべて含める）:**
```
- aws_apigatewayv2_api
- aws_apigatewayv2_stage  
- aws_apigatewayv2_route
- aws_apigatewayv2_integration
- aws_lambda_function
- aws_lambda_permission
- aws_iam_role
- aws_iam_role_policy (インラインポリシー)
- aws_cloudwatch_log_group
```

**厳格に除外するリソース:**
```
- aws_api_gateway_rest_api
- aws_api_gateway_resource  
- aws_api_gateway_method
- aws_api_gateway_integration
- aws_api_gateway_deployment
- aws_api_gateway_stage
- aws_iam_policy
- aws_iam_role_policy_attachment
```

### 3. サーバーレス REST API パターン（明示指定時のみ）
**必須リソース:**
```
- aws_api_gateway_rest_api
- aws_api_gateway_resource
- aws_api_gateway_method  
- aws_api_gateway_integration
- aws_api_gateway_deployment
- aws_api_gateway_stage
- aws_lambda_function
- aws_lambda_permission
- aws_iam_role
- aws_iam_role_policy_attachment
- aws_iam_policy
- aws_cloudwatch_log_group
```

## 必須実装テンプレート

### サーバーレス HTTP API（4点セット）
```hcl
# 1. API Gateway HTTP API
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

  tags = {
    Name = var.api_name
  }
}

# 2. ステージ（必須）
resource "aws_apigatewayv2_stage" "stage" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = var.stage_name
  auto_deploy = true

  tags = {
    Name = "${var.api_name}-${var.stage_name}"
  }
}

# 3. Lambda統合（必須）
resource "aws_apigatewayv2_integration" "lambda" {
  api_id             = aws_apigatewayv2_api.api.id
  integration_type   = "AWS_PROXY"
  integration_method = "POST"
  integration_uri    = aws_lambda_function.function.invoke_arn
}

# 4. ルート（必須）
resource "aws_apigatewayv2_route" "route" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "${var.http_method} ${var.route_path}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Lambda関数
resource "aws_lambda_function" "function" {
  filename         = var.lambda_filename
  function_name    = var.function_name
  role            = aws_iam_role.lambda_role.arn
  handler         = var.lambda_handler
  runtime         = var.lambda_runtime
  
  depends_on = [
    aws_iam_role_policy.lambda_policy,
    aws_cloudwatch_log_group.lambda_logs
  ]

  tags = {
    Name = var.function_name
  }
}

# IAM Role
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

  tags = {
    Name = "${var.function_name}_role"
  }
}

# IAM Policy（インライン - サーバーレス必須）
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

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.function_name}-logs"
  }
}

# Lambda Permission
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.function.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
```

### Web3層 IAM設定テンプレート
```hcl
# IAM Role
resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}_ec2_role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}_ec2_role"
  }
}

# IAM Policy（マネージド - Web3層）
resource "aws_iam_policy" "ec2_policy" {
  name        = "${var.project_name}_ec2_policy"
  description = "Policy for EC2 instances"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "ec2:DescribeTags"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}_ec2_policy"
  }
}

# Policy Attachment（Web3層）
resource "aws_iam_role_policy_attachment" "ec2_policy_attachment" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.ec2_policy.arn
}
```

## 生成前必須チェックリスト

### アーキテクチャ判定チェック
1. **キーワード確認**:
   - [ ] 「EC2」「ALB」→ Web3層確定
   - [ ] 「Lambda」+API → サーバーレス確定  
   - [ ] 「ECS」「Docker」→ コンテナ確定

2. **API種別確認（サーバーレスの場合）**:
   - [ ] 「REST API」明示 → v1使用
   - [ ] 「HTTP API」明示 or 指定なし → v2使用（デフォルト）

3. **追加機能確認**:
   - [ ] Auto Scaling: 明示的要求があるか？
   - [ ] CloudWatchアラーム: 明示的要求があるか？
   - [ ] データベース: 明示的要求があるか？

### リソース生成チェック
1. **サーバーレス HTTP API の場合**:
   - [ ] 4点セット完備: api, stage, route, integration
   - [ ] IAMはインラインポリシー（`aws_iam_role_policy`）
   - [ ] v1リソース（`aws_api_gateway_*`）を含まない
   - [ ] CloudWatch Log Group含む

2. **Web3層の場合**:
   - [ ] VPCフルスタック含む
   - [ ] ALB + Target Group + Listener含む  
   - [ ] Auto Scaling Group + Launch Template含む
   - [ ] IAMはマネージドポリシー（`aws_iam_policy` + attachment）

3. **共通チェック**:
   - [ ] 要件にない余分なAWSサービスを含まない
   - [ ] 全リソースにNameタグ設定
   - [ ] 変数化適切に実施

## AWSサービス選択の厳密ルール

### API Gateway選択（厳密）
1. **HTTP API (v2) 使用**:
   - サーバーレス要件かつAPI種別指定なし（**デフォルト**）
   - 「HTTP API」の明示的記載がある場合
   
2. **REST API (v1) 使用**:
   - 「REST API」の明示的記載がある場合**のみ**

### IAM設定選択（厳密）
1. **インラインポリシー（`aws_iam_role_policy`）使用**:
   - サーバーレスアーキテクチャ（**必須**）
   - Lambda関連の権限設定
   
2. **マネージドポリシー（`aws_iam_policy` + attachment）使用**:
   - Web3層アーキテクチャ（**必須**）
   - EC2、ECS関連の権限設定

### 条件付きリソース生成ルール
1. **Auto Scaling Policy & CloudWatch Alarm**:
   - 明示的に「スケーリング設定」「アラーム設定」が要求された場合のみ生成
   - 一般的なWeb3層要件では**生成しない**

2. **データベースリソース**:
   - 「データベース」「DB」「RDS」「DynamoDB」の明示的記載がある場合のみ
   - 「永続化」「データ保存」等の曖昧な要件では生成しない

## Terraform記述ルール

### プロバイダー設定（必須）
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

### 命名規則（厳密）
- リソース論理名: `aws_<service>_<purpose>`
- 変数名: snake_case
- タグ: **必ず**`Name`タグを含める
- 物理名: `${var.project_name}_<resource_type>`の形式

### セキュリティ（必須）
- セキュリティグループは最小権限の原則
- IAMロールは必要最小限のポリシー
- 暗号化はデフォルトで有効化
- CloudWatch Logsの保持期間設定

## エラー回避のための実装ルール

### 必須設定項目
1. **Lambda Permission**:
   ```hcl
   resource "aws_lambda_permission" "api_gateway" {
     statement_id  = "AllowExecutionFromAPIGateway"
     action        = "lambda:InvokeFunction"
     function_name = aws_lambda_function.function.function_name
     principal     = "apigateway.amazonaws.com"
     source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
   }
   ```

2. **CloudWatch Log Group事前作成**:
   ```hcl
   resource "aws_cloudwatch_log_group" "lambda_logs" {
     name              = "/aws/lambda/${var.function_name}"
     retention_in_days = 14
   }
   ```

3. **Dependencies設定**:
   ```hcl
   depends_on = [
     aws_iam_role_policy.lambda_policy,
     aws_cloudwatch_log_group.lambda_logs
   ]
   ```

### 禁止事項
1. **サーバーレスでのv1リソース使用禁止**
2. **異なるIAM設定パターンの混在禁止**  
3. **要件にない機能の推測実装禁止**
4. **ハードコーディング禁止**

## 要件分析チェックリスト（実行必須）

生成開始前に以下を必ず確認:

1. **アーキテクチャタイプ確認**:
   - [ ] Web3層: EC2、ALB等の記載
   - [ ] サーバーレス: Lambda、API等の記載
   - [ ] コンテナ: ECS、Docker等の記載

2. **API要件確認（サーバーレスの場合）**:
   - [ ] REST API明示: v1使用
   - [ ] HTTP API明示またはAPI種別指定なし: v2使用

3. **追加機能確認**:
   - [ ] データストレージ: 明示的要求の有無
   - [ ] スケーリング設定: 明示的要求の有無  
   - [ ] アラーム設定: 明示的要求の有無

4. **除外確認**:
   - [ ] 要件にないAWSサービスが含まれていないか
   - [ ] 推測で追加した機能がないか

この分析結果に基づき、該当するアーキテクチャパターンの必須リソースセットを**完全に**実装する。