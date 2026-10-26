# Painel Higienização de Rede 2.0 — site estático (GitHub Pages)

Site só de visualização, alimentado pela planilha consolidada do projeto.
O acesso é por **usuário e senha**, e os dados são criptografados. O painel geral mostra números agregados. A aba **Potenciais a descredenciamento** lista os candidatos dos blocos C–F pelo **nome**. Ela não traz CPF/CNPJ, endereço, telefone nem valores.

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

## Login (usuário e senha)

O site abre numa tela de login. Todos os dados (`docs/dados.js`) ficam **criptografados com AES-256-GCM**: sem um usuário e senha válidos, ninguém consegue lê-los, nem baixando o repositório. A decifragem acontece só no navegador de quem entra.

**Como funciona:**
- **Chave do site:** fica em `dados\.chave_site` e **nunca vai para o GitHub**. Sem ela não é possível atualizar o site. Guarde uma cópia em local seguro.
- **Usuários e senhas:** cada usuário tem a chave do site protegida pela própria senha (PBKDF2-SHA256, 600 mil iterações), em `docs/acesso.js`. Os nomes de usuário ficam só como hash, e as senhas não são guardadas em lugar nenhum.
- **Sessão:** vale até fechar a aba do navegador ou clicar em **Sair**.

**Gerenciar usuários** (requer `pip install cryptography`):
```bat
python scripts\usuarios.py adicionar maria --gerar     (gera uma senha forte e mostra uma vez)
python scripts\usuarios.py adicionar joao              (você digita a senha, mínimo 10 caracteres)
python scripts\usuarios.py trocar guilherme
python scripts\usuarios.py remover maria
python scripts\usuarios.py listar
```
Depois de qualquer mudança, publique com `atualizar_site.bat`.

**Para cortar de vez o acesso de alguém** que possa ter guardado uma cópia antiga do site, rode `python scripts\usuarios.py nova-chave`. Depois recadastre os usuários e rode `atualizar_site.bat`.

**Limitações:**
- não há "esqueci a senha";
- não há registro de acessos;
- não há bloqueio por tentativas, por isso as senhas precisam ser fortes.

## Aba "Regras do projeto"

A aba lista as 20 regras de escopo e de decisão, na ordem em que são aplicadas, e mostra quantos prestadores cada uma afeta. O link direto é `.../#regras`. As regras estão organizadas em seis grupos:
1. **Fora do escopo:** enfermeiros e derivados, médico regulador, rede própria Ipasgo, registros técnicos e registros sem CPF/CNPJ.
2. **Protegidos:** quem faturou em 12 meses, quem foi credenciado há menos de 1 ano e quem está em só uma base cadastral.
3. **Candidatos e blocos:** C (rede suficiente), D (rede mínima), E (único na localidade) e F (efeito cumulativo).
4. **Normas:** RN 567, RN 585, RN 566 e Lei 13.003.
5. **Tratamento dos dados:** normalização de CPF/CNPJ, categoria oficial do BI CODER e score.
6. **Regras da 1ª higienização ainda pendentes de base:** solicitações e execuções de serviços.

Os textos e as contagens são gerados em `scripts/gerar_dados_site.py` (função `regras_do_projeto`). A regra em si é aplicada em `scripts/gerar_consolidado.py`. Ao mudar uma regra, atualize os dois arquivos.

## Aba "Potenciais a descredenciamento"

A aba lista os candidatos dos blocos C–F. Para cada um, mostra:
- prestador, categoria, especialidade e município;
- bloco e score;
- motivo, ação recomendada, norma aplicável e composição do score.

Na tela, é possível:
- filtrar por nome, categoria, especialidade, região, município e bloco;
- ordenar clicando no título de cada coluna;
- baixar a lista filtrada em CSV.

O link direto para a aba é `.../#candidatos`.

**Especialidade médica.** As bases atuais não têm esse campo. Para preenchê-lo, siga estes passos:
1. Salve `dados\especialidades.csv` com duas colunas separadas por `;`: `CPF_CNPJ;ESPECIALIDADE`. Use uma linha por especialidade; quem tiver mais de uma aparece como "A; B".
2. Rode `atualizar_site.bat`.

