"""WebUI for Terraform generation"""
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from anthropic import Anthropic

from .runner import load_skills, generate_terraform

load_dotenv()

app = FastAPI(title="Terraform Generator", description="Claude Skills-based Terraform Generator")

BASE_DIR = Path(__file__).parent.parent
SKILLS_DIR = BASE_DIR / "skills"


class GenerateRequest(BaseModel):
    request: str


class GenerateResponse(BaseModel):
    success: bool
    main_tf: str = ""
    variables_tf: str = ""
    outputs_tf: str = ""
    providers_tf: str = ""
    error: str = ""


@app.get("/", response_class=HTMLResponse)
async def index():
    return """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terraform Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #FFFFFF;
            color: #1A1A1A;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 60px 24px;
        }
        
        header {
            margin-bottom: 48px;
        }
        
        h1 {
            font-size: 28px;
            font-weight: 400;
            color: #1A1A1A;
            margin-bottom: 8px;
        }
        
        .subtitle {
            font-size: 14px;
            color: #6B7280;
        }
        
        .input-section {
            margin-bottom: 48px;
        }
        
        label {
            display: block;
            font-size: 13px;
            color: #6B7280;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        textarea {
            width: 100%;
            min-height: 120px;
            padding: 16px;
            border: 1px solid #E5E7EB;
            border-radius: 4px;
            font-size: 15px;
            font-family: inherit;
            resize: vertical;
            transition: border-color 0.2s;
        }
        
        textarea:focus {
            outline: none;
            border-color: #6B7280;
        }
        
        button {
            padding: 12px 32px;
            background-color: #1A1A1A;
            color: #FFFFFF;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            cursor: pointer;
            transition: background-color 0.2s;
            margin-top: 16px;
        }
        
        button:hover {
            background-color: #333333;
        }
        
        button:disabled {
            background-color: #9CA3AF;
            cursor: not-allowed;
        }
        
        .output-section {
            display: none;
        }
        
        .output-section.visible {
            display: block;
        }
        
        .output-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid #E5E7EB;
        }
        
        .output-header h2 {
            font-size: 18px;
            font-weight: 400;
        }
        
        .tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 24px;
            border-bottom: 1px solid #E5E7EB;
        }
        
        .tab {
            padding: 12px 20px;
            background: none;
            border: none;
            font-size: 14px;
            color: #6B7280;
            cursor: pointer;
            position: relative;
            margin: 0;
        }
        
        .tab.active {
            color: #1A1A1A;
        }
        
        .tab.active::after {
            content: '';
            position: absolute;
            bottom: -1px;
            left: 0;
            right: 0;
            height: 2px;
            background-color: #1A1A1A;
        }
        
        .code-container {
            background-color: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 4px;
            overflow: hidden;
        }
        
        .code-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background-color: #F3F4F6;
            border-bottom: 1px solid #E5E7EB;
        }
        
        .code-header span {
            font-size: 13px;
            color: #6B7280;
        }
        
        .copy-btn {
            padding: 6px 12px;
            font-size: 12px;
            background-color: #FFFFFF;
            color: #1A1A1A;
            border: 1px solid #E5E7EB;
            margin: 0;
        }
        
        .copy-btn:hover {
            background-color: #F9FAFB;
        }
        
        pre {
            padding: 20px;
            overflow-x: auto;
            font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            line-height: 1.5;
            margin: 0;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
            color: #6B7280;
        }
        
        .loading.visible {
            display: block;
        }
        
        .error {
            padding: 16px;
            background-color: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 4px;
            color: #991B1B;
            margin-bottom: 24px;
            display: none;
        }
        
        .error.visible {
            display: block;
        }
        
        .status {
            font-size: 12px;
            color: #6B7280;
            margin-top: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Terraform Generator</h1>
            <p class="subtitle">Claude Skillsを使用してAWSインフラのTerraformコードを生成</p>
        </header>
        
        <section class="input-section">
            <label for="request">要望を入力</label>
            <textarea id="request" placeholder="例: 高可用性のWebアプリケーション基盤を構築したい。ALBで負荷分散し、EC2をAuto Scalingで配置、RDSはMulti-AZで冗長化。"></textarea>
            <button id="generate-btn" onclick="generateTerraform()">Terraform生成</button>
            <p class="status" id="status"></p>
        </section>
        
        <div class="error" id="error"></div>
        
        <div class="loading" id="loading">
            <p>生成中...</p>
        </div>
        
        <section class="output-section" id="output-section">
            <div class="output-header">
                <h2>生成結果</h2>
            </div>
            
            <div class="tabs">
                <button class="tab active" data-tab="main">main.tf</button>
                <button class="tab" data-tab="variables">variables.tf</button>
                <button class="tab" data-tab="outputs">outputs.tf</button>
                <button class="tab" data-tab="providers">providers.tf</button>
            </div>
            
            <div class="tab-content active" id="tab-main">
                <div class="code-container">
                    <div class="code-header">
                        <span>main.tf</span>
                        <button class="copy-btn" onclick="copyCode('main')">コピー</button>
                    </div>
                    <pre id="code-main"></pre>
                </div>
            </div>
            
            <div class="tab-content" id="tab-variables">
                <div class="code-container">
                    <div class="code-header">
                        <span>variables.tf</span>
                        <button class="copy-btn" onclick="copyCode('variables')">コピー</button>
                    </div>
                    <pre id="code-variables"></pre>
                </div>
            </div>
            
            <div class="tab-content" id="tab-outputs">
                <div class="code-container">
                    <div class="code-header">
                        <span>outputs.tf</span>
                        <button class="copy-btn" onclick="copyCode('outputs')">コピー</button>
                    </div>
                    <pre id="code-outputs"></pre>
                </div>
            </div>
            
            <div class="tab-content" id="tab-providers">
                <div class="code-container">
                    <div class="code-header">
                        <span>providers.tf</span>
                        <button class="copy-btn" onclick="copyCode('providers')">コピー</button>
                    </div>
                    <pre id="code-providers"></pre>
                </div>
            </div>
        </section>
    </div>
    
    <script>
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                
                tab.classList.add('active');
                document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
            });
        });
        
        async function generateTerraform() {
            const request = document.getElementById('request').value.trim();
            if (!request) {
                showError('要望を入力してください');
                return;
            }
            
            const btn = document.getElementById('generate-btn');
            const loading = document.getElementById('loading');
            const output = document.getElementById('output-section');
            const error = document.getElementById('error');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            loading.classList.add('visible');
            output.classList.remove('visible');
            error.classList.remove('visible');
            status.textContent = '';
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ request })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('code-main').textContent = data.main_tf;
                    document.getElementById('code-variables').textContent = data.variables_tf;
                    document.getElementById('code-outputs').textContent = data.outputs_tf;
                    document.getElementById('code-providers').textContent = data.providers_tf;
                    output.classList.add('visible');
                    status.textContent = '生成完了';
                } else {
                    showError(data.error || '生成に失敗しました');
                }
            } catch (e) {
                showError('エラーが発生しました: ' + e.message);
            } finally {
                btn.disabled = false;
                loading.classList.remove('visible');
            }
        }
        
        function showError(message) {
            const error = document.getElementById('error');
            error.textContent = message;
            error.classList.add('visible');
        }
        
        function copyCode(type) {
            const code = document.getElementById('code-' + type).textContent;
            navigator.clipboard.writeText(code).then(() => {
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = 'コピー完了';
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 1500);
            });
        }
    </script>
</body>
</html>"""


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return GenerateResponse(success=False, error="ANTHROPIC_API_KEY not set")
        
        client = Anthropic(api_key=api_key)
        skills_path = SKILLS_DIR / "terraform-aws.md"
        
        if not skills_path.exists():
            return GenerateResponse(success=False, error="Skills file not found")
        
        skills = load_skills(skills_path)
        terraform_files = generate_terraform(client, req.request, skills)
        
        return GenerateResponse(
            success=True,
            main_tf=terraform_files.get("main_tf", ""),
            variables_tf=terraform_files.get("variables_tf", ""),
            outputs_tf=terraform_files.get("outputs_tf", ""),
            providers_tf=terraform_files.get("providers_tf", "")
        )
    except Exception as e:
        return GenerateResponse(success=False, error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

