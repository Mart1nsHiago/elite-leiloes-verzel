# Elite Leilões — Teste técnico Verzel (Elite Dev)

> Casa de leilões on-line para **livros e colecionáveis**, com salas em tempo real, carteira simulada, competição de lances, liquidação e auditoria pública.

**Stack:** React 18 + Vite + TypeScript | Python + FastAPI | PostgreSQL + SQLAlchemy | WebSockets | Docker.

O projeto implementa o desafio proposto no PDF *Teste técnico: Elite Dev na Verzel*. Nenhuma transação financeira real é realizada.

## 1. Comece em 2 comandos (Docker)

Requisitos: **Docker** e plugin **Docker Compose** instalados.

```bash
docker compose up --build -d
```

Acesse **http://localhost:8000** (aplicação completa) ou **http://localhost:8000/docs** (documentação interativa da API).

Para acompanhar logs:

```bash
docker compose logs -f app
```

Para encerrar, preservando dados do PostgreSQL:

```bash
docker compose down
```

> `docker compose down -v` **apaga o banco** e refaz os dados de demonstração na próxima execução.

**Alternativa sem Docker para desenvolvimento:**

Terminal 1 — back-end (SQLite local para agilizar a configuração):

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — front-end:

```bash
cd frontend
npm install
npm run dev
```

Acesse **http://localhost:5173**. O servidor Vite encaminha `/api` e WebSockets ao FastAPI.

Recomenda-se Python 3.12 e Node.js 22.

## 2. Contas prontas para avaliação

Os dados são criados automaticamente quando o banco está vazio.

| Papel | E-mail | Senha local | Observações |
|---|---|---|---|
| Leiloeiro | `leiloeiro@demo.com` | `Demo@2026` | Publica, acompanha e cancela lotes sem lances |
| Licitante 1 | `ana@demo.com` | `Demo@2026` | Carteira com saldo e um arremate encerrado |
| Licitante 2 | `bruno@demo.com` | `Demo@2026` | Líder de um leilão ao vivo |

**Importante:** a senha das contas de demonstração deve ser alterada com `DEMO_PASSWORD` ao fazer o deploy. O ambiente `ENVIRONMENT=production` **recusa inicialização** com a senha padrão e também exige segredos `JWT_SECRET` e `AUDIT_SECRET` longos.

Lotes iniciais:

- **Dom Casmurro:** ao vivo com dois lances válidos; permite testar disputa e superação.
- **O Pequeno Príncipe:** ao vivo, ainda sem lances; permite testar o primeiro lance.
- **Memórias Póstumas de Brás Cubas:** agendado para começar em cerca de uma hora.
- **A Metamorfose:** encerrado, com arremate da conta `ana@demo.com`, liquidação e comprovante público.

Os horários são relativos ao instante em que um banco vazio é inicializado; o estado de lotes ativos muda normalmente com o tempo.

## 3. Percurso sugerido para o avaliador

1. Abra a vitrine pública e filtre lotes **Ao vivo**, **Em breve** e **Encerrados**.
2. Acesse **Dom Casmurro**, veja valor atual, cronômetro, histórico e auditoria pública.
3. Entre como **Ana** e ofereça o valor mínimo exibido. Observe a notificação, o lance registrado e o saldo comprometido.
4. Entre em uma segunda janela com a conta **Bruno**. Supere o lance de Ana; a carteira dela libera a reserva.
5. Entre como **leiloeiro**, abra **Painel do leiloeiro → Novo lote**, pesquise um livro na Open Library e configure valor inicial, incremento, início e fim.
6. Verifique que só se cancela um lote que **não recebeu nenhum lance**.
7. Entre como Ana e acesse **Meus arremates → A Metamorfose → Comprovante**. Copie seu link e abra em uma janela anônima.
8. Acesse a **Auditoria pública**, onde cada lance possui assinatura individual, referência ao anterior e âncora assinada do lote.
9. Para demonstrar o *anti-sniping* sem aguardar duas horas, crie um lote com término próximo; quando faltarem até 2 minutos, um lance válido prorroga o encerramento em 2 minutos.

## 4. Regras de negócio implementadas

### Autenticação e permissões

- Login com e-mail e senha armazenada como hash Argon2id; token JWT HS256 com expiração.
- Cadastro aberto apenas para novos licitantes. O leiloeiro é uma conta pré-configurada para evitar elevação de privilégios por cadastro.
- Leiloeiro pode gerenciar **apenas os próprios lotes**, não pode dar lances.
- Licitante pode depositar créditos simulados e oferecer lances, mas não publicar lotes.
- Auditoria e comprovantes são públicos. Dados pessoais dos participantes não aparecem neles; apenas aliases.

### Lance e concorrência

