# Claude Skills 自動チューニングシステム

## このプロジェクトは何？

「AWSのインフラを作りたい」という要望を入力すると、実際に動くTerraformコードを生成するシステムです。

さらに、**AIの出力精度を自動的に改善する仕組み**を備えています。

## 解決したい問題

AIに「こんなAWS構成を作って」と依頼しても、出力されるTerraformコードが**実際には動かない**ことがほとんどです。

```
ユーザー: 「ALBとEC2とRDSでWebアプリ基盤を作って」
     ↓
AI: Terraformコードを出力
     ↓
実行: terraform validate → エラー！動かない...
```

## 解決アプローチ

### 従来の方法（うまくいかない）
```
要望 → AIが推測でコード生成 → だいたい動かない
```

### このプロジェクトの方法（逆算アプローチ）
```
① 実際に動くTerraformコードを集める（正解データ）
② そのコードから「どんな依頼でこれが出るか」を逆算
③ 「依頼→コード」のパターンをAIに学習させる（Skills）
④ AIの出力と正解を比較し、間違いを分析
⑤ 分析結果をもとにSkillsを自動改善
⑥ ③〜⑤を繰り返して精度を上げる
```

```
┌─────────────────────────────────────────────────────────┐
│                    チューニングループ                      │
│                                                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│   │ 正解データ │───▶│ Skills   │───▶│ AI実行   │        │
│   │(Terraform)│    │ (ルール) │    │          │        │
│   └──────────┘    └──────────┘    └────┬─────┘        │
│                         ▲                 │             │
│                         │                 ▼             │
│                   ┌─────┴────┐    ┌──────────┐        │
│                   │ 自動改善  │◀───│ 評価比較  │        │
│                   │          │    │          │        │
│                   └──────────┘    └──────────┘        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 実験結果と精度

### チューニングの推移

| 回数 | 平均スコア | terraform validate通過率 | 主な改善内容 |
|:---:|:---:|:---:|:---|
| 1回目 | 69.4% | **100%** | 初期状態 |
| 2回目 | 68.2% | **100%** | API Gateway v1/v2の使い分けルール追加 |
| 3回目 | 66.9% | **100%** | アーキテクチャ判定フロー追加 |
| 4回目 | 57.0% | 66.7% | templatefile関数の禁止ルール追加 |
| 5回目 | 53.5% | 66.7% | 最終状態 |

### 精度の見方

#### terraform validate通過率（重要）
- 生成されたコードが**構文的に正しいか**を示す指標
- 初期3回は**100%達成** → 実用レベルのコードが生成できている
- 4回目以降で低下 → Skillsの過学習（後述）

#### 平均スコア
以下の3つの指標を組み合わせた総合スコアです：

| 指標 | 重み | 説明 |
|:---|:---:|:---|
| validate通過 | 30% | `terraform validate`が通るか |
| リソース一致率 | 40% | 必要なAWSサービスが含まれているか |
| 設定一致率 | 30% | コードの内容が正解に近いか |

### 現在使用中のSkillsバージョン

チューニングを重ねるとSkillsが複雑化し、4回目以降は**過学習**によりvalidate通過率が低下しました。

そのため、**最高精度を記録した1回目の結果（69.4%、validate 100%）を採用**しています。

| ファイル | 内容 | スコア | validate通過率 | 状態 |
|:---|:---|:---:|:---:|:---:|
| terraform-aws_backup_1.md | 初期状態 | - | - | バックアップ |
| **terraform-aws.md** | **1回目の結果** | **69.4%** | **100%** | **使用中** |
| terraform-aws_backup_3.md | 2回目の結果 | 68.2% | 100% | バックアップ |
| terraform-aws_backup_4.md | 3回目の結果 | 66.9% | 100% | バックアップ |
| terraform-aws_backup_5.md | 5回目の結果 | 53.5% | 66.7% | バックアップ |

> **ポイント**: チューニングは「やればやるほど良くなる」わけではありません。
> 過学習を防ぐため、**validate通過率100%を維持できる範囲で最高スコアのバージョン**を選択しています。

### 課題と考察

#### うまくいったこと
1. **terraform validate 100%達成**（初期3回）
   - 生成されたコードは実際に動作する品質
2. **Skillsの自動改善が機能**
   - エラーパターンを分析し、ルールが自動追加された
   - 例：`templatefile`関数の使用禁止ルール

#### 改善が必要なこと
1. **評価指標の改善**
   - 現在はテキストの類似度で比較しているため、正確な評価ができていない
   - 構造的な正しさを評価する仕組みが必要

2. **正解データの拡充**
   - 現在3パターンのみ → 10-15パターンに増やす必要あり

3. **過学習の防止**
   - 4回目以降、Skillsが複雑になりすぎてvalidate通過率が低下
   - 最適な停止タイミングの自動判定が必要

## Skillsとは？

Claude（AI）に対する**ルールブック**のようなものです。

```markdown
# 例：Skills定義の一部

