# ✈️ LetsFlyGo Analytics
**O Raio-X Completo do Sistema de Monitoramento Preditivo de Passagens Aéreas**

O **LetsFlyGo** é um poderoso sistema de extração, histórico e monitoramento preditivo de preços de passagens aéreas. Construído sobre uma arquitetura enxuta baseada em Python (Flask) e JavaScript (Tailwind, Chart.js, SQL.js), o sistema varre a malha aérea buscando os menores preços com um horizonte anual (365 dias), agregando inteligência de dados ao longo do tempo.

Este documento serve como a "caixa preta" do software, destrinchando suas mecânicas visíveis e invisíveis.

---

## ⚙️ 1. Como os JSONs Funcionam na Arquitetura

Para garantir uma interface que se adapta facilmente e automatizar o sistema, dois arquivos de configuração JSON regem o LetsFlyGo dentro da pasta `config/`:

### A) `config/destinos.json`
Este arquivo é o **coração geográfico** do seu programa. Ele foi criado para remover completamente informações fixas de aeroportos (hardcoded) do código-fonte.
* **Mapeamento de Botões:** Na tela inicial (`http://localhost:5000/`), o Python lê as chaves (ex: `top_50_brasil`, `america_latina`, `nordeste`) e cria os "botões de atalho" (presets). O botão recebe o nome da chave e injeta as siglas IATA automaticamente no formulário.
* **Mapeamento Cidades:** No painel analítico (Dashboard), ao invés de exibir rotas frias como "POA ➔ MVD", o sistema lê a propriedade `"cidade"` atrelada ao `"iata"` (ex: "Porto Alegre ➔ Montevidéu").
* **Regra Oculta:** O próprio código destaca automaticamente os botões cujas chaves se chamem `tudo` ou `top_50_brasil` com cores primárias na tela inicial para facilitar o acesso.

### B) `config/config.json`
É o **cérebro da automação**. Quando você usa a interface da web e clica em *"Salvar Config"*, o LetsFlyGo grava neste arquivo as siglas de origens e destinos informadas no campo de texto.
* **Benefício:** Evita digitar as rotas favoritas novamente a cada vez que o programa é aberto.
* **Oculto:** Ele é a *chave mestre* para o modo de automação via Command Line (explicado mais abaixo).

---

## 🧠 2. Mecânica do Desconto e Análise de Preço (Top 10)

A cada vez que você pesquisa uma rota, o sistema estampa no banco de dados (`passagens.db`) uma exata *timestamp* (`data_pesquisa`). Como ele calcula e exibe as quedas de preço (descontos)?

1. **Acréscimo de Histórico Total:** O Dashboard coleta o banco de dados e identifica TODOS os timestamps que você já gerou.
2. **Combinação Temporal:** Para cada combinação *Rota + Mês*, ele busca qual foi a **última** vez que aquela rota foi pesquisada e qual foi a **penúltima** vez.
3. **Cálculo de *Diff*:**
   > `Percentual = ((Preço Atual - Preço Anterior) / Preço Anterior) * 100`
   > *(Se esse percentual for negativo, significa que o preço caiu!)*
4. **Agrupamento Oculto de Datas:** Para um mesmo mês e mesmo "preço mínimo absoluto", a API pode retornar várias datas diferentes. O sistema captura todas essas ocorrências em um cofre oculto e, quando exposto no dashboard, te mostra apenas `x data(s)`. O clique gera os links no Modal.
5. **Destaque Visual do Menor Preço Absoluto:** Na matriz do Dashboard, o sistema faz uma varredura cruzada no eixo horizontal (em todos os meses). O mês que tiver a passagem mais barata dentre os 12 recebe um emblema verde "glowing" (`price-badge-green`), saltando aos olhos instantaneamente.

---

## 📄 3. Standalone HTML vs. Dashboard do Servidor

Muitas vezes você precisará fechar o servidor, mas ainda quer mandar o resultado para um cliente ou consultar os números do celular depois. É aqui que entra a diferença de design das exportações:

### 🖥️ Dashboard do Servidor (Modo Online via Flask)
* **Acesso:** `http://localhost:5000/dashboard`
* **Mecânica:** Altamente dinâmico. O navegador (graças ao `sql.js` WebAssembly) puxa o arquivo `passagens.db`, entra dentro dele e o analisa usando a RAM local.
* **Diferenciais:** Gráficos dinâmicos temporais de tendências (Chart.js), possibilidade de aplicar filtros em tempo real, e capacidade de injetar e analisar um `.db` antigo guardado na máquina via botão "Carregar".

