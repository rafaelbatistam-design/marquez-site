# Marquez Advogados — Automação de Notícias

Sistema que atualiza automaticamente a seção de Notícias do site toda segunda-feira, buscando artigos relevantes do STJ, Conjur, Migalhas e Jota.

---

## Como funciona

1. Todo **segunda-feira às 8h** (Brasília), o GitHub executa o script automaticamente
2. O script busca artigos nas 4 fontes, filtrando por palavras-chave das áreas do escritório
3. Seleciona as 6 melhores notícias, distribuindo entre as fontes
4. Atualiza o `index.html` e publica no Netlify automaticamente
5. Você não precisa fazer nada — o site se atualiza sozinho ✅

Também é possível rodar manualmente a qualquer momento pelo painel do GitHub (botão "Run workflow").

---

## Configuração inicial (única vez)

### Passo 1 — Criar conta no GitHub
Acesse https://github.com e crie uma conta gratuita.

### Passo 2 — Criar repositório
1. Clique em **"New repository"**
2. Nome: `marquez-site`
3. Marque **"Private"** (para manter o código privado)
4. Clique em **"Create repository"**

### Passo 3 — Fazer upload dos arquivos
1. No repositório criado, clique em **"uploading an existing file"**
2. Faça upload de **todos os arquivos desta pasta** (index.html + pasta scripts + pasta .github)
3. Clique em **"Commit changes"**

### Passo 4 — Obter o token do Netlify
1. Acesse https://app.netlify.com → clique na sua foto → **"User settings"**
2. Clique em **"Applications"** → **"New access token"**
3. Nome: `GitHub Actions`
4. Copie o token gerado (começa com `nfp_...`)

### Passo 5 — Obter o Site ID do Netlify
1. No Netlify, acesse seu site **marquezadvogados.com.br**
2. Vá em **"Site configuration"** → **"General"**
3. Copie o **"Site ID"** (formato: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### Passo 6 — Adicionar os segredos no GitHub
1. No seu repositório GitHub, clique em **"Settings"**
2. No menu esquerdo: **"Secrets and variables"** → **"Actions"**
3. Clique em **"New repository secret"** e adicione os dois:

| Nome | Valor |
|------|-------|
| `NETLIFY_AUTH_TOKEN` | O token copiado no Passo 4 |
| `NETLIFY_SITE_ID` | O Site ID copiado no Passo 5 |

### Passo 7 — Testar
1. No repositório, clique em **"Actions"** (menu superior)
2. Clique em **"Atualizar Notícias — Marquez Advogados"**
3. Clique em **"Run workflow"** → **"Run workflow"** (botão verde)
4. Acompanhe a execução — deve completar em ~2 minutos
5. Verifique o site: https://marquezadvogados.com.br

---

## Personalização

Para ajustar as palavras-chave de filtragem, edite a lista `KEYWORDS` no arquivo `scripts/atualizar_noticias.py`.

Para mudar a frequência, edite a linha `cron` no arquivo `.github/workflows/atualizar-noticias.yml`:
- Toda segunda: `'0 11 * * 1'`
- Toda semana (segunda e quinta): `'0 11 * * 1,4'`
- Todo dia: `'0 11 * * *'`
