# Amazon Scraper Service (SeleniumBase UC Mode)

Serviço próprio, self-hosted, pra substituir o Browserless **só** nas chamadas
pra Amazon — usa Chrome com modo furtivo (UC Mode) pra passar pelo AWS WAF,
onde o Browserless puro cai na tela de bloqueio ("Amazon.com.br Algo deu errado").

Continue usando o Browserless normalmente pra Shein, Avon, Natura etc. — esse
serviço aqui é só mais uma peça, não substitui o resto.

## ⚠️ Aviso importante

Não consegui testar o `docker build` deste Dockerfile de verdade aqui (meu
ambiente não tem acesso de rede aos repositórios do Google/Docker Hub). A
receita segue o padrão comum pra instalar Chrome + SeleniumBase em Debian
slim, mas se o build falhar no easypanel, o mais provável é algum pacote de
sistema ter mudado de nome — nesse caso, cola a mensagem de erro do build
que eu ajusto o Dockerfile.

## 1. Subir pro GitHub

Cria um repositório novo (pode ser privado) e sobe os 3 arquivos desta pasta
(`main.py`, `Dockerfile`, este `README.md`) na raiz dele.

## 2. Deploy no easypanel

1. Novo App → conectar ao repositório Git que você criou
2. Porta interna: **8000**
3. (Opcional, mas recomendado) Adicionar variável de ambiente `API_TOKEN`
   com um valor aleatório seu — isso tranca o serviço pra só aceitar
   chamadas que mandem o header `X-Token` certo, já que ele vai ficar
   exposto publicamente num subdomínio do easypanel.
4. Deploy — a primeira build demora mais porque baixa o Chrome inteiro.

Ao final, o easypanel te dá um domínio tipo
`seleniumbase-amazon.SEUUSUARIO.easypanel.host`.

## 3. Node do n8n

Troca o node "Buscar Produtos Amazon" pra apontar pra esse novo serviço:

```json
{
  "parameters": {
    "method": "POST",
    "url": "https://SEU-DOMINIO-AQUI/content",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        { "name": "X-Token", "value": "O_MESMO_VALOR_DO_API_TOKEN" }
      ]
    },
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify({ url: $json.link_ofertas_amazon, wait_selector: \"div[data-component-type='s-search-result']\", timeout: 12 }) }}",
    "options": { "timeout": 40000 }
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.3,
  "name": "Buscar Produtos Amazon",
  "retryOnFail": true,
  "maxTries": 3,
  "waitBetweenTries": 5000
}
```

Se você não configurou `API_TOKEN`, pode remover o bloco `sendHeaders`/
`headerParameters` inteiro — o serviço não vai exigir nada.

A resposta vem no mesmo formato que o Browserless já te dá
(`{"data": "<html>...</html>"}`), então o node de extração HTML que vem
depois continua lendo `{{ $json.data }}` sem precisar mudar nada.

## 4. Teste rápido

```
GET https://SEU-DOMINIO-AQUI/health
```

Deve responder `{"status": "ok"}` — confirma que o serviço subiu antes
mesmo de testar contra a Amazon.
