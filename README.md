# Painel Higienização de Rede 2.0 — site estático (GitHub Pages)

Site só de visualização, alimentado pela planilha consolidada do projeto.
Mostra **apenas números agregados**: não há CPF/CNPJ, nome, endereço nem valor de prestador individual.

## Como funciona

```
dados/HIGIENIZACAO_REDE_CONSOLIDADA.xlsx   (fica só no seu computador; ignorado pelo git)
        │  scripts/gerar_dados_site.py
        ▼
docs/dados.js   (resumo agregado — é isto que vai para o GitHub)
docs/index.html (o painel)
```

Regras de proteção aplicadas em `gerar_dados_site.py`:
- **Contagens** são feitas por UF × região × categoria × bloco × classe de rede.
- **Municípios** aparecem só com totais, sem cruzar com categoria nem com bloco.
- **Valores em R$** aparecem só por bloco e por região, e somente para grupos com 3 ou mais prestadores.

## Publicar pela primeira vez

1. No GitHub, clique em **New repository** e dê um nome, por exemplo `painel-higienizacao`.
   - No plano gratuito, o GitHub Pages exige repositório **público**.
2. No computador, dentro desta pasta, rode:
   ```bat
   git init -b main
   git add .
   git commit -m "Painel Higienização de Rede 2.0"
   git remote add origin https://github.com/<usuario>/painel-higienizacao.git
   git push -u origin main
   ```
3. No repositório, vá em **Settings → Pages**. Em *Source*, escolha "Deploy from a branch". Em *Branch*, escolha `main` e a pasta `/docs`. Depois clique em **Save**.
4. Em 1 a 2 minutos o site fica em `https://<usuario>.github.io/painel-higienizacao/`.

## Atualizar os dados

1. Salve a nova planilha em `dados\HIGIENIZACAO_REDE_CONSOLIDADA.xlsx`. Ela precisa ter a aba `CONSOLIDADO`.
2. Dê dois cliques em `atualizar_site.bat`. Ele gera o resumo, faz o commit e envia ao GitHub.

O computador precisa ter Python com `pandas` e `openpyxl` (`pip install pandas openpyxl`) e o Git configurado com acesso ao repositório.

Para gerar a planilha a partir das 3 bases (faturamento, FACIL e BI CODER), rode:
```bat
python scripts\gerar_consolidado.py --faturamento FAT.csv --facil FACIL.csv --coder CODER.xlsx --saida dados\HIGIENIZACAO_REDE_CONSOLIDADA.xlsx --data-ref 2026-09-18
```

## Ver localmente

Abra `docs/index.html` no navegador. Funciona sem servidor.

## Limitações

- **O site e o repositório são públicos.** Qualquer pessoa com o link vê os números agregados. O site pede para não ser indexado por buscadores, mas não tem login.
- Não há lista nem detalhe de prestador. Para isso, use a planilha ou o painel Django (VRS 2).
- A tabela de municípios não cruza com categoria nem com bloco, por proteção.
- A atualização depende de rodar o `atualizar_site.bat` num computador com a planilha.