## 禁止事項
- templatefile関数の使用禁止
- 外部ファイルへの参照禁止

## サーバーレスAPIの場合
必ず以下の4つのリソースを含めること：
- aws_apigatewayv2_api
- aws_apigatewayv2_stage
- aws_apigatewayv2_route
- aws_apigatewayv2_integration
```

このSkillsがチューニングによって自動的に改善されていきます。

## 使い方

### 1. WebUIでTerraform生成（かんたん）

```bash
# Dockerで起動
docker compose up --build

# ブラウザでアクセス
# http://100.113.108.98:8080 （Tailscale経由の場合）
# http://localhost:8080 （ローカルの場合）
```

1. テキストエリアに要望を入力
2. 「Terraform生成」ボタンをクリック
3. 生成されたコードをコピーして使用

### 2. Skillsのチューニング実行

```bash
# 自動チューニングを実行（5回繰り返し）
docker compose --profile tuning run --rm tuner
```

## ファイル構成

```
claude-skills-automation/
├── src/
│   ├── web.py              # WebUI（ブラウザ画面）
│   ├── main.py             # チューニングのメイン処理
│   ├── runner.py           # AIにTerraformを生成させる
│   ├── evaluator.py        # 生成結果を評価する
│   ├── skills_updater.py   # Skillsを自動改善する
│   └── models.py           # データ構造の定義
├── skills/
│   └── terraform-aws.md    # AIへのルールブック（自動改善される）
├── data/training/          # 正解データ（要望→Terraformのペア）
│   ├── 001_alb_ec2_rds.json    # Web3層構成
│   ├── 002_serverless_api.json # サーバーレスAPI
│   └── 003_ecs_fargate.json    # コンテナ構成
├── output/                 # 生成されたTerraformコード
├── results/                # 評価結果のJSON
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 正解データの形式

```json
{
  "id": "001_alb_ec2_rds",
  "source": "AWS Well-Architected Framework",
  "request": "高可用性のWebアプリケーション基盤を構築したい。ALBで負荷分散し、EC2をAuto Scalingで配置、RDSはMulti-AZで冗長化。",
  "terraform_files": {
    "main_tf": "resource \"aws_vpc\" ...",
    "variables_tf": "variable \"aws_region\" ...",
    "outputs_tf": "output \"alb_dns_name\" ...",
    "providers_tf": "terraform { ... }"
  },
  "tags": ["alb", "ec2", "rds", "high-availability"]
}
```

## 今後の改善案

1. **正解データの追加**
   - より多くのAWSアーキテクチャパターンを収集
   - 実際のプロジェクトで使われたTerraformを活用

2. **評価方法の改善**
   - リソースの依存関係を評価
   - セキュリティ設定の評価
   - `terraform plan`の実行結果も評価に含める

3. **Skills改善ロジックの最適化**
   - ルールの重要度を判定
   - 矛盾するルールの自動削除

## 環境変数

`.env`ファイルに以下を設定：

```
ANTHROPIC_API_KEY=your-api-key
```

## 参考リンク

- [Claude Code Skills公式ドキュメント](https://code.claude.com/docs/ja/skills)
- [Claude Code概要](https://code.claude.com/docs/ja/overview)
- [参考記事：AWSダイアグラム生成の試行錯誤](https://dev.classmethod.jp/articles/trial-and-error-aws-diagram-agent-skills/)
