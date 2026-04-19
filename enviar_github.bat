@echo off
chcp 65001 >nul
echo ====================================================
echo        Enviando versao para o GitHub (1 Clique)
echo ====================================================
echo.

if not exist ".git" (
    echo [INFO] Inicializando o repositorio pela primeira vez...
    git init
)

echo [INFO] Conectando ao repositorio passagensaereas...
git remote add origin https://github.com/tailerteilor/passagensaereas.git 2>nul

echo [INFO] Lendo arquivo github\version.json...
powershell -ExecutionPolicy Bypass -Command "$json = Get-Content -Raw -Encoding UTF8 'github\version.json' | ConvertFrom-Json; $commitMsg = 'v' + $json.version + ' - ' + $json.title; Write-Host '=> Subindo:' -ForegroundColor Yellow -NoNewline; Write-Host \" $commitMsg\" -ForegroundColor Cyan; git add .; git commit -m $commitMsg; git branch -M main; git push -u origin main"

echo.
echo ====================================================
echo      Tudo nas nuvens! Pressione algo para sair...
echo ====================================================
pause