- Lances aceitos somente **entre início e término**, em lotes ativos.
- Primeiro lance `>= valor inicial`; seguintes `>= valor atual + incremento mínimo`.
- Licitante líder não pode cobrir o próprio lance.
- Cada lance exige saldo **disponível** suficiente.
- A operação é executada na mesma transação que atualiza preço, liderança, reserva lógica e cadeia de auditoria.
- No **PostgreSQL**, o lote é selecionado com `SELECT ... FOR UPDATE` para serializar lances concorrentes no mesmo item; a carteira do licitante também é bloqueada para reduzir corridas entre lotes simultâneos.
- Valores monetários em **centavos inteiros**, evitando arredondamento com ponto flutuante.
- Em caso de lance aceito quando restam `<= 120 s`, `ends_at += 120 s`.
- A resposta ao lance traz motivo claro se houver conflito, saldo insuficiente ou outro impedimento.

### Saldo e liquidação

- `total` = depósitos simulados + vendas recebidas − compras liquidadas.
- `comprometido` = soma do maior lance nos lotes ativos em que o licitante lidera.
- `disponível = total − comprometido`.
- Quando outro licitante lidera, a antiga reserva deixa de entrar no cálculo **imediatamente**.
- Ao encerrar, o worker verifica integridade e realiza uma única liquidação: débito do licitante, crédito do leiloeiro, transações de carteira e comprovante. Lotes sem lances fecham sem vencedor.
- O processamento de fechamento é **idempotente**, protegido pelo estado e por índice único `receipts.lot_id`.

### Tempo real e API externa

- A sala abre um WebSocket público e recebe avisos `lot_updated`. Após cada aviso, busca o estado autoritativo no banco (evita divergência de estado em mensagens atrasadas).
- Também há atualização periódica a cada 12 segundos caso o WebSocket fique indisponível.
- Um worker verifica os lotes expirados a cada 4 segundos.
- A Open Library é usada apenas na **pesquisa do catálogo** durante a criação de um lote; os detalhes selecionados são gravados no PostgreSQL.
- Se a API externa falhar, a busca oferece uma pequena lista local de **referências previamente conhecidas**, marcada como `source: cached_reference`. Leilões existentes, carteira, sala, auditoria e recibos funcionam independentemente da API.

### Auditoria de integridade

Cada lance registra `id`, `lot_id`, `bidder_id`, `alias`, `amount_cents`, `timestamp`, `previous_hash` e uma **assinatura HMAC-SHA256** com segredo configurado **fora do banco**. A assinatura cobre todos esses campos em JSON canônico.

A cada novo lance, o lote armazena `audit_count`, `audit_head` e um `audit_seal` assinado que vincula número de lances, hash final, preço e líder. A rota `/api/lots/{id}/audit` verifica:

1. A assinatura de **cada** lance;
2. A continuidade dos hashes da cadeia;
3. A contagem e o hash final com a âncora;
4. O selo do lote, a sequência de valores e a liderança.

Isso **detecta inserções, edições e exclusões diretas de linhas SQL** sem acesso ao segredo da aplicação, e impede liquidação de um histórico violado.

**Limite explícito de segurança:** o hash final está ancorado no **mesmo banco**. Um adversário capaz de restaurar um snapshot antigo completo do banco pode, em tese, reintroduzir um estado anteriormente assinado, sem disparar detecção. Garantir *rollback resistance* exigiria publicação periódica do `audit_head` em um meio **externo, durável e imutável** (por exemplo: object storage com Object Lock, log de transparência ou notário). Esse mecanismo adicional não está provisionado nesta demonstração; não afirmamos proteção absoluta contra rollback completo. O segredo HMAC nunca deve ficar no banco.

## 5. Endpoints principais

Documentação OpenAPI: `GET /docs` (Swagger UI gerada pelo FastAPI).

| Método | Caminho | Função | Permissão |
|---|---|---|---|
| `POST` | `/api/auth/login` | Login e JWT | Pública |
| `POST` | `/api/auth/register` | Cadastro de licitante | Pública |
| `GET` | `/api/auth/me` | Perfil autenticado | Autenticada |
| `GET` | `/api/lots?status=live` | Vitrine e filtros | Pública |
| `GET` | `/api/lots/{id}` | Sala/lote | Pública |
| `GET` | `/api/lots/{id}/audit` | Auditoria completa | Pública |
| `WS` | `/api/lots/{id}/ws` | Eventos em tempo real | Pública |
| `GET` | `/api/catalog/search?q=...` | API Open Library/fallback | Pública |
| `POST` | `/api/lots` | Criar lote | Leiloeiro |
| `GET` | `/api/me/lots` | Lotes próprios | Leiloeiro |
| `DELETE` | `/api/lots/{id}` | Cancelar lote sem lances | Leiloeiro |
| `POST` | `/api/lots/{id}/bids` | Realizar lance | Licitante |
| `GET` | `/api/wallet` | Saldo total, comprometido e disponível | Autenticada |
| `POST` | `/api/wallet/deposit` | Depósito simulado | Licitante |
| `GET` | `/api/me/activity` | Lances e arremates | Licitante |
| `GET` | `/api/receipts/{token}` | Comprovante verificável | Pública |
| `GET` | `/api/health` | Health check | Pública |

