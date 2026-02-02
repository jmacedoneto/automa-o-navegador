
# Plano: Configurar Suporte WebSocket no Traefik para Browserless

## Problema Identificado

A tela do DevTools fica em branco porque a conexão WebSocket não está sendo estabelecida corretamente. O Traefik precisa de configuração específica para permitir o upgrade de conexão HTTP para WebSocket.

## Solução

Adicionar labels no serviço Browserless no Docker Compose para configurar o Traefik a aceitar conexões WebSocket.

---

## Mudança Necessária no docker-compose.yml do Browserless

Adicionar as seguintes labels ao serviço browserless:

```yaml
services:
  browserless:
    image: browserless/chrome:latest
    # ... suas outras configuracoes ...
    deploy:
      labels:
        # Labels existentes
        - "traefik.enable=true"
        - "traefik.http.routers.browserless.rule=Host(`browserless.apvsiguatemi.net`)"
        - "traefik.http.routers.browserless.entrypoints=websecure"
        - "traefik.http.routers.browserless.tls=true"
        - "traefik.http.routers.browserless.tls.certresolver=letsencryptresolver"
        - "traefik.http.routers.browserless.service=browserless"
        - "traefik.http.services.browserless.loadbalancer.server.port=3000"
        
        # NOVAS LABELS PARA WEBSOCKET
        - "traefik.http.middlewares.browserless-ws.headers.customRequestHeaders.Connection=Upgrade"
        - "traefik.http.middlewares.browserless-ws.headers.customRequestHeaders.Upgrade=websocket"
        - "traefik.http.routers.browserless.middlewares=browserless-ws"
        
        # Tambem pode tentar com sticky sessions para WebSocket
        - "traefik.http.services.browserless.loadbalancer.sticky.cookie=true"
        - "traefik.http.services.browserless.loadbalancer.sticky.cookie.name=browserless_affinity"
```

---

## Configuracao Completa Atualizada

Aqui está o docker-compose.yml completo do Browserless com as correções:

```yaml
version: "3.7"

services:
  browserless:
    image: browserless/chrome:latest
    networks:
      - Deltanet
    environment:
      # --- Security (SSOT) ---
      - TOKEN=DefinaUmaSenhaForteAqui123
      
      # --- Recording & Debugging ---
      - HEADLESS=false
      - ENABLE_API_GET=true
      - ENABLE_CORS=true
      - ENABLE_DEBUGGER=true    # ADICIONAR ESTA LINHA
      
      # --- Evasion & Stealth ---
      - DEFAULT_STEALTH=true
      - DEFAULT_BLOCK_ADS=true
      
      # --- Performance ---
      - MAX_CONCURRENT_SESSIONS=20
      - MAX_QUEUE_LENGTH=40
      - CONNECTION_TIMEOUT=300000  # 5 minutos para gravacao
      
      # --- Workspace ---
      - WORKSPACE_DELETE_EXPIRED=1
      - WORKSPACE_EXPIRE_DAYS=1
      - PREBOOT_CHROME=1
      - KEEP_ALIVE=1

    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      resources:
        limits:
          cpus: "4"
          memory: 8192M
        reservations:
          cpus: "2"
          memory: 4096M
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.browserless.rule=Host(`browserless.apvsiguatemi.net`)"
        - "traefik.http.routers.browserless.entrypoints=websecure"
        - "traefik.http.routers.browserless.tls=true"
        - "traefik.http.routers.browserless.tls.certresolver=letsencryptresolver"
        - "traefik.http.routers.browserless.service=browserless"
        - "traefik.http.services.browserless.loadbalancer.server.port=3000"
        
        # === NOVAS LABELS PARA WEBSOCKET ===
        # Timeout maior para conexoes WebSocket de longa duracao
        - "traefik.http.services.browserless.loadbalancer.server.scheme=http"
        - "traefik.http.services.browserless.loadbalancer.passHostHeader=true"
        
        # Sticky sessions para manter conexao no mesmo container
        - "traefik.http.services.browserless.loadbalancer.sticky.cookie=true"
        - "traefik.http.services.browserless.loadbalancer.sticky.cookie.name=browserless_affinity"

networks:
  Deltanet:
    external: true
```

---

## Alternativa: Testar Conexao Direta (Debug)

Se após adicionar as labels o problema persistir, podemos testar acessando o Browserless diretamente (sem Traefik) para confirmar que o problema é do proxy:

1. Expor temporariamente a porta do Browserless no host:
```yaml
ports:
  - "3001:3000"
```

2. Testar acessando:
```
http://SEU_IP:3001/sessions?token=DefinaUmaSenhaForteAqui123
```

---

## Passos para Aplicar

| Passo | Acao | Descricao |
|-------|------|-----------|
| 1 | Editar docker-compose.yml | Adicionar labels de WebSocket e ENABLE_DEBUGGER |
| 2 | Redeploy do stack | `docker stack deploy -c docker-compose.yml browserless` |
| 3 | Aguardar 30 segundos | Esperar o servico reiniciar |
| 4 | Testar gravacao | Clicar em "Gravar Automacao" na aplicacao |

---

## Verificacao de Logs

Apos aplicar as mudancas, se ainda houver problemas, verifique os logs do Traefik:

```bash
docker service logs traefik_traefik -f --tail 100
```

Procure por erros relacionados a WebSocket ou conexoes rejeitadas.

---

## Resultado Esperado

1. Traefik passa corretamente os headers de WebSocket
2. Chrome DevTools consegue conectar via wss://
3. Tela mostra a pagina do ERP carregada
4. Usuario pode interagir com a sessao remota
