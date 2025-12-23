"""Terraform出力の評価ロジック（改善版）"""
import subprocess
import re
import json
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
            ["terraform", "validate", "-json"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        try:
            result_json = json.loads(validate_result.stdout)
            if result_json.get("valid", False):
                return True, ""
            else:
                errors = result_json.get("diagnostics", [])
                error_msgs = [e.get("summary", "") for e in errors if e.get("severity") == "error"]
                return False, "; ".join(error_msgs)
        except json.JSONDecodeError:
            if validate_result.returncode != 0:
                return False, validate_result.stderr
            return True, ""
    
    except subprocess.TimeoutExpired:
        return False, "Terraform command timed out"
    except FileNotFoundError:
        return False, "Terraform not found"
    except Exception as e:
        return False, str(e)


def run_tflint(terraform_dir: Path) -> tuple[int, list[str]]:
    """
    tflintを実行して静的解析
    
    Returns:
        tuple: (警告数, 警告メッセージリスト)
    """
    try:
        # tflint init
        subprocess.run(
            ["tflint", "--init"],
            cwd=terraform_dir,
            capture_output=True,
            timeout=60
        )
        
        # tflint実行
        result = subprocess.run(
            ["tflint", "--format=json"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        try:
            issues = json.loads(result.stdout)
            if isinstance(issues, dict):
                issues = issues.get("issues", [])
            warnings = [f"{i.get('rule', {}).get('name', 'unknown')}: {i.get('message', '')}" 
                       for i in issues]
            return len(warnings), warnings
        except json.JSONDecodeError:
            return 0, []
    
    except subprocess.TimeoutExpired:
        return 0, ["tflint timed out"]
    except FileNotFoundError:
        return 0, []  # tflintがない場合はスキップ
    except Exception as e:
        return 0, [str(e)]


def extract_resources(terraform_code: str) -> set[str]:
    """Terraformコードからリソースタイプを抽出"""
    pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
    matches = re.findall(pattern, terraform_code)
    return {m[0] for m in matches}  # リソースタイプのみ


def extract_resource_names(terraform_code: str) -> set[str]:
    """Terraformコードからリソース名（タイプ.名前）を抽出"""
    pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
    matches = re.findall(pattern, terraform_code)
    return {f"{m[0]}.{m[1]}" for m in matches}


def extract_data_sources(terraform_code: str) -> set[str]:
    """Terraformコードからデータソースを抽出"""
    pattern = r'data\s+"([^"]+)"\s+"([^"]+)"'
    matches = re.findall(pattern, terraform_code)
    return {m[0] for m in matches}


def calculate_resource_match_rate(
    generated: dict[str, str],
    expected: TerraformFiles
) -> tuple[float, list[str], list[str]]:
    """
    リソース一致率を計算（改善版）
    
    Returns:
        tuple: (一致率, 不足リソース, 余分リソース)
    """
    gen_types = extract_resources(generated.get("main_tf", ""))
    exp_types = extract_resources(expected.main_tf)
    
    if not exp_types:
        return 1.0 if not gen_types else 0.5, [], list(gen_types)
    
    # 一致しているリソース
    matched = gen_types & exp_types
    missing = list(exp_types - gen_types)
    extra = list(gen_types - exp_types)
    
    # Jaccard係数で計算
    union = gen_types | exp_types
    if not union:
        return 1.0, [], []
    
    rate = len(matched) / len(union)
    return rate, missing, extra


def calculate_config_similarity(
    generated: dict[str, str],
    expected: TerraformFiles
) -> float:
    """設定の類似度を計算（改善版）"""
    gen_main = generated.get("main_tf", "")
    exp_main = expected.main_tf
    
    # 空白・改行を正規化
    gen_normalized = " ".join(gen_main.split())
    exp_normalized = " ".join(exp_main.split())
    
    # 変数名などの違いを吸収するため、リソース構造を比較
    gen_resources = extract_resource_names(gen_main)
    exp_resources = extract_resource_names(exp_main)
    
    # リソース構造の類似度
    if gen_resources or exp_resources:
        structure_sim = len(gen_resources & exp_resources) / max(len(gen_resources | exp_resources), 1)
    else:
        structure_sim = 0.5
    
    # テキスト類似度
    text_sim = SequenceMatcher(None, gen_normalized, exp_normalized).ratio()
    
    # 構造を重視（70%）、テキストは参考程度（30%）
    return structure_sim * 0.7 + text_sim * 0.3


def evaluate(
    data_id: str,
    generated: dict[str, str],
    expected: TerraformFiles,
    terraform_dir: Path
) -> EvaluationResult:
    """
    生成されたTerraformを評価（改善版）
    
    スコア計算：
    - validate通過: 必須条件（通過しないと0点）
    - リソース一致率: 50%
    - 設定類似度: 30%
    - tflint警告なし: 20%
    """
    errors = []
    
    # 1. terraform validate（必須）
    validate_passed, validate_error = run_terraform_validate(terraform_dir)
    if not validate_passed:
        errors.append(f"Validation failed: {validate_error}")
    
    # 2. tflint静的解析
    tflint_warnings, tflint_messages = run_tflint(terraform_dir)
    if tflint_warnings > 0:
        errors.extend([f"tflint: {msg}" for msg in tflint_messages[:3]])  # 最大3件
    
    # 3. リソース一致率
    resource_match_rate, missing, extra = calculate_resource_match_rate(generated, expected)
    if missing:
        errors.append(f"Missing resources: {', '.join(missing)}")
    if extra:
        errors.append(f"Extra resources: {', '.join(extra)}")
    
    # 4. 設定類似度
    config_match_rate = calculate_config_similarity(generated, expected)
    
    # 5. 総合スコア計算
    if not validate_passed:
        # validateが通らない場合は大幅減点（最大30点）
        overall_score = (resource_match_rate * 0.2 + config_match_rate * 0.1)
    else:
        # tflintスコア（警告0なら1.0、警告が増えると減点）
        tflint_score = max(0, 1.0 - (tflint_warnings * 0.1))
        
        # 総合スコア
        # validate通過: 必須
        # リソース一致: 50%
        # 設定類似度: 30%
        # tflint: 20%
        overall_score = (
            resource_match_rate * 0.5 +
            config_match_rate * 0.3 +
            tflint_score * 0.2
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
