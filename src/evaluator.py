"""Terraform出力の評価ロジック"""
import subprocess
import re
from pathlib import Path
from difflib import SequenceMatcher
from rich.console import Console
from .models import EvaluationResult, TerraformFiles

console = Console()


def run_terraform_validate(terraform_dir: Path) -> tuple[bool, str]:
    """
    terraform validateを実行
    
    Returns:
        tuple: (成功したか, エラーメッセージ)
    """
    try:
        # terraform init
        init_result = subprocess.run(
            ["terraform", "init", "-backend=false"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if init_result.returncode != 0:
            return False, f"terraform init failed: {init_result.stderr}"
        
        # terraform validate
        validate_result = subprocess.run(
            ["terraform", "validate"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if validate_result.returncode != 0:
            return False, validate_result.stderr
        
        return True, ""
    
    except subprocess.TimeoutExpired:
        return False, "Terraform command timed out"
    except FileNotFoundError:
        return False, "Terraform not found"
    except Exception as e:
        return False, str(e)


def extract_resources(terraform_code: str) -> set[str]:
    """Terraformコードからリソースタイプを抽出"""
    pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
    matches = re.findall(pattern, terraform_code)
    return {f"{m[0]}.{m[1]}" for m in matches}


def extract_data_sources(terraform_code: str) -> set[str]:
    """Terraformコードからデータソースを抽出"""
    pattern = r'data\s+"([^"]+)"\s+"([^"]+)"'
    matches = re.findall(pattern, terraform_code)
    return {f"data.{m[0]}.{m[1]}" for m in matches}


def calculate_resource_match_rate(
    generated: dict[str, str],
    expected: TerraformFiles
) -> float:
    """リソース一致率を計算"""
    gen_resources = extract_resources(generated.get("main_tf", ""))
    exp_resources = extract_resources(expected.main_tf)
    
    if not exp_resources:
        return 1.0 if not gen_resources else 0.5
    
    # リソースタイプのみで比較（名前は無視）
    gen_types = {r.split(".")[0] for r in gen_resources}
    exp_types = {r.split(".")[0] for r in exp_resources}
    
    if not exp_types:
        return 1.0
    
    intersection = gen_types & exp_types
    union = gen_types | exp_types
    
    return len(intersection) / len(union) if union else 1.0


def calculate_config_match_rate(
    generated: dict[str, str],
    expected: TerraformFiles
) -> float:
    """設定の類似度を計算（テキストベース）"""
    gen_main = generated.get("main_tf", "")
    exp_main = expected.main_tf
    
    # 空白を正規化
    gen_normalized = " ".join(gen_main.split())
    exp_normalized = " ".join(exp_main.split())
    
    return SequenceMatcher(None, gen_normalized, exp_normalized).ratio()


def find_missing_resources(
    generated: dict[str, str],
    expected: TerraformFiles
) -> list[str]:
    """不足しているリソースを検出"""
    gen_types = {r.split(".")[0] for r in extract_resources(generated.get("main_tf", ""))}
    exp_types = {r.split(".")[0] for r in extract_resources(expected.main_tf)}
    
    missing = exp_types - gen_types
    return list(missing)


def find_extra_resources(
    generated: dict[str, str],
    expected: TerraformFiles
) -> list[str]:
    """余分なリソースを検出"""
    gen_types = {r.split(".")[0] for r in extract_resources(generated.get("main_tf", ""))}
    exp_types = {r.split(".")[0] for r in extract_resources(expected.main_tf)}
    
    extra = gen_types - exp_types
    return list(extra)


def evaluate(
    data_id: str,
    generated: dict[str, str],
    expected: TerraformFiles,
    terraform_dir: Path
) -> EvaluationResult:
    """
    生成されたTerraformを評価
    
    Args:
        data_id: データID
        generated: 生成されたTerraformファイル
        expected: 期待されるTerraformファイル
        terraform_dir: Terraformファイルが保存されたディレクトリ
    
    Returns:
        EvaluationResult: 評価結果
    """
    errors = []
    
    # terraform validate
    validate_passed, validate_error = run_terraform_validate(terraform_dir)
    if not validate_passed:
        errors.append(f"Validation failed: {validate_error}")
    
    # リソース一致率
    resource_match_rate = calculate_resource_match_rate(generated, expected)
    
    # 設定一致率
    config_match_rate = calculate_config_match_rate(generated, expected)
    
    # 不足・余分なリソース
    missing = find_missing_resources(generated, expected)
    if missing:
        errors.append(f"Missing resources: {', '.join(missing)}")
    
    extra = find_extra_resources(generated, expected)
    if extra:
        errors.append(f"Extra resources: {', '.join(extra)}")
    
    # 総合スコア計算
    # validate: 30%, resource_match: 40%, config_match: 30%
    validate_score = 1.0 if validate_passed else 0.0
    overall_score = (
        validate_score * 0.3 +
        resource_match_rate * 0.4 +
        config_match_rate * 0.3
    )
    
    return EvaluationResult(
        data_id=data_id,
        validate_passed=validate_passed,
        validate_error=validate_error if not validate_passed else None,
        resource_match_rate=resource_match_rate,
        config_match_rate=config_match_rate,
        overall_score=overall_score,
        errors=errors
    )

