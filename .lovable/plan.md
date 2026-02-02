
# Plano: Melhorar Formulario + Upload Multimodal

## Resumo

Reorganizar o editor de automacao para:
1. Tornar campos de login/senha visiveis na aba de configuracao (com checkbox para ativar)
2. Marcar Google Sheets como opcional
3. Adicionar upload de audio, imagem e video na aba de Passos para descrever automacoes

---

## 1. Reorganizacao da Aba "Configuracao"

### Alteracoes no Formulario

**Campo ERP URL + Credenciais**
- Adicionar checkbox "Este ERP requer login?" abaixo do campo URL do ERP
- Quando marcado, exibir campos de usuario e senha diretamente na aba de configuracao
- Remover a aba separada de "Credenciais" (mover para dentro de Configuracao)

**Campo Google Sheets**
- Adicionar texto "(opcional)" ao label
- Manter o campo, mas deixar claro que nao e obrigatorio

### Layout Proposto

```text
+------------------------------------------+
|  INFORMACOES BASICAS                     |
+------------------------------------------+
|  Nome da Automacao *                     |
|  [____________________________________]  |
|                                          |
|  Descricao                               |
|  [____________________________________]  |
+------------------------------------------+
|  URL DO ERP                              |
+------------------------------------------+
|  URL do ERP                              |
|  [____________________________________]  |
|                                          |
|  [x] Este ERP requer login               |
|                                          |
|  +-- Campos que aparecem se marcado --+  |
|  |  Usuario        Senha              |  |
|  |  [__________]   [__________]       |  |
|  +------------------------------------+  |
+------------------------------------------+
|  INTEGRACAO (opcional)                   |
+------------------------------------------+
|  URL do Google Sheets (opcional)         |
|  [____________________________________]  |
+------------------------------------------+
```

---

## 2. Upload Multimodal na Aba "Passos"

### Novo Componente: MediaUploader

Adicionar zona de upload na aba de passos que aceita:
- **Audio** (MP3, WAV, M4A) - para descrever por voz o que quer automatizar
- **Imagem** (PNG, JPG, WEBP) - screenshots do ERP para a IA analisar
- **Video** (MP4, WEBM) - gravacao de tela mostrando o fluxo

### Layout da Aba Passos

```text
+------------------------------------------+
|  DESCREVA A AUTOMACAO                    |
+------------------------------------------+
|  Explique o que voce quer automatizar:   |
|  [Texto ou...                         ]  |
|  [                                    ]  |
|                                          |
|  OU envie midias para a IA analisar:     |
|                                          |
|  +--------------------------------------+|
|  |  [Icone Audio]  [Icone Imagem]       ||
|  |  [Icone Video]                       ||
|  |                                      ||
|  |  Arraste arquivos ou clique          ||
|  |  Audio, Imagem ou Video              ||
|  +--------------------------------------+|
|                                          |
|  Arquivos enviados:                      |
|  [X] audio_descricao.mp3 (transcrito)   |
|  [X] screenshot_erp.png                 |
|                                          |
|  [Gerar Passos com IA]                   |
+------------------------------------------+
```

### Fluxo de Processamento

1. Usuario faz upload de arquivo
2. Arquivo e salvo no Storage do backend
3. URL e registrada na tabela `media_uploads`
4. Ao clicar "Gerar Passos":
   - Audio: transcrito pela IA (modelo com capacidade de audio)
   - Imagem: analisada pela IA (visao computacional)
   - Video: frames extraidos e analisados
5. Conteudo processado e combinado com texto para gerar passos

---

## 3. Alteracoes nas Abas

### Antes (4 abas)
1. Configuracao
2. Passos
3. Credenciais
4. Webhook

### Depois (3 abas)
1. **Configuracao** (inclui credenciais do ERP)
2. **Passos** (inclui upload multimodal)
3. **Webhook**

---

## Detalhes Tecnicos

### Arquivos a Criar

**src/components/automation/MediaUploader.tsx**
- Componente de upload drag-and-drop
- Preview de arquivos enviados
- Botao para remover arquivos
- Indicador de processamento

**src/services/mediaService.ts**
- Upload de arquivos para Storage
- Registro na tabela `media_uploads`
- Processamento de audio/imagem/video

### Arquivos a Modificar

**src/pages/AutomationEditor.tsx**
- Remover aba "Credenciais"
- Adicionar checkbox "Requer login" na aba Configuracao
- Mostrar campos usuario/senha condicionalmente
- Adicionar MediaUploader na aba Passos
- Atualizar logica de salvamento

**supabase/functions/generate-steps/index.ts**
- Adicionar suporte a entrada multimodal
- Processar imagens (modelo com visao)
- Processar audio (modelo com transcricao)
- Combinar todas as fontes de informacao

### Migracao de Banco

- Criar bucket de storage `media-uploads`
- Configurar politicas de acesso

### Estrutura de Dados

A tabela `media_uploads` ja existe com os campos necessarios:
- `file_type`: 'image' | 'audio' | 'video'
- `file_url`: URL do arquivo no storage
- `transcription`: texto transcrito (para audio)
- `analysis`: resultado da analise de IA

---

## Validacoes

- Nome da automacao: obrigatorio
- URL do ERP: obrigatorio
- Credenciais: opcionais (aparecem se checkbox marcado)
- Google Sheets URL: opcional
- Passos: obrigatorio (pelo menos 1 passo)

---

## Beneficios

- **UX melhorada**: Credenciais visiveis sem mudar de aba
- **Flexibilidade**: Google Sheets claramente opcional
- **Multimodal**: Usuario pode descrever por voz, mostrar screenshots ou gravar video
- **Acessibilidade**: Quem prefere falar pode usar audio
- **Precisao**: Screenshots ajudam a IA entender o layout do ERP