Exemplo de lance (JSON):

```http
POST /api/lots/1/bids
Authorization: Bearer <TOKEN_JWT>
Content-Type: application/json

{"amount_cents": 15000}
```

## 6. Testes automatizados

```bash
cd backend
pip install -r requirements.txt
python -m pytest -q
```

Há **16 testes** cobrindo: autenticação, papéis, lances, incremento, autossuperação, reserva/desbloqueio de saldo, insuficiência de créditos, depósito, criação/cancelamento, *anti-sniping*, leilão encerrado, recibo público, adulteração de lance, remoção de lance, inserção de lance e liquidação única.

A suíte isolada usa **SQLite** como banco transitório para execução rápida. As garantias de bloqueio de linhas (`SELECT FOR UPDATE`) são específicas do PostgreSQL e devem ser verificadas em um teste de integração com Postgres para validar contenção de alta concorrência.

## 7. Deploy público (obrigatório no desafio)

O projeto inclui `render.yaml` para a plataforma **Render**, com:

- Uma aplicação Docker (FastAPI + React compilado) em um **único domínio**;
- PostgreSQL gerenciado;
- Health check `/api/health`;
- Geração de `JWT_SECRET` e `AUDIT_SECRET`;
- `DEMO_PASSWORD` solicitado na configuração do Blueprint.

Passos:

1. Crie um **repositório público no GitHub** e envie o conteúdo desta pasta (inclusive `render.yaml`).
2. Na Render, abra **New → Blueprint** e selecione o repositório.
3. Confira serviços e banco propostos. **Revise eventuais custos, limites e expiração do plano gratuito** antes de criar.
4. Quando solicitado, configure `DEMO_PASSWORD` com uma senha forte diferente de `Demo@2026`; guarde-a para a equipe avaliadora.
5. Aguarde a primeira implantação e teste o endereço público criado pela Render.
6. Confirme `https://SEU-ENDERECO.onrender.com/api/health`, vitrine, cadastro, login, lances, WebSocket, auditoria e comprovante.
7. Envie o link do repositório e a URL pública no formulário da Verzel.

**Atenção:** o deploy **não é feito automaticamente por baixar o ZIP**. Ele exige autenticação nas contas GitHub/Render. O projeto já contém os arquivos de configuração, mas a URL pública só existe após a publicação.

Se preferir configurar manualmente, é possível publicar este `Dockerfile` em qualquer host capaz de executar Docker com PostgreSQL persistente. Execute **uma instância da aplicação, um processo Uvicorn**; o pub/sub dos WebSockets está em memória. Para múltiplas réplicas, use um broker externo (ex.: Redis pub/sub).

## 8. Estrutura

```text
elite-leiloes/
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Telas, navegação e WebSocket
│   │   ├── api.ts               # Cliente HTTP, contratos TypeScript
│   │   └── styles.css           # Design system responsivo
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── main.py              # Rotas, autenticação, realtime, background worker
│   │   ├── db.py                # Conexão e sessões SQLAlchemy
│   │   ├── models.py            # Tabelas e relações
│   │   ├── services.py          # Regras de saldo, auditoria e liquidação
│   │   ├── security.py          # Argon2, JWT e HMAC
│   │   └── seed.py              # Usuários e lotes de demonstração
│   ├── tests/test_auction.py
│   └── requirements.txt
├── Dockerfile                   # Imagem web completa
├── docker-compose.yml          # API + PostgreSQL local
├── render.yaml                 # Infraestrutura Render
└── README.md
```

## 9. Decisões e próximos aprimoramentos

- **Praticidade:** uma mesma instância FastAPI serve API e React compilado em produção, sem necessidade de dois domínios.
- **Persistência:** o PostgreSQL é fonte única da verdade; dinheiro em centavos inteiros e datas UTC.
- **Consistência:** transação + bloqueio de lote e licitante reduzem *race conditions* de ofertas simultâneas.
- **Realtime:** WebSockets são notificações; a leitura do banco define o estado definitivo.
- **Privacidade:** auditoria não expõe e-mails, nomes, senhas nem tokens JWT.
- **Auditabilidade:** hash encadeado + autenticação HMAC + selo independente de dados do histórico para detectar escrita SQL indevida.
- **Limitações:** não há gateways reais de pagamento, nota fiscal, restauração de senha nem suporte a múltiplas instâncias sem broker; não foram solicitados.
- **Evoluções possíveis:** migrações com Alembic, testes end-to-end de navegador, testes simultâneos sob PostgreSQL e ancoragem imutável externa da auditoria.

## 10. Declaração de uso de IA

Conforme solicitado pelo formulário da Verzel, declare honestamente a assistência de IA utilizada no projeto e as partes que você efetivamente revisou e validou. Uma sugestão fiel de texto está em [`docs/USO-DE-IA.md`](docs/USO-DE-IA.md). Não declare revisões ou testes manuais que não foram realizados.
