"""Skills自動更新ロジック（改善版）"""
from pathlib import Path
from anthropic import Anthropic
from rich.console import Console
from .models import EvaluationResult

console = Console()


def analyze_errors(results: list[EvaluationResult]) -> dict:
    """
    エラーパターンを詳細分析
    
    Returns:
        dict: エラー分析結果
    """
    analysis = {
        "validation_errors": [],
        "missing_resources": {},  # リソース名: 出現回数
        "extra_resources": {},    # リソース名: 出現回数
        "tflint_warnings": [],
        "low_score_cases": [],
        "high_score_cases": []    # 成功パターンも収集
    }
    
    for result in results:
        # バリデーションエラー
        if not result.validate_passed:
            analysis["validation_errors"].append({
                "data_id": result.data_id,
                "error": result.validate_error
            })
        
        # エラー分析
        for error in result.errors:
            if "Missing resources" in error:
                resources = error.replace("Missing resources: ", "").split(", ")
                for r in resources:
                    analysis["missing_resources"][r] = analysis["missing_resources"].get(r, 0) + 1
            elif "Extra resources" in error:
                resources = error.replace("Extra resources: ", "").split(", ")
                for r in resources:
                    analysis["extra_resources"][r] = analysis["extra_resources"].get(r, 0) + 1
            elif "tflint" in error:
                analysis["tflint_warnings"].append(error)
        
        # スコア別分類
        if result.overall_score < 0.6:
            analysis["low_score_cases"].append({
                "data_id": result.data_id,
                "score": result.overall_score,
                "errors": result.errors
            })
        elif result.overall_score >= 0.8:
            analysis["high_score_cases"].append({
                "data_id": result.data_id,
                "score": result.overall_score
            })
    
    # 頻出する不足リソースをソート
    analysis["missing_resources"] = dict(
        sorted(analysis["missing_resources"].items(), key=lambda x: -x[1])
    )
    analysis["extra_resources"] = dict(
        sorted(analysis["extra_resources"].items(), key=lambda x: -x[1])
    )
    
    return analysis


def generate_skills_update(
    client: Anthropic,
    current_skills: str,
    error_analysis: dict,
    model: str = "claude-sonnet-4-20250514"
) -> tuple[str, list[str]]:
    """
    エラー分析に基づいてskillsを改善（改善版）
    
    重要：
    - 既存の良いルールは維持
    - 追加は最小限に
    - 具体的なエラーに対する対策のみ追加
    """
    # 深刻なエラーがない場合は更新しない
    if (not error_analysis.get('validation_errors') and 
        not error_analysis.get('missing_resources') and
        len(error_analysis.get('low_score_cases', [])) == 0):
        return current_skills, ["改善が不要（エラーなし）"]
    
    prompt = f"""あなたはTerraform Skillsの改善エキスパートです。
以下のSkills定義とエラー分析結果を見て、**最小限の改善**を行ってください。

## 重要なルール
1. **既存のルールは維持する** - 動作しているルールは変更しない
2. **追加は最小限に** - 具体的なエラーに対する対策のみ追加
3. **シンプルに保つ** - 複雑なルールは避ける
4. **過学習を防ぐ** - 汎用的なルールのみ追加

## 現在のスキル定義

{current_skills}

## エラー分析結果

### バリデーションエラー（terraform validate失敗）
{error_analysis.get('validation_errors', [])}

### 頻繁に不足するリソース
{error_analysis.get('missing_resources', {})}

### 余分に生成されるリソース
{error_analysis.get('extra_resources', {})}

### tflint警告
{error_analysis.get('tflint_warnings', [])}

### 低スコアケース
{error_analysis.get('low_score_cases', [])}

### 高スコアケース（参考）
{error_analysis.get('high_score_cases', [])}

## タスク

上記のエラーを解消するために、以下の形式で出力してください：

[UPDATES_START]
- 改善点1の説明
- 改善点2の説明
（最大3点まで）
[UPDATES_END]

[SKILLS_START]
（更新後の完全なスキル定義）
[SKILLS_END]

重要：
- 既存の良いルールはそのまま維持
- 追加するルールは具体的なエラーに対応するもののみ
- 複雑化を避け、シンプルに保つ
"""

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    content = response.content[0].text
    
    # 更新内容を抽出
    updates = []
    updates_start = content.find("[UPDATES_START]")
    updates_end = content.find("[UPDATES_END]")
    if updates_start != -1 and updates_end != -1:
        updates_text = content[updates_start + len("[UPDATES_START]"):updates_end].strip()
        updates = [line.strip().lstrip("- ").lstrip("• ") 
                  for line in updates_text.split("\n") 
                  if line.strip() and not line.strip().startswith("#")]
    
    # 更新後のスキルを抽出
    skills_start = content.find("[SKILLS_START]")
    skills_end = content.find("[SKILLS_END]")
    if skills_start != -1 and skills_end != -1:
        new_skills = content[skills_start + len("[SKILLS_START]"):skills_end].strip()
        # マークダウンのコードブロックを除去
        new_skills = new_skills.replace("```markdown", "").replace("```", "").strip()
    else:
        # マーカーがない場合は現在のスキルを維持
        new_skills = current_skills
        updates = ["スキル更新なし（マーカーが見つかりませんでした）"]
    
    return new_skills, updates


def save_skills(skills_content: str, skills_path: Path) -> None:
    """スキルファイルを保存"""
    skills_path.write_text(skills_content, encoding="utf-8")
    console.print(f"[green]✓[/green] Skills saved: {skills_path}")


def backup_skills(skills_path: Path, iteration: int) -> Path:
    """スキルファイルをバックアップ"""
    backup_path = skills_path.parent / f"{skills_path.stem}_backup_{iteration}{skills_path.suffix}"
    if skills_path.exists():
        backup_path.write_text(skills_path.read_text(encoding="utf-8"), encoding="utf-8")
        console.print(f"[blue]ℹ[/blue] Skills backed up: {backup_path}")
    return backup_path
