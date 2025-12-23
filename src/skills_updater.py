"""Skills自動更新ロジック"""
from pathlib import Path
from anthropic import Anthropic
from rich.console import Console
from .models import EvaluationResult

console = Console()


def analyze_errors(results: list[EvaluationResult]) -> dict:
    """
    エラーパターンを分析
    
    Returns:
        dict: エラー分析結果
    """
    analysis = {
        "validation_errors": [],
        "missing_resources": [],
        "extra_resources": [],
        "low_score_cases": []
    }
    
    for result in results:
        if not result.validate_passed:
            analysis["validation_errors"].append({
                "data_id": result.data_id,
                "error": result.validate_error
            })
        
        for error in result.errors:
            if "Missing resources" in error:
                resources = error.replace("Missing resources: ", "").split(", ")
                analysis["missing_resources"].extend(resources)
            elif "Extra resources" in error:
                resources = error.replace("Extra resources: ", "").split(", ")
                analysis["extra_resources"].extend(resources)
        
        if result.overall_score < 0.7:
            analysis["low_score_cases"].append({
                "data_id": result.data_id,
                "score": result.overall_score,
                "errors": result.errors
            })
    
    # 重複を除去してカウント
    analysis["missing_resources"] = list(set(analysis["missing_resources"]))
    analysis["extra_resources"] = list(set(analysis["extra_resources"]))
    
    return analysis


def generate_skills_update(
    client: Anthropic,
    current_skills: str,
    error_analysis: dict,
    model: str = "claude-sonnet-4-20250514"
) -> tuple[str, list[str]]:
    """
    エラー分析に基づいてskillsを更新
    
    Args:
        client: Anthropic client
        current_skills: 現在のskills内容
        error_analysis: エラー分析結果
    
    Returns:
        tuple: (更新後のskills, 更新内容のリスト)
    """
    prompt = f"""以下はAWS Terraformコード生成のためのスキル定義です。
このスキルを使ってTerraformを生成した結果、いくつかのエラーが発生しました。

## 現在のスキル定義

{current_skills}

## エラー分析結果

### バリデーションエラー
{error_analysis.get('validation_errors', [])}

### 不足していたリソース
{error_analysis.get('missing_resources', [])}

### 余分に生成されたリソース
{error_analysis.get('extra_resources', [])}

### 低スコアのケース
{error_analysis.get('low_score_cases', [])}

## タスク

上記のエラーを解消するために、スキル定義を改善してください。
改善点を明確にしつつ、更新後の完全なスキル定義を出力してください。

出力形式：
1. まず [UPDATES_START] と [UPDATES_END] で囲んで、行った改善点をリストアップしてください
2. 次に [SKILLS_START] と [SKILLS_END] で囲んで、更新後の完全なスキル定義を出力してください

重要：
- 既存の良い部分は維持すること
- エラーパターンに対する具体的な対策を追加すること
- 実践的なTerraformコード生成に役立つ情報を追加すること
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
        updates = [line.strip().lstrip("- ") for line in updates_text.split("\n") if line.strip()]
    
    # 更新後のスキルを抽出
    skills_start = content.find("[SKILLS_START]")
    skills_end = content.find("[SKILLS_END]")
    if skills_start != -1 and skills_end != -1:
        new_skills = content[skills_start + len("[SKILLS_START]"):skills_end].strip()
    else:
        # マーカーがない場合は現在のスキルを維持
        new_skills = current_skills
        updates.append("スキル更新なし（マーカーが見つかりませんでした）")
    
    return new_skills, updates


def save_skills(skills_content: str, skills_path: Path) -> None:
    """スキルファイルを保存"""
    skills_path.write_text(skills_content, encoding="utf-8")
    console.print(f"[green]✓[/green] Skills updated: {skills_path}")


def backup_skills(skills_path: Path, iteration: int) -> Path:
    """スキルファイルをバックアップ"""
    backup_path = skills_path.parent / f"{skills_path.stem}_backup_{iteration}{skills_path.suffix}"
    if skills_path.exists():
        backup_path.write_text(skills_path.read_text(encoding="utf-8"), encoding="utf-8")
        console.print(f"[blue]ℹ[/blue] Skills backed up: {backup_path}")
    return backup_path

