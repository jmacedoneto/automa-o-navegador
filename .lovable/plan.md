
# Plano: Sistema Robusto de Automação ERP com Browserless

## Visao Geral

Transformar a aplicacao simples atual em um sistema completo e robusto de automacao ERP que suporta:
- **Multiplas automacoes** com agendamentos diversos (diario, semanal, a cada X minutos)
- **Geracao de webhooks** para integracao com N8N
- **Entrada multimodal**: texto, audio, imagens e video para explicar automacoes
- **IA interpretando conteudo visual** para entender fluxos de automacao
- **Execucao via Browserless** hospedado na VPS do usuario

---

## Arquitetura do Sistema

```text
+-------------------+     +-------------------+     +-------------------+
|    FRONTEND       |     |   EDGE FUNCTIONS  |     |   BROWSERLESS     |
|   (Lovable App)   |     |   (Supabase)      |     |   (VPS Usuario)   |
+-------------------+     +-------------------+     +-------------------+
|                   |     |                   |     |                   |
| Dashboard         |---->| generate-steps    |     | /function         |
| - Lista automacoes|     | (IA interpreta)   |     | /scrape           |
| - Upload midia    |     |                   |     | /download         |
| - Agendamentos    |     | process-media     |---->| /screenshot       |
| - Logs execucao   |     | (audio/video/img) |     |                   |
|                   |     |                   |     |                   |
|                   |     | execute-automation|---->|                   |
|                   |     | (roda no browser) |     |                   |
|                   |     |                   |     |                   |
|                   |     | webhook-trigger   |---->| N8N (externo)     |
|                   |     |                   |     |                   |
+-------------------+     +-------------------+     +-------------------+
         |                        |
         v                        v
+------------------------------------------------+
|              BANCO DE DADOS                    |
|  - automations (config + passos)               |
|  - execution_logs (historico)                  |
|  - schedules (agendamentos)                    |
|  - media_uploads (arquivos midia)              |
+------------------------------------------------+
```

---

## Funcionalidades Principais

### 1. Dashboard de Automacoes
- Lista todas as automacoes criadas
- Status (ativa/inativa)
- Ultima execucao e proximo agendamento
- Botoes para editar, executar, pausar, excluir

### 2. Entrada Multimodal com IA
- **Texto**: Campo para descrever em portugues
- **Audio**: Gravacao de voz que e transcrita e interpretada
- **Imagens**: Upload de screenshots do ERP para a IA identificar elementos
- **Video**: Upload de gravacao de tela que a IA analisa frame a frame

### 3. Sistema de Agendamentos
- Frequencia: uma vez, diario, semanal, mensal, a cada X minutos
- Horarios especificos
- Dias da semana
- Fuso horario

### 4. Webhooks para N8N
- URL unico gerado para cada automacao
- Disparo automatico apos execucao
- Payload customizavel com dados extraidos

### 5. Execucao e Logs
- Execucao manual ou agendada
- Logs detalhados de cada passo
- Screenshots de cada etapa
- Status de sucesso/erro

---

## Endpoints Browserless Utilizados

Baseado na documentacao estudada:

| Endpoint | Uso no Sistema |
|----------|----------------|
| `POST /function` | Executar scripts Puppeteer customizados com login, navegacao, cliques |
| `POST /scrape` | Extrair dados estruturados de tabelas/elementos |
| `POST /screenshot` | Capturar imagem da tela para logs |
| `POST /download` | Baixar arquivos (Excel, PDF) do ERP |

### Formato de Chamada /function
```javascript
// Enviar codigo + contexto para Browserless
{
  "code": "export default async function({ page, context }) { ... }",
  "context": {
    "username": "usuario",
    "password": "senha",
    "steps": [/* passos gerados pela IA */]
  }
}
```

---

## Estrutura de Banco de Dados (Novas Tabelas)

### Tabela: schedules
```sql
- id: UUID
- automation_id: FK -> automations
- schedule_type: enum (once, daily, weekly, monthly, interval)
- cron_expression: TEXT (para agendamentos complexos)
- interval_minutes: INTEGER (para "a cada X minutos")
- days_of_week: INTEGER[] (para semanal)
- time_of_day: TIME
- timezone: TEXT
- is_active: BOOLEAN
- next_run_at: TIMESTAMP
- last_run_at: TIMESTAMP
```

### Tabela: execution_logs
```sql
- id: UUID
- automation_id: FK -> automations
- started_at: TIMESTAMP
- finished_at: TIMESTAMP
- status: enum (running, success, failed)
- error_message: TEXT
- steps_completed: INTEGER
- total_steps: INTEGER
- screenshots: JSONB (array de URLs)
- extracted_data: JSONB
- webhook_response: JSONB
```

