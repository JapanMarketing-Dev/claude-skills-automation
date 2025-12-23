# AWS Terraform生成スキル

このスキルは、ユーザーの要望からAWSインフラのTerraformコードを生成します。

## 基本原則

1. **動作するコードを生成する**: 構文エラーのない、`terraform validate`が通るコードを出力
2. **外部依存を排除する**: 外部ファイルへの参照を行わず、すべてTerraformコード内で完結
3. **ベストプラクティスに従う**: AWSのWell-Architected Frameworkに沿った設計
4. **変数化**: ハードコーディングを避け、適切に変数化する
5. **モジュール構造**: 再利用可能な構造を維持
6. **適切なリソース選択**: 要件に最適なAWSサービスとリソースを選択
7. **最小構成の原則**: 要件に明記されていない機能は追加しない

## 禁止事項（必須遵守）

### 絶対に使用禁止
1. **templatefile関数**: `templatefile("${path.module}/file", {})`の使用を禁止
2. **外部ファイル参照**: 存在しないスクリプトファイルへの参照禁止
3. **file関数**: 外部ファイル読み込み関数の使用禁止
4. **パターン外リソース混在**: 異なるアーキテクチャパターンのリソース混在禁止

### user_data設定ルール（厳格）
```hcl
# 正しい方法（インライン記述）
user_data = base64encode(<<-EOF
#!/bin/bash
yum update -y
yum install -y httpd
systemctl start httpd
systemctl enable httpd
echo "<h1>Hello World</h1>" > /var/www/html/index.html
EOF
)

# 禁止（外部ファイル参照）
user_data = base64encode(templatefile("${path.module}/user_data.sh", {}))  # ❌ 使用禁止
user_data = file("${path.module}/user_data.sh")  # ❌ 使用禁止
```

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
- IAM: aws_iam_role, aws_iam_instance_profile, aws_iam_policy, aws_iam_role_policy_attachment
- データベース: aws_db_instance, aws_db_subnet_group（明示的要求がある場合）
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
- aws_iam_instance_profile
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

**厳格に除外するリソース:**
```
- aws_apigatewayv2_api
- aws_apigatewayv2_stage
- aws_apigatewayv2_route
- aws_apigatewayv2_integration
- aws_iam_role_policy
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

### Web3層 Launch Template（外部ファイル依存排除版）
```hcl
resource "aws_launch_template" "main" {
  name_prefix   = "${var.project_name}-template-"
  description   = "Launch template for ${var.project_name}"
  image_id      = var.ami_id
  instance_type = var.instance_type
  
  vpc_security_group_ids = [aws_security_group.ec2.id]
  
  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_profile.name
  }
  
  # user_dataをインラインで記述（外部ファイル参照禁止）
  user_data = base64encode(<<-EOF
#!/bin/bash
yum update -y
yum install -y httpd
systemctl start httpd
systemctl enable httpd
echo "<h1>Hello from ${var.project_name}</h1>" > /var/www/html/index.html
EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project_name}-instance"
    }
  }

  tags = {
    Name = "${var.project_name}-launch-template"
  }
}
```

### Web3層 IAM設定テンプレート（完全版）
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

# IAM Instance Profile（Web3層必須）
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}_ec2_profile"
  role = aws_iam_role.ec2_role.name

  tags = {
    Name = "${var.project_name}_ec2_profile"
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

3. **外部依存チェック**:
   - [ ] templatefile関数を使用していないか
   - [ ] file関数を使用していないか
   - [ ] 外部スクリプトファイルを参照していないか

### リソース生成チェック
1. **サーバーレス HTTP API の場合**:
   - [ ] 4点セット完備: api, stage, route, integration
   - [ ] IAMはインラインポリシー（`aws_iam_role_policy`）のみ
   - [ ] v1リソース（`aws_api_gateway_*`）を含まない
   - [ ] `aws_iam_instance_profile`を含まない
   - [ ] CloudWatch Log Group含む

2. **Web3層の場合**:
   - [ ] VPCフルスタック含む
   - [ ] ALB + Target Group + Listener含む  
   - [ ] Auto Scaling Group + Launch Template含む
   - [ ] IAMはマネージドポリシー（`aws_iam_policy` + attachment）
   - [ ] `aws_iam_instance_profile`を含む
   - [ ] user_dataはインラインで記述

3. **共通チェック**:
   - [ ] 要件にない余分なAWSサービスを含まない
   - [ ] 全リソースにNameタグ設定
   - [ ] 変数化適切に実施
   - [ ] depends_on関係適切に設定

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
   - `aws_iam_instance_profile`は使用しない
   
2. **マネージドポリシー（`aws_iam_policy` + attachment）使用**:
   - Web3層アーキテクチャ（**必須**）
   - EC2、ECS関連の権限設定
   - `aws_iam_instance_profile`を必ず含める

### EC2 user_data設定ルール（厳密）
1. **インライン記述（必須）**:
   ```hcl
   user_data = base64encode(<<-EOF
   #!/bin/bash
   # スクリプト内容をここに直接記述
   EOF
   )
   ```

2. **禁止事項**:
   ```hcl
   # 以下はすべて使用禁止
   user_data = base64encode(templatefile("${path.module}/user_data.sh", {}))  # ❌
   user_data = file("${path.module}/user_data.sh")  # ❌
   user_data = base64encode(file("user_data.sh"))  # ❌
   ```

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

### 禁止事項（再確認）
1. **外部ファイル参照の完全禁止**
   - `templatefile()`関数使用禁止
   - `file()`関数使用禁止
   - すべての設定をTerraformコード内で完結

2. **サーバーレスでのv1リソース使用禁止**
3. **異なるIAM設定パターンの混在禁止**  
4. **要件にない機能の推測実装禁止**
5. **ハードコーディング禁止**

## 要件分析チェックリスト（実行必須）

生成開始前に以下を必ず確認:

1. **アーキテクチャタイプ確認**:
   - [ ] Web3層: EC2、ALB等の記載
   - [ ] サーバーレス: Lambda、API等の記載
   - [ ] コンテナ: ECS、Docker等の記載

2. **API要件確認（サーバーレスの場合）**:
   - [ ] REST API明示: v1使用
   - [ ] HTTP API明示またはAPI種別指定なし: v2使用

3. **外部依存除去確認**:
   - [ ] 全ての設定をTerraformコード内で記述
   - [ ] 外部スクリプトファイルへの参照なし
   - [ ] templatefile/file関数の使用なし

4. **除外確認**:
   - [ ] 要件にないAWSサービスが含まれていないか
   - [ ] 推測で追加した機能がないか

この分析結果に基づき、該当するアーキテクチャパターンの必須リソースセットを**完全に**実装し、外部依存を排除した自己完結型のTerraformコードを生成する。