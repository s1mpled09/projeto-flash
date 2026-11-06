# Flash 3.0 — Site + Android + iPhone (base de desenvolvimento)

Marketplace de serviços em Flask/SQLite com interface responsiva, PWA instalável e projeto-base Capacitor para Android e iOS.

## Rodar o site

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abra http://127.0.0.1:5000. Para instalar como PWA, use o menu do navegador em um dispositivo compatível. Fora do localhost, a instalação requer HTTPS. A versão offline mostra apenas uma página de aviso; funcionalidades de conta exigem internet.

## Android e iPhone (Capacitor)

A pasta `mobile/` contém um **invólucro inicial** que carrega o site publicado via HTTPS. Não inclui APK, IPA nem builds nativas prontas.

1. Publique o backend Flask com HTTPS em domínio próprio (ambiente de produção).
2. Instale Node.js, Android Studio (Android) e, para iOS, macOS + Xcode.
3. Entre em `mobile/` e execute `npm install`.
4. Configure `FLASH_PUBLIC_URL=https://seu-dominio.example` no ambiente. No PowerShell: `$env:FLASH_PUBLIC_URL="https://seu-dominio.example"`.
5. Execute `npx cap add android` e/ou `npx cap add ios`; depois `npm run sync`.
6. Execute `npm run android` ou `npm run ios` para abrir o projeto na IDE correspondente.

**Atenção:** carregar um site remoto dentro de um app é uma base de protótipo, não uma garantia de aprovação nas lojas. Antes de publicar, crie recursos nativos reais, configure deep links, permissões, identidade visual, políticas e faça testes de loja.

## Recursos existentes

Cadastro/login, publicação e busca de serviços, propostas, contratação, perfil com avaliações, chat entre contratados, conclusão em duas etapas, registro de contestação, layout responsivo e navegação mobile.

## Segurança e limites

**Não existe pagamento, Pix, custódia ou liberação de dinheiro**; nenhum valor é cobrado. Para pagamento protegido, é necessário um parceiro financeiro autorizado, webhooks autenticados, reconciliação, KYC e processo de disputa.

Antes de uso público: HTTPS, SECRET_KEY persistente, banco PostgreSQL, migrações, backups, rate limiting, validação adicional, recuperação de senha, verificação de identidade, painel de mediação, LGPD, moderação, monitoramento e testes de segurança. O app não foi testado em Android/iOS físicos.

## Teste rápido

`python -m compileall -q app.py`
