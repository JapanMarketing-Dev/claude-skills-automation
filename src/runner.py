"""Claude APIを使ってskillsを実行し、Terraformを生成"""
import os
from pathlib import Path
from anthropic import Anthropic
from rich.console import Console

console = Console()


def load_skills(skills_path: Path) -> str:
    """skillsファイルを読み込む"""
    return skills_path.read_text(encoding="utf-8")


def generate_terraform(
    client: Anthropic,
    request: str,
    skills: str,
    model: str = "claude-sonnet-4-20250514"
) -> dict[str, str]:
    """
    依頼文からTerraformコードを生成
    
    Returns:
        dict: main_tf, variables_tf, outputs_tf, providers_tf のキーを持つ辞書
    """
    system_prompt = f"""あなたはAWS Terraformの専門家です。以下のスキル定義に従って、ユーザーの依頼からTerraformコードを生成してください。

{skills}

## 出力形式

必ず以下の4つのセクションに分けて出力してください。各セクションは必ず指定のマーカーで囲んでください：

### main.tf
```terraform
[MAIN_TF_START]
... main.tf の内容 ...
[MAIN_TF_END]
```

### variables.tf
```terraform
[VARIABLES_TF_START]
... variables.tf の内容 ...
[VARIABLES_TF_END]
```

### outputs.tf
```terraform
[OUTPUTS_TF_START]
... outputs.tf の内容 ...
[OUTPUTS_TF_END]
```

### providers.tf
```terraform
[PROVIDERS_TF_START]
... providers.tf の内容 ...
[PROVIDERS_TF_END]
```

重要：
- 必ず動作するTerraformコードを出力すること
- terraform validateが通るコードであること
- AWSのベストプラクティスに従うこと
"""

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"以下の要望に基づいてTerraformコードを生成してください：\n\n{request}"}
        ]
    )

    content = response.content[0].text
    return parse_terraform_output(content)


def parse_terraform_output(content: str) -> dict[str, str]:
    """Claude出力からTerraformファイルを抽出"""
    result = {
        "main_tf": "",
        "variables_tf": "",
        "outputs_tf": "",
        "providers_tf": ""
    }
    
    # 各セクションを抽出
    markers = [
        ("main_tf", "[MAIN_TF_START]", "[MAIN_TF_END]"),
        ("variables_tf", "[VARIABLES_TF_START]", "[VARIABLES_TF_END]"),
        ("outputs_tf", "[OUTPUTS_TF_START]", "[OUTPUTS_TF_END]"),
        ("providers_tf", "[PROVIDERS_TF_START]", "[PROVIDERS_TF_END]"),
    ]
    
    for key, start_marker, end_marker in markers:
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            extracted = content[start_idx + len(start_marker):end_idx].strip()
            # コードブロックマーカーを除去
            extracted = extracted.replace("```terraform", "").replace("```hcl", "").replace("```", "").strip()
            result[key] = extracted
    
    return result


def save_terraform_files(terraform_files: dict[str, str], output_dir: Path) -> None:
    """Terraformファイルを保存"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    file_mapping = {
        "main_tf": "main.tf",
        "variables_tf": "variables.tf",
        "outputs_tf": "outputs.tf",
        "providers_tf": "providers.tf"
    }
    
    for key, filename in file_mapping.items():
        filepath = output_dir / filename
        filepath.write_text(terraform_files[key], encoding="utf-8")
        console.print(f"  [green]✓[/green] {filepath}")

