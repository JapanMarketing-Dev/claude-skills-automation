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

### 改善版フィードバックループ（v2）

従来のチューニングでは「後半でスコアが下がる」問題がありました。これを解決するために以下の改善を実施：

1. **スコアが上がった場合のみSkillsを更新**
2. **validate通過率が下がったら自動ロールバック**
3. **terraform validate + tflintによる厳密な評価**

```
┌─────────────────────────────────────────────────────────────┐
│              改善版フィードバックループ                        │
│                                                             │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│   │ 正解データ │───▶│ Skills   │───▶│ AI実行   │            │
│   │(Terraform)│    │ (ルール) │    │          │            │
│   └──────────┘    └──────────┘    └────┬─────┘            │
│                         ▲                 │                 │
│                         │                 ▼                 │
│   ┌──────────────┐ ┌────┴────┐    ┌──────────┐            │
│   │スコア上がった？│◀│自動改善  │◀───│ 評価比較  │            │
│   │              │ │         │    │+tflint   │            │
│   └──────┬───────┘ └─────────┘    └──────────┘            │
│          │                                                  │
│    YES ──┼── NO                                             │
│    ↓     ↓                                                  │
│ 更新   ロールバック                                          │
└─────────────────────────────────────────────────────────────┘
```

## 実験結果と精度

### 最新チューニング結果（v2: 改善版フィードバックループ）

| 回数 | 平均スコア | validate通過率 | 状態 |
|:---:|:---:|:---:|:---:|
| 1回目 | 61.95% | **100%** | |
| 2回目 | 47.12% | 66.67% | ⚠️ ロールバック |
| 3回目 | 46.69% | 66.67% | ⚠️ ロールバック |
| **4回目** | **68.34%** | **100%** | **★ BEST** |
| 5回目 | 35.67% | 33.33% | ⚠️ ロールバック |

**改善のポイント：**
- スコアが下がった場合は自動的にベストSkillsにロールバック
- Iteration 4でスコアが向上（61.95% → 68.34%、+6.39%）
- **最終的にベストスコア（68.34%、validate 100%）のSkillsを採用**

### 評価指標（v2）

| 指標 | 重み | 説明 |
|:---|:---:|:---|
| validate通過 | **必須** | `terraform validate`が通らないと大幅減点 |
| リソース一致率 | 50% | 必要なAWSサービスが含まれているか |
| 設定類似度 | 30% | コードの構造が正解に近いか |
| tflint警告なし | 20% | 静的解析で警告がないか |

### 現在使用中のSkillsバージョン

**Iteration 4の結果（68.34%、validate 100%）を採用**しています。

| ファイル | 内容 | スコア | validate通過率 | 状態 |
|:---|:---|:---:|:---:|:---:|
| **terraform-aws.md** | **Iteration 4の結果** | **68.34%** | **100%** | **★使用中** |
| terraform-aws_backup_1.md | Iteration 1の結果 | 61.95% | 100% | バックアップ |
| terraform-aws_backup_4.md | Iteration 4のバックアップ | 68.34% | 100% | バックアップ |

### 旧バージョン（v1）との比較

| 項目 | v1（旧） | v2（改善版） |
|:---|:---:|:---:|
| 最終スコア | 53.5% | **68.34%** |
| validate通過率 | 66.7% | **100%** |
| 後半のスコア低下 | あり | **自動ロールバックで防止** |
| 静的解析 | なし | **tflint導入** |

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

チューニングの特徴：
- スコアが上がった場合のみSkillsを更新
- validate通過率が下がったら自動ロールバック
- 最終的にベストスコアのSkillsを採用

## ファイル構成

```
claude-skills-automation/
├── src/
│   ├── web.py              # WebUI（ブラウザ画面）
│   ├── main.py             # チューニングのメイン処理（v2改善版）
│   ├── runner.py           # AIにTerraformを生成させる
│   ├── evaluator.py        # 評価ロジック（terraform validate + tflint）
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
├── Dockerfile              # terraform + tflint入り
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
