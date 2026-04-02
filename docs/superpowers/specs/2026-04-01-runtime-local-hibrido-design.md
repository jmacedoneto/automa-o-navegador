# Runtime Local Hibrido Design

## Contexto

O projeto atual mistura painel, gravacao, execucao, IA, Browserless e integracoes no mesmo fluxo operacional. O problema principal nao e um bug pontual: a arquitetura base do gravador depende de uma representacao remota por screenshot/WebSocket, o que impede interacao confiavel com o navegador e torna a geracao de passos e a execucao hibrida instaveis.

O objetivo da reestruturacao e transformar o produto em uma plataforma de automacao web com:

- gravacao de passos em uma janela real do Chrome;
- execucao manual, agendada e por webhook;
- motor hibrido com roteiro base + fallback por IA;
- outputs para webhook e planilha;
- pausa para intervencao humana quando o fallback falhar.

## Objetivo Da Primeira Versao

Entregar uma V1 funcional para dois cenarios de ponta a ponta:

- operar sistemas web: login, navegacao por menus, preenchimento de formularios, clique em botoes e validacao de retorno;
- capturar leads ou dados: navegar, extrair informacoes, baixar arquivos quando necessario, consolidar resultado e enviar para webhook ou planilha.

Essa V1 deve priorizar dois modos de produto:

- gravador em Chrome real controlado;
- executor hibrido.

Os modos `gravado puro` e `livre por IA` permanecem no desenho da plataforma, mas nao sao o foco da primeira fatia de implementacao.

## Abordagens Consideradas

### 1. Corrigir a base atual por cima

Manter React + FastAPI + Browserless como centro de gravacao e execucao e melhorar seletores, captura de eventos e IA.

Vantagens:

- menor volume inicial de mudanca;
- reaproveitamento direto de partes do backend atual.

Desvantagens:

- o defeito estrutural continua: o usuario nao opera um Chrome real;
- a confiabilidade do gravador segue limitada por screenshot, overlay e traducao de eventos;
- o executor hibrido fica preso a uma base fragil.

### 2. Arquitetura local-first com runtime local

Separar painel, API e motor de navegador. O painel continua web, a API orquestra, e um runtime local abre e controla um Chrome real.

Vantagens:

- resolve o requisito central de uso em janela real do Chrome;
- cria fronteiras claras entre UI, orquestracao e execucao;
- suporta gravacao, execucao hibrida, webhook e agendamento no mesmo desenho.

Desvantagens:

- exige criar um novo componente local;
- aumenta o trabalho de instalacao e operacao do produto.

### 3. Extensao-first

Fazer da extensao do Chrome o nucleo de gravacao e de parte da execucao.

Vantagens:

- gravacao em aba real;
- baixa friccao para certas capturas de eventos.

Desvantagens:

- pior acoplamento para agendamento, downloads, uploads e execucao fora da aba interativa;
- complexidade maior para fluxos hibridos e automacao robusta.

## Decisao

Adotar a abordagem 2: arquitetura local-first com runtime local.

Essa abordagem atende melhor aos requisitos aprovados:

- o gravador passa a abrir uma janela real do Chrome;
- a aplicacao deixa de embutir navegador como experiencia principal;
- o executor hibrido passa a operar em um motor proprio;
- webhook, agendamento e execucao manual convergem para o mesmo pipeline.

## Arquitetura Alvo

### 1. Painel Web

Responsabilidades:

- criar, editar e duplicar automacoes;
- iniciar gravacao;
- revisar e ajustar passos;
- configurar variaveis, outputs, webhook e agendamentos;
- visualizar logs, evidencias, falhas e pausas para intervencao;
- relancar execucoes.

Fora de escopo do painel:

- renderizar navegador interno como base da experiencia;
- executar diretamente a automacao no browser do frontend.

### 2. API De Orquestracao

Responsabilidades:

- persistir automacoes, sessoes de gravacao, jobs e execucoes;
- receber disparos manuais, webhooks e agendamentos;
- montar jobs para o runtime;
- aplicar politicas de fallback e regras de roteamento;
- armazenar resultados, evidencias, arquivos e entregas;
- acionar outputs como webhook e planilha.

Fora de escopo da API:

- ser o navegador;
- depender de screenshot interativo como forma principal de gravacao.

### 3. Runtime Local