### 💾 Standalone HTML (Snapshot Fixo)
* **Localização:** Gerado na pasta `/htmls/` no fim da pesquisa, ou via botão "Salvar HTML".
* **Mecânica:** É uma "foto morta" (estática) gerada pelo Python no backend. Todo o CSS, Tabelas e Dados estão embutidos (inline) em um único arquivo HTML.
* **Diferenciais:** Pode ser aberto por *qualquer aparelho do mundo* sem precisar de Python instalado ou servidor ativo. Os dias de voo não estão escondidos dentro de um Modal clicável, eles já são "links azuis" que redirecionam direto ao Google Flights.

---

## 📊 4. Mecânicas de Exportação (CSV e WhatsApp)

A plataforma conta com exportação relâmpago:

* 📱 **WhatsApp:** A mecânica de copiar texto (`navigator.clipboard`) cria uma versão Markdown limpa. Se houver 8 datas baratas em um único mês, ele condensa listando apenas os 3 primeiros dias e adicionando `...` para não estourar a tela do celular do recipiente.
* 📈 **Exportação CSV:** Lê os dados da RAM gerados pelo Dashboard e simula um clique virtual (`a.download`), jogando para o seu computador um arquivo `letsflygo_DATA.csv` instantâneo pronto para tabelas dinâmicas no Excel.

---

## 🤫 5. Mecânicas Ocultas (Limpezas e Segredos)

Dentro do motor em Python (o `rapidapi.py`), existem regras rodando silenciosamente:

1. **🧹 Auto-Clean de 10 Dias:** Sempre que a varredura inicia, o LetsFlyGo executa sorrateiramente: `DELETE FROM historico_voos WHERE data_pesquisa < datetime('now', '-10 days')`. Isso impede que o banco SQLite infle e estoure a memória do seu navegador. Para guardar históricos longos, baixe o CSV!
2. **📡 Event-Stream (SSE):** Na tela de carregamento animada, não há refresh da página. O Python e o Navegador mantêm uma conexão TCP aberta (`text/event-stream`), onde o servidor injeta textos `[TOTAL:x]` ou `[PROGRESSO:x/y]` em tempo real para pintar a barra de progresso.
3. **🔗 Carga Viva no Google Flights:** Os links gerados não perdem tempo com a API que forneceu os dados. O redirecionamento é construído cruamente para o Google: `q=Flights from POA to MVD on 2026-05-10`, enviando a transação diretamente para as vias principais de reserva.

---

## 🤖 6. Modo Automação (CLI / "Rodar Escondido")

Um recurso de nível avançado incluído é a capacidade de **usar o programa sem depender do seu mouse ou do navegador**, perfeito para agendamentos de madrugada.

**Comando Terminal / PowerShell:**
```bash
python rapidapi.py -noview config/config.json
```

**Como Funciona?**
1. O argumento `-noview` impede a abertura forçada da janela do navegador.
2. O segundo argumento (`config/config.json`) fornece a rota exata predefinida ao sistema.
3. A busca não passa pela página principal e joga o processamento pesadíssimo para uma *Thread* em segundo plano.
4. Ao final, a interface terminal avisa a conclusão, e seus relatórios são guardados nas pastas!

> **Dica Pro:** Utilize os arquivos `.bat` fornecidos (como o `iniciar_oculto.bat`) junto ao "Agendador de Tarefas do Windows" para rodar o motor invisivelmente todos os dias de madrugada!

---

## ☁️ 7. O Ecossistema Nuvem (GitHub Actions + Telegram)

Para levar a automação ao extremo e rodar sem nem precisar ligar o seu computador, o sistema agora conta com um isolamento completo para CI/CD através do **GitHub Actions**.

### Como Funciona:
1. **O Robô Isolado:** Há um motor de varredura específico criado em `telegram/rapidapi_github_actions.py`. Ele **não usa** interface Web (Flask) para economizar RAM do servidor da Microsoft.
2. **Cronograma:** Todos os dias às 13:30 (horário de Brasília), o `.github/workflows/telegram_flight_bot.yml` acorda o robô na nuvem.
3. **Memória Persistente:** O robô alimenta um banco SQLite exclusivo (`passagens_telegram.db`) e faz um auto-commit (`git push`) para dentro do seu próprio repositório GitHub, criando uma memória vitalícia das pesquisas passadas.
4. **Cálculo Matemático Instantâneo:** Ao finalizar a varredura, o Python levanta o Top 10 maiores descontos do dia vs. dia anterior e salva os resultados em texto (Markdown).
5. **A Entrega:** Usando a integração de bot (`appleboy/telegram-action`), ele envia diretamente para o seu grupo no Telegram o arquivo HTML Standalone novinho em folha, junto com as mensagens de desconto. 

> **Segurança:** O robô usa a chave secreta de API injetada diretamente via `Github Secrets` (`RAPIDAPI_KEY`), impedindo que o seu token vaze na internet caso o código seja público.
