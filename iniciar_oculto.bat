@echo off
echo ====================================================
echo    Iniciando LetsFlyGo Analytics (Modo Oculto)
echo ====================================================
echo Executando varredura em segundo plano usando config/config.json...
echo Pode minimizar esta janela. Ela fechara sozinha ao concluir.
echo.
python rapidapi.py -noview config/config.json
