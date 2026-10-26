# Elite Leilões | Plataforma de leilões em tempo real

> Plataforma full-stack desenvolvida para o desafio técnico Elite Dev da Verzel, com leilões de livros e colecionáveis, disputa em tempo real, carteira simulada, liquidação e auditoria pública.

**Stack:** React 18 + Vite + TypeScript | Python + FastAPI | PostgreSQL + SQLAlchemy | WebSockets | Docker.

**Aplicação pública:** https://elite-leiloes-verzel.onrender.com  
**Documentação da API:** https://elite-leiloes-verzel.onrender.com/docs  
**Repositório:** https://github.com/Mart1nsHiago/elite-leiloes-verzel

O sistema contempla os papéis de leiloeiro (responsável por publicar e gerenciar seus lotes) e licitante (responsável por depósitos simulados e lances). Nenhuma movimentação financeira real é realizada.

## 1. Execução local com Docker

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

## 2. Perfis e contas de demonstração

Os dados são criados automaticamente quando o banco está vazio.

| Papel | E-mail | Senha no ambiente local | Permissões |
|---|---|---|---|
| Leiloeiro | `leiloeiro@demo.com` | `Demo@2026` | Publica, acompanha e cancela lotes sem lances |
| Licitante 1 | `ana@demo.com` | `Demo@2026` | Carteira com saldo e um arremate encerrado |
| Licitante 2 | `bruno@demo.com` | `Demo@2026` | Líder de um leilão ao vivo |

**Credenciais em produção:** a senha local de demonstração acima **não é utilizada no ambiente público**. A Render recebe outra senha por meio da variável privada `DEMO_PASSWORD`. As credenciais necessárias para a avaliação devem ser compartilhadas separadamente com a equipe Verzel. A inicialização em `ENVIRONMENT=production` exige a substituição da senha padrão e a configuração dos segredos `JWT_SECRET` e `AUDIT_SECRET`.

Lotes iniciais:

- **Dom Casmurro:** ao vivo com dois lances válidos; permite testar disputa e superação.
- **O Pequeno Príncipe:** ao vivo, ainda sem lances; permite testar o primeiro lance.
- **Memórias Póstumas de Brás Cubas:** agendado para começar em cerca de uma hora.
- **A Metamorfose:** encerrado, com arremate da conta `ana@demo.com`, liquidação e comprovante público.

Os horários são relativos ao instante em que um banco vazio é inicializado; o estado de lotes ativos muda normalmente com o tempo.

## 3. Fluxos funcionais para avaliação

1. **Vitrine:** exibe lotes ao vivo, agendados e encerrados, com filtros e pesquisa. Lotes cancelados não aparecem na vitrine.
2. **Sala do lote:** reúne imagem, descrição, maior lance, incremento mínimo, contagem regressiva, posição na disputa e histórico.
3. **Lances:** licitantes autenticados ofertam valores. A aplicação valida o valor mínimo, saldo disponível, período ativo e impedimento de autossuperação.
4. **Tempo real:** sessões independentes recebem atualizações por WebSocket sem recarregar a página. O backend é a fonte de verdade para os valores apresentados.
5. **Carteira:** o lance líder compromete o valor ofertado, que volta a ficar disponível quando outro participante o supera.
6. **Painel do leiloeiro:** permite pesquisar livros na Open Library, criar lotes, visualizar resultados e cancelar lotes que ainda não receberam lances.
7. **Encerramento:** o maior licitante recebe o arremate, o sistema liquida os créditos simulados e emite um comprovante compartilhável. Lotes sem lances encerram sem vencedor.
8. **Auditoria:** disponível sem login, consulta assinaturas, ligações da cadeia e selo de integridade; os participantes são identificados por aliases, sem exposição de dados pessoais.
9. **Prorrogação automática (*anti-sniping*):** lances aceitos nos dois minutos finais acrescentam dois minutos ao prazo de encerramento.

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

A suíte contém **16 testes** cobrindo: autenticação, papéis, lances, incremento, autossuperação, reserva/desbloqueio de saldo, insuficiência de créditos, depósito, criação/cancelamento, *anti-sniping*, leilão encerrado, recibo público, adulteração de lance, remoção de lance, inserção de lance e liquidação única.

A suíte isolada usa **SQLite** como banco transitório para execução rápida. As garantias de bloqueio de linhas (`SELECT FOR UPDATE`) são específicas do PostgreSQL e devem ser verificadas em um teste de integração com Postgres para validar contenção de alta concorrência.

## 7. Infraestrutura e publicação

**Ambiente publicado:** https://elite-leiloes-verzel.onrender.com  
**Health check:** https://elite-leiloes-verzel.onrender.com/api/health  
**Swagger/OpenAPI:** https://elite-leiloes-verzel.onrender.com/docs

O repositório utiliza um `render.yaml` que define uma aplicação web Docker e um banco PostgreSQL gerenciado. O `Dockerfile` compila o front-end React e publica os arquivos estáticos pelo FastAPI no mesmo domínio. O banco persiste usuários, lotes, lances, transações e comprovantes.

A configuração do ambiente é feita por variáveis, sem armazenar credenciais de produção no repositório:

| Variável | Função |
|---|---|
| `DATABASE_URL` | Endereço de conexão do PostgreSQL |
| `ENVIRONMENT` | Seleciona o modo de execução, incluindo `production` |
| `JWT_SECRET` | Assinatura dos tokens de autenticação |
| `AUDIT_SECRET` | Assinatura da trilha de auditoria |
| `DEMO_PASSWORD` | Senha das contas de demonstração em produção |
| `PYTHONUNBUFFERED` | Saída imediata dos logs do Python |

O arquivo `docker-compose.yml` permite reproduzir localmente o ambiente de aplicação e banco. A configuração atual usa uma instância do aplicativo com um processo Uvicorn; o mecanismo de eventos WebSocket é em memória, portanto múltiplas réplicas exigiriam um broker externo (por exemplo, Redis pub/sub).

O serviço de hospedagem pode aplicar limites de recursos ou suspensão por inatividade conforme o plano contratado.

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

## 10. Uso de IA e verificações realizadas

Foi utilizada assistência de inteligência artificial para apoiar o planejamento, a implementação de componentes do front-end e do back-end e a elaboração de documentação. O projeto foi executado localmente com Docker e publicado no GitHub e na Render. Na validação manual foram exercitados login e perfis, criação de lotes, lances em contas distintas, atualização em tempo real, regras de incremento e saldo, prorrogação, encerramento, liquidação, comprovantes e auditoria pública.

A trilha de auditoria utiliza HMAC-SHA256 e as verificações automatizadas incluem casos de adulteração. O relatório dos testes automatizados encontra-se em `docs/RESULTADO-TESTES.txt`; o escopo desses testes não substitui testes de carga e de concorrência em larga escala no PostgreSQL. A descrição complementar do uso de IA está em [`docs/USO-DE-IA.md`](docs/USO-DE-IA.md).