Responsabilidades:

- abrir uma janela real do Chrome em perfil controlado;
- gravar eventos do usuario e consolidar em passos estruturados;
- executar fluxos Playwright em Chrome local;
- aplicar fallback por IA em desvios limitados;
- coletar screenshots, downloads, extracoes e logs;
- devolver estado e resultado para a API.

Caracteristicas principais:

- instalado junto com o produto ou empacotado como servico local;
- comunica-se com a API por jobs, eventos e heartbeats;
- pode operar tanto em modo interativo de gravacao quanto em modo automatizado de execucao.

## Estrutura De Codigo Alvo

```text
apps/
  web/
  api/
  runtime/
packages/
  shared/
docs/
  superpowers/
    specs/
    plans/
```

### apps/web

Painel React reorganizado por dominio:

- automations;
- recordings;
- executions;
- schedules;
- settings;
- outputs.

### apps/api

Backend de orquestracao com modulos focados:

- automation domain;
- recording session domain;
- execution jobs/runs;
- outputs/integrations;
- schedules/triggers;
- ai fallback policy.

### apps/runtime

Novo servico local com modulos focados:

- chrome session manager;
- recorder;
- step normalizer;
- playback engine;
- fallback resolver;
- artifact collector.

### packages/shared

Contratos tipados entre painel, API e runtime:

- tipos de passo;
- tipos de automacao;
- tipos de job/run;
- tipos de output;
- tipos de erro e status;
- contrato de fallback.

## Modelo De Dominio

### automation

Representa a automacao configurada pelo usuario.

Campos principais:

- id;
- nome;
- modo principal: `gravado`, `hibrido`, `livre_ai`;
- passos base;
- variaveis;
- outputs;
- politica de fallback;
- configuracao de agenda;
- metadados operacionais.

### recording_session

Representa uma sessao temporaria de gravacao no Chrome real.

Campos principais:

- id;
- status;
- maquina/runtime responsavel;
- janela/perfil de navegador;
- eventos brutos capturados;
- passos normalizados gerados;
- timestamps de inicio e encerramento.

### execution_job

Representa um pedido de execucao ainda nao concluido.

Origem:

- manual;
- webhook;
- agendamento.

Campos principais:

- automacao alvo;
- payload de entrada;
- variaveis resolvidas;
- modo de execucao;
- prioridade;
- runtime designado.

### execution_run

Representa a execucao em andamento ou concluida.

Campos principais:

- status;
- etapas executadas;
- falhas;
- tentativas de fallback;
- screenshots;
- downloads;
- dados extraidos;
- logs;
- resultado final.

### fallback_policy

Define o comportamento do modo misto com limite.

Campos principais:

- max_tentativas_ia;
- timeout_total_fallback;
- tipos de correcao permitidos;
- quando pausar para intervencao humana.

### output_delivery

Representa a entrega final do resultado.

Destinos iniciais:

- webhook;
- planilha.

Campos principais:

- destino;
- payload enviado;
- status da entrega;
- historico de tentativas;
- erro final, se houver.

## Fluxo De Gravacao

1. O usuario cria uma nova automacao e escolhe gravar no Chrome.
2. O painel solicita a abertura de uma `recording_session`.
3. A API cria a sessao e a atribui a um runtime disponivel.
4. O runtime abre uma janela real do Chrome com perfil controlado.
5. O usuario navega normalmente.
6. O runtime captura navegacao, clique, digitacao, selecao, upload, download, espera e pontos de extracao.
7. Ao encerrar, o runtime normaliza os eventos em passos estruturados.
8. A API persiste os passos.
9. O painel apresenta a revisao dos passos, variaveis e outputs.

## Fluxo De Execucao Hibrida

1. Uma execucao e disparada manualmente, por webhook ou por agendamento.
2. A API monta um `execution_job` com automacao, variaveis, politica de fallback e outputs.
3. O runtime consome o job e inicia a execucao no Chrome local controlado.
4. O runtime segue o roteiro base.
5. Se um passo falhar por seletor, mudanca leve de tela ou ambiguidade, o runtime aciona o fallback por IA.
6. O fallback so pode agir dentro dos limites da `fallback_policy`.
7. Se resolver, o runtime registra a tentativa e segue a execucao.
8. Se nao resolver dentro do limite, a execucao pausa e aguarda intervencao humana no painel.
9. Ao terminar, a API processa outputs, registra historico e disponibiliza evidencias.

