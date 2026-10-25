@echo off
REM Atualiza o painel publicado no GitHub Pages a partir da planilha consolidada.
REM 1) Coloque a nova versão em dados\HIGIENIZACAO_REDE_CONSOLIDADA.xlsx
REM 2) Confira se existe dados\.chave_site (a chave que cifra os dados; nunca vai para o GitHub).
REM 3) Dê dois cliques neste arquivo.
cd /d "%~dp0"
python scripts\gerar_dados_site.py dados\HIGIENIZACAO_REDE_CONSOLIDADA.xlsx || goto erro
git add docs\dados.js docs\index.html docs\acesso.js || goto erro
git commit -m "Atualiza dados do painel" || echo Nada novo para enviar.
git push || goto erro
echo.
echo Pronto. O site atualiza em 1 a 2 minutos.
pause
exit /b 0
:erro
echo.
echo Algo deu errado. Leia a mensagem acima.
pause
exit /b 1