### Tabela: media_uploads
```sql
- id: UUID
- automation_id: FK -> automations (nullable para drafts)
- file_type: enum (image, audio, video)
- file_url: TEXT
- transcription: TEXT (para audio)
- analysis: JSONB (resultado da IA)
- created_at: TIMESTAMP
```

### Alteracoes na Tabela automations
```sql
- webhook_url: TEXT (URL unico gerado)
- webhook_secret: TEXT (para validacao)
- credentials: JSONB (usuario/senha criptografados)
- last_execution_at: TIMESTAMP
- last_execution_status: enum
```

---

## Edge Functions a Criar

### 1. process-media
- Recebe arquivo de audio/video/imagem
- Audio: transcreve usando Lovable AI (modelo com suporte a audio)
- Video: extrai frames e analisa com Gemini Vision
- Imagem: analisa com Gemini Vision para identificar elementos
- Retorna descricao textual + sugestoes de seletores

### 2. execute-automation
- Recebe automation_id
- Busca configuracao e passos do banco
- Monta script Puppeteer dinamicamente
- Envia para Browserless via /function
- Registra logs e screenshots
- Dispara webhook se configurado

### 3. trigger-webhook
- Chamado apos execucao bem-sucedida
- Envia dados extraidos para URL do N8N
- Registra resposta

### 4. generate-webhook-url
- Cria URL unico para cada automacao
- Gera secret para validacao

---

## Interface do Usuario (Componentes)

### Paginas
1. **Dashboard** (`/`)
   - Lista de automacoes com cards
   - Filtros e busca
   - Acoes rapidas

2. **Nova/Editar Automacao** (`/automation/new`, `/automation/:id`)
   - Wizard em etapas
   - Upload multimodal
   - Preview dos passos

3. **Detalhes da Automacao** (`/automation/:id/details`)
   - Configuracoes
   - Historico de execucoes
   - Logs detalhados

4. **Agendamentos** (`/automation/:id/schedule`)
   - Configurar frequencia
   - Calendario visual

### Componentes Novos
- `AutomationCard`: Card resumo na lista
- `MediaUploader`: Upload de audio/video/imagem com preview
- `AudioRecorder`: Gravar audio pelo microfone
- `VideoPlayer`: Visualizar video enviado
- `ScheduleConfigurator`: Configurar agendamentos
- `ExecutionLogs`: Timeline de execucoes
- `WebhookConfig`: Configurar integracao N8N
- `CredentialsForm`: Salvar usuario/senha do ERP

---

## Fluxo de Uso

1. Usuario clica "Nova Automacao"
2. Preenche dados basicos (nome, URL do ERP, URL Browserless)
3. Escolhe como descrever a automacao:
   - Texto: digita ou cola
   - Audio: grava ou faz upload
   - Imagem: envia screenshots
   - Video: envia gravacao de tela
4. IA processa a entrada e gera passos
5. Usuario revisa e ajusta passos
6. Configura credenciais (usuario/senha)
7. Configura agendamento (opcional)
8. Configura webhook N8N (opcional)
9. Salva e testa

---

## Detalhes Tecnicos

### Processamento de Audio
- Modelo: `google/gemini-2.5-flash` com suporte a audio
- Transcricao + interpretacao em uma chamada
- Retorna texto descritivo das instrucoes

### Processamento de Video
- Extrair frames chave (1 frame a cada 2 segundos)
- Enviar frames para `google/gemini-2.5-pro` (visao)
- IA descreve o que esta acontecendo em cada frame
- Gera sequencia de passos baseada na analise

### Processamento de Imagem
- Enviar imagem para `google/gemini-2.5-pro`
- IA identifica elementos da interface
- Sugere seletores CSS/XPath
- Descreve o que cada elemento faz

### Geracao de Script Browserless
- Converter passos em codigo Puppeteer valido
- Incluir tratamento de erros
- Adicionar screenshots em cada passo
- Estrutura com context para credenciais

---

## Consideracoes de Seguranca

- Credenciais armazenadas com criptografia
- Webhook URLs com secrets para validacao
- Rate limiting nas execucoes
- Logs nao expoe dados sensiveis

---

## Sequencia de Implementacao

### Fase 1: Estrutura Base
1. Migracoes do banco (novas tabelas)
2. Estrutura de rotas e paginas
3. Dashboard com lista de automacoes

### Fase 2: Entrada Multimodal
4. Componente de upload de midia
5. Gravacao de audio
6. Edge function process-media
7. Integracao com generate-steps

### Fase 3: Execucao
8. Edge function execute-automation
9. Integracao com Browserless /function
10. Sistema de logs

### Fase 4: Agendamentos e Webhooks
11. Configurador de agendamentos
12. Edge function trigger-webhook
13. Integracao N8N

### Fase 5: Polish
14. Melhorias de UX
15. Tratamento de erros
16. Documentacao