O arquivo fica fora do git. Só a especialidade vai para o site, ligada ao nome.

## Mapa da rede e RN 566/2022

O mapa cobre Goiás (246 municípios, 18 regiões de saúde da SES-GO) e o DF. Ele tem dois modos:

**Camadas:** municípios ou regiões de saúde. Na camada de regiões, clicar numa região filtra o painel inteiro por ela.

**Indicadores:**
- Mapa de calor de prestadores na rede, de prestadores que faturam ou de candidatos C–F.
- **Cobertura RN 566** de hoje e após descredenciar os candidatos C–F, por categoria. Cada município recebe um nível:
  1. no município;
  2. só em limítrofe;
  3. só na região de saúde, com transporte custeado;
  4. fora da região, com transporte de ida e volta;
  5. sem rede em GO/DF.
- **Impacto:** destaca os municípios onde a cobertura piora e lista as categorias mais afetadas.

Ao clicar num município, aparecem a região, os limítrofes com rede, o nível em três lentes (hoje, após o descredenciamento e só a rede que fatura) e um alerta quando o descredenciamento piora a garantia.

A base geográfica fica em `scripts/` e só precisa ser refeita se mudar a malha ou as regiões:
```bat
pip install shapely
python scripts\preparar_mapa.py
```
Esse comando gera `scripts/base_geografica.json`, com região e limítrofes, e `docs/mapa.js`, com os contornos.

**Fontes:**
- Malha municipal do IBGE, obtida via github.com/tbrugz/geodata-br. A geometria inválida de Mineiros e Sítio d'Abadia foi corrigida.
- Regiões de saúde: SES-GO (goias.gov.br/saude/regioes-de-saude-planejamento).

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

O computador precisa ter Python com `pandas` e `openpyxl` (`pip install pandas openpyxl cryptography`) e o Git configurado com acesso ao repositório.

Para gerar a planilha a partir das 3 bases (faturamento, FACIL e BI CODER), rode:
```bat
python scripts\gerar_consolidado.py --faturamento FAT.csv --facil FACIL.csv --coder CODER.xlsx --saida dados\HIGIENIZACAO_REDE_CONSOLIDADA.xlsx --data-ref 2026-09-18
```

## Marca "Em construção"

Enquanto as bases definitivas de credenciamento e faturamento não chegam, o site mostra três sinais de versão de teste:
- uma marca d'água diagonal, "EM CONSTRUÇÃO · VERSÃO DE TESTE · DADOS PRELIMINARES";
- um selo no título;
- uma faixa listrada abaixo do cabeçalho.

Para a versão final, apague em `docs/index.html`:
- o bloco de estilos que começa em `/* ---- marca d'água`;
- as linhas `<div class="faixa-construcao">` e `<div class="marca-construcao">`;
- o `<span class="selo-construcao">`;
- o prefixo `[EM CONSTRUÇÃO]` do `<title>`.

## Ver localmente

Abra `docs/index.html` no navegador. Funciona sem servidor.

## Limitações

- **O repositório é público, mas os dados vão criptografados.** O que fica legível é só o código da página, a malha do mapa (dados públicos do IBGE) e os hashes de acesso. Versões publicadas antes do login (até o commit `42f9c79`) continuam no histórico do Git, até ele ser reescrito.
- A tabela de municípios não cruza com categoria nem com bloco, por proteção.
- O mapa de cobertura mostra o **nível** por município × categoria, sem contagens. Ainda assim, quem conhece a rede local pode deduzir onde há candidatos. Avalie isso antes de divulgar o link.
- A cobertura é medida por categoria do BI CODER, sem especialidade médica, e não considera prestadores fora da rede nem prazos de atendimento.
- O mapa cobre só GO e DF. Prestadores de outras UFs ficam fora dele.
- A atualização depende de rodar o `atualizar_site.bat` num computador com a planilha.
