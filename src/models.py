"""データモデル定義"""
from pydantic import BaseModel
from typing import Optional


class TerraformFiles(BaseModel):
    """Terraformファイルセット"""
    main_tf: str
    variables_tf: str
    outputs_tf: str
    providers_tf: str


class TrainingData(BaseModel):
    """学習データ"""
    id: str
    source: str
    request: str  # ユーザーの依頼文
    terraform_files: TerraformFiles
    tags: list[str]


class EvaluationResult(BaseModel):
    """評価結果"""
    data_id: str
    validate_passed: bool
    validate_error: Optional[str] = None
    resource_match_rate: float  # 0.0 - 1.0
    config_match_rate: float  # 0.0 - 1.0
    overall_score: float  # 0.0 - 1.0
    errors: list[str]


class TuningIteration(BaseModel):
    """チューニングイテレーション結果"""
    iteration: int
    avg_score: float
    validate_pass_rate: float
    results: list[EvaluationResult]
    skills_updates: list[str]

