# Stack `claudecodeui-v2`

Arquivo: `stacks/claudecodeui-v2.yml`

## Objetivo
Criar uma stack nova, isolada da atual, para validar mudanças sem conflitar com o roteamento existente.

## Diferenças principais
- Usa hostname separado via `APP_HOST`.
- Mantém os patches globais em `/root/.claude-patches`.
- Adiciona `healthcheck` e `update_config`.
- Inclui `STACK_RELEASE` para facilitar forçar recriação.
- Expõe `DEFAULT_MODEL=gpt-5.4-mini` como variável de ambiente.

## Deploy sugerido
1. No Portainer, crie uma nova stack.
2. Cole o conteúdo de `stacks/claudecodeui-v2.yml`.
3. Ajuste `APP_HOST` para um domínio de teste.
4. Faça deploy.
5. Valide os logs para confirmar aplicação dos patches.

## Importante
Esta stack por si só não altera o comportamento da UI se o modelo padrão estiver codificado dentro da imagem ou do patch em `/root/.claude-patches/claude-sdk.js`.

## Validação rápida
- Verificar logs da stack e procurar por:
  - `[PATCH] Applied claude-sdk.js patch`
  - `[PATCH] Applied claude wrapper`
- Validar se o domínio de teste abre a nova interface.
- Se o default ainda não mudar, o próximo ajuste deve ser no arquivo `/root/.claude-patches/claude-sdk.js`.
