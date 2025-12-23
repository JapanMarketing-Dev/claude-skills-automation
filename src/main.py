"""メインエントリーポイント"""
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .models import TrainingData, TerraformFiles, TuningIteration
from .runner import load_skills, generate_terraform, save_terraform_files
from .evaluator import evaluate
from .skills_updater import (
    analyze_errors,
    generate_skills_update,
    save_skills,
    backup_skills
)

console = Console()

# パス設定
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "training"
SKILLS_DIR = BASE_DIR / "skills"
OUTPUT_DIR = BASE_DIR / "output"
RESULTS_DIR = BASE_DIR / "results"


def load_training_data() -> list[TrainingData]:
    """学習データを読み込む"""
    data_list = []
    for json_file in sorted(DATA_DIR.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
            terraform_files = TerraformFiles(
                main_tf=raw["terraform_files"]["main_tf"],
                variables_tf=raw["terraform_files"]["variables_tf"],
                outputs_tf=raw["terraform_files"]["outputs_tf"],
                providers_tf=raw["terraform_files"]["providers_tf"]
            )
            data = TrainingData(
                id=raw["id"],
                source=raw["source"],
                request=raw["request"],
                terraform_files=terraform_files,
                tags=raw["tags"]
            )
            data_list.append(data)
    return data_list


def run_single_evaluation(
    client: Anthropic,
    data: TrainingData,
    skills: str,
    iteration: int
) -> tuple[dict[str, str], any]:
    """単一データに対する評価を実行"""
    # 出力ディレクトリ
    output_subdir = OUTPUT_DIR / f"iter_{iteration}" / data.id
    
    # Terraform生成
    generated = generate_terraform(client, data.request, skills)
    
    # ファイル保存
    save_terraform_files(generated, output_subdir)
    
    # 評価
    result = evaluate(data.id, generated, data.terraform_files, output_subdir)
    
    return generated, result


def print_results_table(results: list) -> None:
    """結果をテーブル表示"""
    table = Table(title="Evaluation Results")
    table.add_column("Data ID", style="cyan")
    table.add_column("Validate", style="green")
    table.add_column("Resource Match", justify="right")
    table.add_column("Config Match", justify="right")
    table.add_column("Overall Score", justify="right", style="bold")
    
    for result in results:
        validate_icon = "✓" if result.validate_passed else "✗"
        validate_style = "green" if result.validate_passed else "red"
        
        table.add_row(
            result.data_id,
            f"[{validate_style}]{validate_icon}[/{validate_style}]",
            f"{result.resource_match_rate:.2%}",
            f"{result.config_match_rate:.2%}",
            f"{result.overall_score:.2%}"
        )
    
    console.print(table)


def save_iteration_results(iteration_result: TuningIteration) -> None:
    """イテレーション結果を保存"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = RESULTS_DIR / f"iteration_{iteration_result.iteration}_{timestamp}.json"
    
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(iteration_result.model_dump(), f, indent=2, ensure_ascii=False)
    
    console.print(f"[blue]ℹ[/blue] Results saved: {result_file}")


def run_tuning_loop(
    max_iterations: int = 5,
    target_score: float = 0.85
) -> None:
    """
    チューニングループを実行
    
    Args:
        max_iterations: 最大イテレーション回数
        target_score: 目標スコア
    """
    load_dotenv()
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        return
    
    client = Anthropic(api_key=api_key)
    
    # 学習データ読み込み
    training_data = load_training_data()
    console.print(f"[blue]ℹ[/blue] Loaded {len(training_data)} training data")
    
    # スキルファイルパス
    skills_path = SKILLS_DIR / "terraform-aws.md"
    
    for iteration in range(1, max_iterations + 1):
        console.print(f"\n[bold cyan]===== Iteration {iteration} =====[/bold cyan]")
        
        # スキル読み込み
        skills = load_skills(skills_path)
        
        # 各データで評価
        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Evaluating...", total=len(training_data))
            
            for data in training_data:
                progress.update(task, description=f"Evaluating {data.id}...")
                _, result = run_single_evaluation(client, data, skills, iteration)
                results.append(result)
                progress.advance(task)
        
        # 結果表示
        print_results_table(results)
        
        # スコア計算
        avg_score = sum(r.overall_score for r in results) / len(results)
        validate_pass_rate = sum(1 for r in results if r.validate_passed) / len(results)
        
        console.print(f"\n[bold]Average Score: {avg_score:.2%}[/bold]")
        console.print(f"[bold]Validate Pass Rate: {validate_pass_rate:.2%}[/bold]")
        
        # 目標達成チェック
        if avg_score >= target_score and validate_pass_rate >= 0.9:
            console.print(f"\n[green bold]✓ Target achieved! Stopping tuning.[/green bold]")
            break
        
        # エラー分析とスキル更新
        if iteration < max_iterations:
            console.print("\n[yellow]Analyzing errors and updating skills...[/yellow]")
            
            # バックアップ
            backup_skills(skills_path, iteration)
            
            # エラー分析
            error_analysis = analyze_errors(results)
            
            # スキル更新
            new_skills, updates = generate_skills_update(client, skills, error_analysis)
            
            # 更新内容表示
            console.print("\n[bold]Skills Updates:[/bold]")
            for update in updates:
                console.print(f"  • {update}")
            
            # 保存
            save_skills(new_skills, skills_path)
            
            # イテレーション結果保存
            iteration_result = TuningIteration(
                iteration=iteration,
                avg_score=avg_score,
                validate_pass_rate=validate_pass_rate,
                results=results,
                skills_updates=updates
            )
            save_iteration_results(iteration_result)
    
    console.print("\n[bold green]Tuning completed![/bold green]")


if __name__ == "__main__":
    run_tuning_loop()