## Modo Hibrido E Modos Futuros

### Modo gravado

Executa apenas o roteiro validado, com minimo de inferencia.

### Modo hibrido

Executa um roteiro validado, com pequenas decisoes e correcoes assistidas por IA. Esse e o modo prioritario da primeira implementacao.

### Modo livre por IA

Recebe uma instrucao aberta, sem roteiro base, e usa o mesmo runtime para planejar e agir. Esse modo permanece planejado, mas nao entra na primeira entrega funcional.

## Integracoes De Saida

### Webhook

- envio de payload JSON com status, dados extraidos e metadados de execucao;
- suporte a cenarios de integracao com n8n, Make e sistemas proprios.

### Planilha

- envio de linhas estruturadas para planilha;
- foco inicial em fluxo simples e estavel de append/escrita;
- sem multiplicar formatos antes de estabilizar o caso principal.

## Estrategia De Migracao

### O que reaproveitar

- partes do editor atual;
- parte do modelo atual de automacoes, execucoes e integracoes;
- parte da engine atual como referencia de tipos de passo;
- integracoes de webhook e planilha, desde que reorganizadas por dominio.

### O que substituir

- recorder baseado em screenshot/WebSocket como caminho principal;
- dependencia central de Browserless para gravacao;
- acoplamento entre UI e execucao remota;
- geracao de passos por IA como substituto da gravacao real.

### Sequencia recomendada

1. Criar contratos compartilhados do dominio.
2. Reorganizar API em jobs/runs e sessoes de gravacao.
3. Implementar runtime local com Chrome real.
4. Conectar o painel ao novo fluxo de gravacao.
5. Conectar o painel ao novo fluxo de execucao e outputs.
6. Introduzir fallback hibrido com limite.
7. Migrar o restante da UI e remover o recorder legado.

## Riscos E Restricoes

### 1. Captura confiavel no Chrome real

E preciso definir bem como o runtime vai abrir e controlar o Chrome, preservar perfil e capturar eventos sem depender de overlay fragil.

### 2. Fallback por IA sem comportamento erratico

O fallback deve ser estritamente limitado. Sem limite claro, a plataforma fica imprevisivel, cara e dificil de auditar.

### 3. Sessao autenticada, downloads e uploads

Perfis, cookies, arquivos temporarios e isolamento por execucao precisam de uma estrategia explicita desde o inicio.

### 4. Escopo da primeira entrega

Se o projeto tentar entregar com a mesma profundidade `gravado`, `hibrido` e `livre por IA` ao mesmo tempo, ha alto risco de repetir a fragilidade atual.

## Testes E Validacao

### Validacao funcional da V1

Os seguintes cenarios precisam funcionar de ponta a ponta:

- login em sistema web e navegacao por menus;
- preenchimento e envio de formulario;
- extracao de dados de pagina;
- download de arquivo quando aplicavel;
- entrega por webhook;
- entrega em planilha;
- pausa para intervencao humana quando o fallback falhar.

### Estrategia de testes

- testes unitarios para normalizacao de passos e politicas de fallback;
- testes de integracao da API para jobs, runs e outputs;
- testes de runtime para gravacao e playback em fluxo controlado;
- testes end-to-end com cenarios reais minimos para os dois casos prioritarios.

## Decisoes De Escopo

Entram na primeira entrega:

- Chrome real controlado por runtime;
- gravacao funcional;
- execucao manual, agendada e por webhook;
- modo hibrido com limite;
- outputs para webhook e planilha;
- logs, evidencias e pausa para intervencao.

Nao entram na primeira entrega:

- navegador embutido como experiencia principal;
- agente totalmente livre por IA com autonomia ampla;
- expansao prematura de integracoes;
- autoaprendizado avancado baseado em correcao humana.

## Resultado Esperado

Ao final da reestruturacao da V1, o produto deve deixar de ser uma tentativa de controlar um navegador remoto dentro do painel e passar a ser uma plataforma operacional com:

- painel web de controle;
- API de orquestracao;
- runtime local de Chrome real;
- execucao hibrida auditavel;
- capacidade pratica de operar sistemas web e capturar dados com confiabilidade maior que a arquitetura atual.
