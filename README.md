# Claude Skills 自動チューニングシステム

Claude skillsを自動的にチューニングして、Terraform生成の精度を向上させるシステム。

## 概要

要望テキストからAWSインフラのTerraformコードを生成するClaude skillsを、正解データとの突合によって自動改善します。

### アプローチ

1. **正解データ**: 実際に動くTerraformコードを収集（AWSベストプラクティスベース）
2. **逆算**: Terraformから「どんな依頼でこれが出るか」を生成
3. **Skills作成**: 「依頼→Terraform」のパターンをskillsに定義
4. **検証**: skillsで依頼して、正しいTerraformが出るかチェック
5. **自動改善**: エラーパターンを分析し、skillsを自動更新

## 実行方法

### WebUI（Terraform生成）

```bash
# Docker環境でWebUIを起動
docker compose up --build

# ブラウザで http://localhost:8080 にアクセス
```

### チューニングループ実行

```bash
# Skillsの自動チューニングを実行
docker compose --profile tuning run --rm tuner
```

## 実験結果（2025/12/23）

### チューニングループ結果

| Iteration | Avg Score | Validate Pass Rate | 主な改善点 |
|-----------|-----------|-------------------|-----------|
| 1 | 69.38% | 100% | 初回実行 |
| 2 | 68.23% | 100% | API Gateway v1/v2の使い分け明確化 |
| 3 | 66.87% | 100% | アーキテクチャパターン判定強化 |
| 4 | 56.97% | 66.67% | templatefile関数使用禁止追加 |
| 5 | 53.53% | 66.67% | チューニング完了 |

### 観察と考察

1. **terraform validate通過率**: 初期3イテレーションで100%達成。実用的なTerraformコードが生成できている
2. **スコア変動**: Config Match（テキスト類似度）の変動が大きく、評価指標の改善が必要
3. **自動改善の効果**: skillsに以下が自動追加された：
   - `templatefile`関数の使用禁止ルール
   - `user_data`のインライン記述ルール
   - アーキテクチャパターン判定フローチャート
   - サーバーレスAPI必須リソース4点セット定義

### 改善すべき点

1. **評価指標の改善**
   - テキスト類似度だけでなく、構造的な正しさを評価
   - リソース間の依存関係の評価追加
   - セキュリティ設定の評価追加

2. **正解データの拡充**
   - 現在3パターン → 10-15パターンに拡充
   - より複雑な構成の追加

3. **skillsの初期品質向上**
   - 実際のエラーパターンを事前に組み込み
   - 具体的なコード例の追加

## プロジェクト構造

```
claude-skills-automation/
├── data/
│   └── training/           # 正解データ（依頼→Terraformペア）
├── skills/
│   └── terraform-aws.md    # Claude skills定義（自動更新される）
├── src/
│   ├── main.py             # メインエントリーポイント
│   ├── runner.py           # Claude API実行
│   ├── evaluator.py        # terraform validate + 比較評価
│   ├── skills_updater.py   # skills自動更新
│   └── models.py           # データモデル
├── output/                 # 生成されたTerraform
├── results/                # 評価結果JSON
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## 参考

- https://code.claude.com/docs/ja/skills
- https://code.claude.com/docs/ja/overview
- https://dev.classmethod.jp/articles/trial-and-error-aws-diagram-agent-skills/

## 環境変数

```
ANTHROPIC_API_KEY=your-api-key
```
