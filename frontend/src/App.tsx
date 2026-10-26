import {useEffect, useState, type FormEvent, type ReactNode} from 'react'
import {ArrowRight, ArrowUpRight, BookOpen, CheckCircle2, ChevronLeft, Clock3, Gavel, Heart,
  LockKeyhole, Menu, Minus, Plus, Search, ShieldCheck, Sparkles, Wallet, X, Zap, ExternalLink,
  CircleAlert, Eye, Activity as ActivityIcon, LogOut, UserRound, Copy, BadgeCheck, SlidersHorizontal} from 'lucide-react'
import {API, request, brl, formatDate, timeLeft, go, type User, type Lot, type Wallet as WalletData,
  type CatalogItem, type Audit, type Activity, type Receipt} from './api'

function usePath(){
  const [path,setPath]=useState(window.location.hash.replace(/^#/, '') || '/')
  useEffect(()=>{const onChange=()=>setPath(window.location.hash.replace(/^#/,'')||'/'); window.addEventListener('hashchange',onChange); return()=>window.removeEventListener('hashchange',onChange)},[])
  return path
}
function useClock(){const [now,setNow]=useState(Date.now());useEffect(()=>{const i=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(i)},[]);return now}

function Status({status}: {status:Lot['status']}) {
 const labels={live:'Ao vivo',scheduled:'Em breve',closed:'Encerrado',cancelled:'Cancelado'}
 return <span className={`status status-${status}`}>{status==='live'&&<span className="status-dot"/>}{labels[status]}</span>
}
function Empty({title,detail,action}:{title:string;detail:string;action?:ReactNode}){
 return <div className="empty-state"><BookOpen size={36} strokeWidth={1.5}/><h3>{title}</h3><p>{detail}</p>{action}</div>
}
function Cover({lot,large=false}:{lot:Pick<Lot,'image_url'|'title'>,large?:boolean}){
 const [broken,setBroken]=useState(false)
 return <div className={`cover ${large?'cover-large':''}`}>{lot.image_url&&!broken?<img src={lot.image_url} alt={`Capa de ${lot.title}`} onError={()=>setBroken(true)} loading="lazy"/>:<div className="no-cover"><BookOpen size={large?76:50} strokeWidth={1}/><span>ELITE COLLECTION</span></div>}</div>
}
function LotCard({lot,now}:{lot:Lot;now:number}){
 return <button className="lot-card" onClick={()=>go(`/lote/${lot.id}`)}>
 <div className="lot-card-media"><Cover lot={lot}/><div className="lot-status"><Status status={lot.status}/></div></div>
 <div className="lot-card-body"><div className="eyebrow subtle">LIVROS & COLECIONÁVEIS <span>·</span> #{String(lot.id).padStart(4,'0')}</div>
 <h3>{lot.title}</h3><p className="lot-author">{lot.author || 'Autor desconhecido'}</p>
 <div className="lot-card-bottom"><div><span className="meta-label">{lot.bid_count?'Lance atual':'Lance inicial'}</span><strong>{brl(lot.bid_count?lot.current_cents:lot.initial_cents)}</strong></div>
 <div className="lot-timer"><Clock3 size={14}/>{lot.status==='scheduled'?`Inicia ${timeLeft(lot.starts_at,now)}`:lot.status==='live'?timeLeft(lot.ends_at,now):`${lot.bid_count} lances`}</div></div></div>
 </button>
}

function LoginModal({onClose,onSuccess}:{onClose:()=>void;onSuccess:(user:User, token:string)=>void}){
 const [register,setRegister]=useState(false),[name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[loading,setLoading]=useState(false),[error,setError]=useState('')
 async function submit(e:FormEvent){e.preventDefault();setError('');setLoading(true);try{
  const data=await request<{user:User;access_token:string}>(`/auth/${register?'register':'login'}`,{method:'POST',body:JSON.stringify(register?{name,email,password}:{email,password})})
  onSuccess(data.user,data.access_token)
 }catch(e){setError((e as Error).message)}finally{setLoading(false)}}
 return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal auth-modal" onMouseDown={e=>e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Acessar conta">
 <button className="icon-button close" onClick={onClose}><X size={20}/></button><div className="modal-emblem"><Gavel size={25}/></div>
 <h2>{register?'Comece a colecionar':'Que bom ter você de volta'}</h2><p>{register?'Crie sua conta de licitante e participe dos leilões.':'Entre na sua conta para continuar explorando raridades.'}</p>
 <form onSubmit={submit} className="form-stack">{register&&<label>Nome completo<input value={name} onChange={e=>setName(e.target.value)} required minLength={2} placeholder="Seu nome"/></label>}
 <label>E-mail<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required placeholder="voce@exemplo.com"/></label>
 <label>Senha<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={register?8:1} placeholder="••••••••"/></label>
 {error&&<div className="error-msg"><CircleAlert size={16}/>{error}</div>}
 <button disabled={loading} className="btn btn-dark full" type="submit">{loading?'Aguarde...':register?'Criar conta':'Entrar na conta'}<ArrowRight size={17}/></button></form>
 <p className="auth-switch">{register?'Já tem uma conta?':'Ainda não tem uma conta?'} <button onClick={()=>{setRegister(!register);setError('')}}>{register?'Fazer login':'Cadastre-se grátis'}</button></p>
 <div className="demo-hint">Para testar: <b>ana@demo.com</b> ou <b>leiloeiro@demo.com</b><br/>Senha no ambiente local: <b>Demo@2026</b>; no deploy, use a senha configurada pelo responsável.</div>
 </div></div>
}

function Home({now}:{now:number}){
 const [lots,setLots]=useState<Lot[]>([]),[filter,setFilter]=useState('all'),[q,setQ]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(true)
 useEffect(()=>{let active=true;const load=()=>request<Lot[]>('/lots').then(v=>{if(active){setLots(v);setError('')}}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoading(false)})
 load();const timer=setInterval(load,12000);return()=>{active=false;clearInterval(timer)}},[])
 const shown=lots.filter(l=>(filter==='all'||l.status===filter) && (l.title+' '+l.author).toLowerCase().includes(q.toLowerCase()))
 return <><section className="hero"><div className="hero-inner container"><div className="hero-copy"><div className="hero-pill"><span className="glow-dot"/> O SEU PRÓXIMO ACHADO ESTÁ AQUI</div>
 <h1>Grandes histórias.<br/><em>Lances inesquecíveis.</em></h1><p>Descubra edições únicas, encontre tesouros literários e participe de leilões ao vivo — cada lance pode virar uma nova história.</p>
 <div className="hero-buttons"><button className="btn btn-lime" onClick={()=>document.getElementById('explorar')?.scrollIntoView({behavior:'smooth'})}>Explorar leilões <ArrowUpRight size={18}/></button><button className="btn btn-hero-outline" onClick={()=>go('/como-funciona')}>Como funciona <ArrowRight size={17}/></button></div>
 <div className="hero-proof"><div className="proof-avatars"><span>A</span><span>B</span><span>M</span></div><span>Uma experiência transparente e em tempo real</span></div></div>
 <div className="hero-showcase"><div className="showcase-shape shape-1"/><div className="showcase-shape shape-2"/><div className="showcase-book book-a"><img src="https://covers.openlibrary.org/b/id/14625893-L.jpg" alt="Livro Dom Casmurro"/></div><div className="showcase-book book-b"><img src="https://covers.openlibrary.org/b/id/10521270-L.jpg" alt="Livro O Pequeno Príncipe"/></div><div className="showcase-sticker"><Zap size={17}/> LANCES AO VIVO</div><div className="showcase-caption">PEÇAS COM HISTÓRIA, VALOR E PROPÓSITO.</div></div></div></section>
 <section className="trust-band"><div className="container trust-items"><span><ShieldCheck size={19}/> Histórico auditável</span><span><Zap size={19}/> Atualização ao vivo</span><span><Wallet size={19}/> Pagamento simulado seguro</span><span><BadgeCheck size={19}/> Comprovante verificável</span></div></section>
 <section id="explorar" className="market-section container"><div className="section-heading"><div><div className="eyebrow accent">EXPLORE A COLEÇÃO</div><h2>Leilões em destaque<span className="heading-dot">.</span></h2><p>Encontre o livro que faltava na sua estante.</p></div><div className="live-counter"><span className="status-dot"/> {lots.filter(l=>l.status==='live').length} leilões ao vivo</div></div>
 <div className="market-toolbar"><div className="tabs">{([['all','Todos os lotes'],['live','Ao vivo'],['scheduled','Em breve'],['closed','Encerrados']] as const).map(([value,label])=><button key={value} className={filter===value?'tab active':'tab'} onClick={()=>setFilter(value)}>{label}</button>)}</div><div className="market-search"><Search size={18}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar por livro ou autor..."/></div></div>
 {error&&<div className="error-msg">{error}</div>}{loading?<div className="loading">Carregando leilões...</div>:shown.length?<div className="lot-grid">{shown.map(l=><LotCard key={l.id} lot={l} now={now}/>)}</div>:<Empty title="Nenhum lote encontrado" detail="Tente outro termo ou filtro para descobrir mais oportunidades."/>}
 </section><section className="bottom-cta container"><div><div className="eyebrow">COLECIONAR É VIVER HISTÓRIAS</div><h2>O próximo capítulo pode ser seu.</h2><p>Crie sua conta, deposite créditos simulados e participe dos leilões.</p></div><button className="btn btn-lime" onClick={()=>go('/como-funciona')}>Entenda como funciona <ArrowRight size={18}/></button></section></>
}

function LotPage({lotId,user,onLogin,now}:{lotId:number;user:User|null;onLogin:()=>void;now:number}){
 const [lot,setLot]=useState<Lot|null>(null),[wallet,setWallet]=useState<WalletData|null>(null),[history,setHistory]=useState<Audit|null>(null),[amount,setAmount]=useState(''),[busy,setBusy]=useState(false),[err,setErr]=useState(''),[ok,setOk]=useState('')
 async function refresh(){try{const current=await request<Lot>(`/lots/${lotId}`);setLot(current);const audit=await request<Audit>(`/lots/${lotId}/audit`);setHistory(audit);if(user?.role==='bidder')setWallet(await request<WalletData>('/wallet'))}catch(e){setErr((e as Error).message)}}
 useEffect(()=>{setLot(null);setHistory(null);setErr('');refresh();const i=setInterval(refresh,12000);
  let socket:WebSocket|undefined;try{const base=API||window.location.origin;const url=new URL(base);const proto=url.protocol==='https:'?'wss:':'ws:';socket=new WebSocket(`${proto}//${url.host}/api/lots/${lotId}/ws`);socket.onmessage=e=>{try{if(JSON.parse(e.data).type==='lot_updated')refresh()}catch{}}}catch{ /* polling fallback */ }
  return()=>{clearInterval(i);socket?.close()}
 },[lotId,user?.id])
 useEffect(()=>{if(lot)setAmount((lot.minimum_next_cents/100).toFixed(2))},[lot?.minimum_next_cents])
 async function bid(e:FormEvent){e.preventDefault();if(!user){onLogin();return}setBusy(true);setErr('');setOk('');try{const cents=Math.round(Number(amount.replace(',','.'))*100)
  if(!Number.isFinite(cents)||cents<=0)throw Error('Informe um valor válido.')
  const result=await request<{extended:boolean}>(`/lots/${lotId}/bids`,{method:'POST',body:JSON.stringify({amount_cents:cents})});setOk(result.extended?'Lance aceito! O encerramento foi prorrogado por 2 minutos.':'Lance realizado com sucesso! Você está na liderança.');await refresh()
 }catch(e){setErr((e as Error).message);await refresh()}finally{setBusy(false)}}
 if(!lot)return <div className="container loading-page">{err?<Empty title="Não foi possível abrir o lote" detail={err}/>: 'Carregando detalhes do lote...'}</div>
 const isLive=lot.status==='live',min=lot.minimum_next_cents,amountNum=Number(amount.replace(',','.'))||0
 const hasBid=Boolean(user&&history?.bids.some(b=>b.alias===user.public_alias))
 const bestByAlias=new Map<string,number>()
 history?.bids.forEach(b=>bestByAlias.set(b.alias,Math.max(bestByAlias.get(b.alias)||0,b.amount_cents)))
 const rank=user?[...bestByAlias.entries()].sort((a,b)=>b[1]-a[1]).findIndex(([alias])=>alias===user.public_alias)+1:0
 return <div className="container lot-detail"><button className="back-link" onClick={()=>go('/')}><ChevronLeft size={18}/> Voltar aos leilões</button>
 <div className="detail-grid"><div className="detail-left"><div className="detail-cover-wrap"><Cover large lot={lot}/><div className="detail-cover-badge"><Status status={lot.status}/></div></div><div className="detail-description"><h3>Sobre esta peça</h3><p>{lot.description||`Obra de ${lot.author}. Este item foi selecionado a partir do catálogo público Open Library.`}</p><div className="detail-facts"><span>Categoria <b>Livros & colecionáveis</b></span><span>Referência <b>#{String(lot.id).padStart(4,'0')}</b></span><span>Incremento mínimo <b>{brl(lot.increment_cents)}</b></span></div></div></div>
 <div className="detail-right"><div className="eyebrow accent">LEILÃO #{String(lot.id).padStart(4,'0')}</div><h1>{lot.title}</h1><p className="detail-author">por {lot.author || 'Autor desconhecido'}</p>
 <div className="auction-main-card"><div className="auction-top"><span>{lot.bid_count?'Lance mais alto':'Lance inicial'}</span><span className="update-tag"><span className="glow-dot"/>{lot.status==='live'?'Tempo real':'Status atualizado'}</span></div>
 <div className="auction-price">{brl(lot.bid_count?lot.current_cents:lot.initial_cents)}</div><div className="bid-count"><Gavel size={16}/>{lot.bid_count} {lot.bid_count===1?'lance registrado':'lances registrados'}</div>
 {hasBid&&rank>0&&<div className="rank-indicator"><ActivityIcon size={15}/> Sua posição na disputa: <strong>{rank}º lugar</strong></div>}
 <div className="auction-divider"/><div className="deadline-row"><div><span className="meta-label">{lot.status==='scheduled'?'Começa em':lot.status==='live'?'Encerra em':'Situação'}</span><strong>{lot.status==='closed'?'Leilão encerrado':timeLeft(lot.status==='scheduled'?lot.starts_at:lot.ends_at,now)}</strong></div><div className="clock-box"><Clock3 size={26}/></div></div>
 <p className="end-date">{lot.status==='scheduled'?'Início: ':'Término: '}{formatDate(lot.status==='scheduled'?lot.starts_at:lot.ends_at)}</p>
 {user?.role==='bidder'&&lot.is_leader&&isLive&&<div className="winner-note"><CheckCircle2 size={19}/> Você está ganhando este lote!</div>}
 {user?.role==='bidder'&&hasBid&&!lot.is_leader&&isLive&&<div className="outbid-note"><CircleAlert size={19}/> Você foi superado. Faça um novo lance para retomar a liderança.</div>}
 {isLive&&user?.role!=='auctioneer'&&<form className="bid-form" onSubmit={bid}><label>Seu lance (mínimo {brl(min)})</label><div className="bid-input-row"><span>R$</span><input inputMode="decimal" value={amount} onChange={e=>setAmount(e.target.value)} aria-label="Valor do lance"/><button type="button" title="Diminuir" onClick={()=>setAmount((Math.max(min/100,amountNum-lot.increment_cents/100)).toFixed(2))}><Minus size={16}/></button><button type="button" title="Aumentar" onClick={()=>setAmount((Math.max(min/100,amountNum+lot.increment_cents/100)).toFixed(2))}><Plus size={16}/></button></div>
 {user&&wallet&&<p className="wallet-mini"><Wallet size={14}/> Disponível: <strong>{brl(wallet.available_cents)}</strong> <button type="button" onClick={()=>go('/carteira')}>Adicionar saldo</button></p>}
 <button disabled={busy||lot.is_leader} className="btn btn-lime full" type="submit">{busy?'Enviando...':lot.is_leader?'Você está na liderança':user?'Fazer meu lance':'Entrar para dar lance'}<ArrowRight size={18}/></button>
 <p className="bid-disclaimer"><LockKeyhole size={13}/> Saldo reservado apenas enquanto você liderar.</p></form>}
 {!isLive&&<div className="inactive-message">{lot.status==='scheduled'?'Este leilão ainda não começou. Volte no horário indicado.':lot.bid_count?`Arrematado por ${lot.winner_alias}.`:'Lote encerrado sem lances.'}</div>}
 {err&&<div className="error-msg"><CircleAlert size={16}/>{err}</div>}{ok&&<div className="success-msg"><CheckCircle2 size={17}/>{ok}</div>}
 </div><div className="integrity-callout"><ShieldCheck size={23}/><div><strong>Histórico verificável</strong><p>Todos os lances têm assinatura criptográfica e cadeia de integridade pública.</p><button onClick={()=>go(`/auditoria/${lot.id}`)}>Ver auditoria do lote <ArrowRight size={14}/></button></div></div>
 <div className="bid-history"><div className="section-mini-heading"><h3>Histórico de lances</h3><span>{history?.bid_count||0} registros</span></div>{history?.bids?.length?<div>{[...history.bids].reverse().map((b,index)=><div className="bid-history-row" key={b.id}><span className="bid-avatar">{b.alias.slice(-2)}</span><div><strong>{b.alias}</strong><small>{formatDate(b.created_at)}</small></div><b>{brl(b.amount_cents)}</b>{index===0&&<span className="lead-pill">Líder</span>}</div>)}</div>:<p className="muted">Seja a primeira pessoa a dar um lance.</p>}</div>
 </div></div></div>
}

function WalletPage({user,onLogin}:{user:User|null;onLogin:()=>void}){
 const [wallet,setWallet]=useState<WalletData|null>(null),[value,setValue]=useState('200'),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false)
 async function load(){try{setWallet(await request<WalletData>('/wallet'))}catch(e){setError((e as Error).message)}}
 useEffect(()=>{if(user)load()},[user?.id]);if(!user)return <div className="container auth-required"><Empty title="Sua carteira espera por você" detail="Faça login para depositar créditos simulados e participar dos leilões." action={<button className="btn btn-dark" onClick={onLogin}>Entrar</button>}/></div>
 async function add(e:FormEvent){e.preventDefault();setBusy(true);setError('');setNotice('');try{const amount_cents=Math.round(Number(value.replace(',','.'))*100);await request('/wallet/deposit',{method:'POST',body:JSON.stringify({amount_cents})});setNotice('Depósito simulado realizado com sucesso.');await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <main className="container app-page"><div className="eyebrow accent">MINHA CONTA</div><h1>Minha carteira<span className="heading-dot">.</span></h1><p className="page-lead">Gerencie seus créditos virtuais para participar dos leilões.</p><div className="wallet-grid"><div className="wallet-balance-card"><div className="wallet-card-top"><span>ELITE WALLET</span><Wallet size={25}/></div><p>Saldo disponível</p><strong>{brl(wallet?.available_cents||0)}</strong><div className="wallet-card-bottom"><span>CONTA DIGITAL SIMULADA</span><span>•••• {String(user.id).padStart(4,'0')}</span></div></div>
 <div className="balance-summary"><h3>Resumo de saldo</h3><div><span>Saldo total</span><b>{brl(wallet?.total_cents||0)}</b></div><div><span>Comprometido em lances</span><b>{brl(wallet?.reserved_cents||0)}</b></div><div className="summary-available"><span>Disponível para dar lances</span><b>{brl(wallet?.available_cents||0)}</b></div></div></div>
 {user.role==='bidder'?<div className="deposit-panel"><div><div className="eyebrow accent">ADICIONAR CRÉDITOS</div><h2>Depósito simulado</h2><p>Escolha um valor para creditar instantaneamente. Nenhum dinheiro real é movimentado.</p></div><form onSubmit={add}><label>Valor do depósito</label><div className="deposit-options">{[100,200,500].map(n=><button type="button" key={n} className={value===String(n)?'selected':''} onClick={()=>setValue(String(n))}>{brl(n*100)}</button>)}</div><div className="money-input"><span>R$</span><input value={value} onChange={e=>setValue(e.target.value)} inputMode="decimal" aria-label="Valor do depósito"/></div><button disabled={busy} className="btn btn-dark full">{busy?'Processando...':'Adicionar saldo'}<Plus size={19}/></button>{error&&<div className="error-msg">{error}</div>}{notice&&<div className="success-msg">{notice}</div>}</form></div>:<div className="notice-panel">O leiloeiro recebe créditos simulados quando seus lotes são arrematados.</div>}
 </main>
}

function MyBids({user,onLogin}:{user:User|null;onLogin:()=>void}){
 const [items,setItems]=useState<Activity[]>([]),[error,setError]=useState(''),[loading,setLoading]=useState(true)
 useEffect(()=>{if(!user)return;request<Activity[]>('/me/activity').then(setItems).catch(e=>setError(e.message)).finally(()=>setLoading(false))},[user?.id])
 if(!user)return <div className="container auth-required"><Empty title="Acompanhe seus lances" detail="Entre para consultar seus lances, vitórias e comprovantes." action={<button className="btn btn-dark" onClick={onLogin}>Entrar</button>}/></div>
 return <main className="container app-page"><div className="eyebrow accent">MINHA JORNADA</div><h1>Meus arremates<span className="heading-dot">.</span></h1><p className="page-lead">Todos os leilões dos quais você participou.</p>{error&&<div className="error-msg">{error}</div>}{loading?<div className="loading">Carregando...</div>:items.length?<div className="activity-list">{items.map(x=><div className="activity-item" key={x.lot.id}><div className="activity-cover"><Cover lot={x.lot}/></div><div className="activity-content"><Status status={x.lot.status}/><h3>{x.lot.title}</h3><p>{x.lot.author}</p>{x.won&&<div className="success-tiny"><BadgeCheck size={15}/> Você arrematou este item!</div>}</div><div className="activity-side"><strong>{brl(x.lot.current_cents||x.lot.initial_cents)}</strong><button className="text-link" onClick={()=>go(`/lote/${x.lot.id}`)}>Ver lote <ArrowRight size={15}/></button>{x.receipt_token&&<button className="text-link" onClick={()=>go(`/comprovante/${x.receipt_token}`)}>Comprovante <ExternalLink size={15}/></button>}</div></div>)}</div>:<Empty title="Nenhum lance ainda" detail="Explore os leilões ao vivo e faça sua primeira oferta." action={<button className="btn btn-dark" onClick={()=>go('/')}>Explorar leilões</button>}/>}</main>
}

function SellerPanel({user}:{user:User}){
 const [lots,setLots]=useState<Lot[]>([]),[catalog,setCatalog]=useState<CatalogItem[]>([]),[query,setQuery]=useState(''),[selected,setSelected]=useState<CatalogItem|null>(null),[searching,setSearching]=useState(false),[saving,setSaving]=useState(false),[err,setErr]=useState(''),[note,setNote]=useState(''),[showForm,setShowForm]=useState(false)
 const [initial,setInitial]=useState('100'),[increment,setIncrement]=useState('10'),[description,setDescription]=useState(''),[start,setStart]=useState(''),[end,setEnd]=useState('')
 function localInput(d:Date){const local=new Date(d.getTime()-d.getTimezoneOffset()*60000);return local.toISOString().slice(0,16)}
 function prepare(){const now=new Date();setStart(localInput(now));setEnd(localInput(new Date(now.getTime()+2*3600_000)));setShowForm(true)}
 const load=()=>request<Lot[]>('/me/lots').then(setLots).catch(e=>setErr(e.message))
 useEffect(()=>{load()},[])
 async function find(e:FormEvent){e.preventDefault();setSearching(true);setErr('');setCatalog([]);try{const data=await request<{items:CatalogItem[]}>('/catalog/search?q='+encodeURIComponent(query));setCatalog(data.items);if(!data.items.length)setErr('Nenhum livro encontrado. Experimente outra busca.')}catch(e){setErr((e as Error).message)}finally{setSearching(false)}}
 async function create(e:FormEvent){e.preventDefault();if(!selected)return;setSaving(true);setErr('');try{await request('/lots',{method:'POST',body:JSON.stringify({external_id:selected.external_id,title:selected.title,author:selected.author,image_url:selected.image_url,description,initial_cents:Math.round(Number(initial.replace(',','.'))*100),increment_cents:Math.round(Number(increment.replace(',','.'))*100),starts_at:new Date(start).toISOString(),ends_at:new Date(end).toISOString()})});setNote('Lote publicado com sucesso!');setShowForm(false);setSelected(null);setCatalog([]);setQuery('');await load()}catch(e){setErr((e as Error).message)}finally{setSaving(false)}}
 async function cancel(id:number){if(!window.confirm('Cancelar este lote sem lances?'))return;try{await request(`/lots/${id}`,{method:'DELETE'});setNote('Lote cancelado.');await load()}catch(e){setErr((e as Error).message)}}
 return <main className="container app-page"><div className="seller-heading"><div><div className="eyebrow accent">ÁREA DO LEILOEIRO</div><h1>Meu painel<span className="heading-dot">.</span></h1><p className="page-lead">Gerencie lotes e acompanhe o resultado dos leilões.</p></div><button className="btn btn-dark" onClick={()=>{prepare();setErr('')}}><Plus size={18}/> Novo lote</button></div>
 <div className="seller-stats"><div><span>Lotes criados</span><strong>{lots.length}</strong></div><div><span>Ao vivo</span><strong>{lots.filter(l=>l.status==='live').length}</strong></div><div><span>Arrematados</span><strong>{lots.filter(l=>l.status==='closed'&&l.bid_count).length}</strong></div><div><span>Total recebido*</span><strong>{brl(lots.filter(l=>l.status==='closed').reduce((sum,l)=>sum+l.current_cents,0))}</strong><small>* créditos simulados</small></div></div>
 {note&&<div className="success-msg">{note}</div>}{!showForm&&err&&<div className="error-msg">{err}</div>}
 {showForm&&<div className="modal-backdrop" onMouseDown={()=>setShowForm(false)}><div className="modal seller-modal" onMouseDown={e=>e.stopPropagation()}><button className="icon-button close" onClick={()=>setShowForm(false)}><X size={20}/></button><div className="eyebrow accent">CRIAR LEILÃO</div><h2>Selecionar item do catálogo</h2><p>Os dados vêm da API pública Open Library e são salvos no lote para funcionamento independente da API.</p>
 {!selected?<><form className="search-catalog" onSubmit={find}><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Busque um título ou autor" required minLength={2}/><button disabled={searching} className="btn btn-dark" type="submit">{searching?'Buscando...':'Buscar'}</button></form><div className="catalog-results">{catalog.map(item=><button key={item.external_id} onClick={()=>setSelected(item)} className="catalog-result"><div className="catalog-cover">{item.image_url?<img src={item.image_url}/>:<BookOpen/>}</div><div><strong>{item.title}</strong><small>{item.author||'Autor desconhecido'} {item.year?`· ${item.year}`:''}</small></div><ArrowRight size={18}/></button>)}</div></>:<form className="form-stack" onSubmit={create}><div className="selected-catalog"><BookOpen size={21}/><div><strong>{selected.title}</strong><small>{selected.author}</small></div><button type="button" className="text-link" onClick={()=>setSelected(null)}>Trocar</button></div>
 <label>Descrição<textarea rows={2} value={description} onChange={e=>setDescription(e.target.value)} placeholder="Informações sobre a peça..."/></label><div className="two-inputs"><label>Lance inicial (R$)<input type="number" min="1" step="0.01" value={initial} onChange={e=>setInitial(e.target.value)} required/></label><label>Incremento mínimo (R$)<input type="number" min="1" step="0.01" value={increment} onChange={e=>setIncrement(e.target.value)} required/></label></div><div className="two-inputs"><label>Data de início<input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)} required/></label><label>Data de término<input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)} required/></label></div><button disabled={saving} className="btn btn-dark full">{saving?'Publicando...':'Publicar lote'}<ArrowRight size={17}/></button></form>}
 {err&&<div className="error-msg">{err}</div>}</div></div>}
 <div className="panel-list-head"><h2>Seus lotes</h2><span>{lots.length} itens</span></div><div className="seller-list">{lots.map(l=><div className="seller-row" key={l.id}><div className="seller-row-img"><Cover lot={l}/></div><div className="seller-row-main"><h3>{l.title}</h3><p>{l.author} · {l.bid_count} lances</p><Status status={l.status}/></div><div className="seller-row-money"><span>{l.bid_count?'Maior lance':'Lance inicial'}</span><strong>{brl(l.current_cents||l.initial_cents)}</strong>{l.status==='closed'&&l.bid_count>0&&<small>Arrematado por {l.winner_alias}</small>}</div><div className="seller-actions"><button className="outline-button" onClick={()=>go(`/lote/${l.id}`)}>Visualizar <ArrowUpRight size={16}/></button>{l.status!=='cancelled'&&<button className="outline-button" onClick={()=>go(`/auditoria/${l.id}`)}>Auditoria</button>}{l.status!=='cancelled'&&l.status!=='closed'&&!l.bid_count&&<button className="cancel-button" onClick={()=>cancel(l.id)}>Cancelar</button>}</div></div>)}</div>
 </main>
}

function AuditPage({lotId}:{lotId:number}){
 const [auditData,setAudit]=useState<Audit|null>(null),[error,setError]=useState('')
 useEffect(()=>{request<Audit>(`/lots/${lotId}/audit`).then(setAudit).catch(e=>setError(e.message))},[lotId])
 return <main className="container app-page"><button className="back-link" onClick={()=>go(`/lote/${lotId}`)}><ChevronLeft size={18}/> Voltar ao lote</button><div className="eyebrow accent">TRANSPARÊNCIA EM CADA LANCE</div><h1>Auditoria pública<span className="heading-dot">.</span></h1><p className="page-lead">Verifique a cadeia criptográfica do histórico de lances. Nenhum login é necessário.</p>{error&&<div className="error-msg">{error}</div>}{auditData&&<><div className={`audit-verdict ${auditData.valid?'valid':'invalid'}`}><div className="audit-verdict-icon">{auditData.valid?<ShieldCheck size={32}/>:<CircleAlert size={32}/>}</div><div><h2>{auditData.valid?'Histórico íntegro e verificado':'Inconsistência detectada no histórico'}</h2><p>{auditData.valid?'Todas as assinaturas, os vínculos e a âncora do histórico foram validados.':'Um ou mais registros foram alterados ou estão inconsistentes.'}</p></div></div>
 <div className="audit-metrics"><div><span>Lote</span><strong>#{String(auditData.lot_id).padStart(4,'0')}</strong></div><div><span>Total de lances</span><strong>{auditData.bid_count}</strong></div><div><span>Resultado</span><strong>{auditData.valid?'Verificado':'Inválido'}</strong></div></div>
 {auditData.issues.length>0&&<div className="error-msg">{auditData.issues.join(' · ')}</div>}
 <div className="audit-table-wrap"><div className="panel-list-head"><h2>Registros assinados</h2><span>SHA-256 · HMAC</span></div><div className="audit-table"><div className="audit-table-header"><span>#</span><span>Participante</span><span>Valor</span><span>Horário</span><span>Assinatura</span></div>{auditData.bids.map(b=><div className="audit-table-row" key={b.id}><span>{b.id}</span><span>{b.alias}</span><strong>{brl(b.amount_cents)}</strong><span>{formatDate(b.created_at)}</span><code title={b.signature}>{b.signature.slice(0,13)}…</code></div>)}{!auditData.bids.length&&<div className="audit-table-empty">Nenhum lance registrado neste lote.</div>}</div></div>
 <div className="audit-hash"><span>HASH FINAL DA CADEIA</span><code>{auditData.head}</code><button onClick={()=>navigator.clipboard?.writeText(auditData.head)}><Copy size={17}/> Copiar</button></div><p className="security-note">A verificação usa HMAC-SHA256 com chave fora do banco e selo do lote. Para resistir também a restaurações completas de snapshots antigos, é necessário ancorar o hash em armazenamento externo imutável.</p></>}</main>
}

function ReceiptPage({receiptToken}:{receiptToken:string}){
 const [data,setData]=useState<Receipt|null>(null),[error,setError]=useState('')
 useEffect(()=>{request<Receipt>(`/receipts/${receiptToken}`).then(setData).catch(e=>setError(e.message))},[receiptToken])
 return <main className="container app-page receipt-page"><div className="eyebrow accent">COMPROVANTE DE ARREMATE</div><h1>Um novo capítulo é seu<span className="heading-dot">.</span></h1>{error&&<div className="error-msg">{error}</div>}{data&&<div className="receipt-card"><div className="receipt-header"><div className="brand-inverse"><Gavel size={23}/> elite<span>.</span></div><span>COMPROVANTE DIGITAL</span></div><div className="receipt-body"><div className={`receipt-verify ${data.valid?'':'invalid'}`}>{data.valid?<CheckCircle2 size={20}/>:<CircleAlert size={20}/>} {data.valid?'Autenticidade verificada':'Assinatura ou histórico inválido'}</div><h2>{data.title}</h2><div className="receipt-lines"><div><span>Lote</span><b>#{String(data.lot_id).padStart(4,'0')}</b></div><div><span>Arrematante</span><b>{data.winner_alias}</b></div><div><span>Data</span><b>{formatDate(data.closed_at)}</b></div><div><span>Valor final</span><strong>{brl(data.final_cents)}</strong></div></div><div className="receipt-signature"><span>ASSINATURA CRIPTOGRÁFICA</span><code>{data.signature}</code></div><div className="receipt-buttons"><button className="btn btn-dark" onClick={()=>navigator.clipboard?.writeText(window.location.href)}><Copy size={17}/> Copiar link público</button><button className="outline-button" onClick={()=>go(`/auditoria/${data.lot_id}`)}>Ver auditoria <ArrowUpRight size={16}/></button></div></div></div>}</main>
}

function HowItWorks(){return <main className="container app-page how-page"><div className="eyebrow accent">SIMPLES, SEGURO E TRANSPARENTE</div><h1>Como funciona<span className="heading-dot">.</span></h1><p className="page-lead">Conheça cada etapa da experiência Elite Leilões.</p><div className="how-grid">{[
 {i:'01',icon:<UserRound size={27}/>,title:'Crie sua conta',body:'Cadastre-se como licitante ou use uma das contas demonstrativas para explorar a plataforma.'},
 {i:'02',icon:<Wallet size={27}/>,title:'Adicione créditos',body:'Faça um depósito simulado em sua carteira. O saldo é reservado enquanto você lidera um lote.'},
 {i:'03',icon:<Gavel size={27}/>,title:'Dê seus lances',body:'Entre em uma sala ao vivo, acompanhe a disputa em tempo real e respeite o incremento mínimo.'},
 {i:'04',icon:<BadgeCheck size={27}/>,title:'Comprove sua vitória',body:'Ao encerrar, o lote vencedor gera um comprovante público e um histórico auditável de todos os lances.'}
 ].map(x=><div className="how-card" key={x.i}><div className="how-number">{x.i}</div><div className="how-icon">{x.icon}</div><h2>{x.title}</h2><p>{x.body}</p></div>)}</div><div className="how-bottom"><ShieldCheck size={26}/><div><strong>Justiça até o último segundo</strong><p>Um lance aceito nos dois minutos finais estende o encerramento por mais dois minutos. Cada proposta é validada no servidor.</p></div></div><button className="btn btn-dark" onClick={()=>go('/')}>Ver leilões <ArrowRight size={17}/></button></main>}

export default function App(){
 const path=usePath(),now=useClock(),[user,setUser]=useState<User|null>(null),[authOpen,setAuthOpen]=useState(false),[mobileOpen,setMobileOpen]=useState(false),[ready,setReady]=useState(false)
 useEffect(()=>{if(!localStorage.getItem('elite_token')){setReady(true);return};request<User>('/auth/me').then(setUser).catch(()=>localStorage.removeItem('elite_token')).finally(()=>setReady(true))},[])
 const logout=()=>{localStorage.removeItem('elite_token');setUser(null);go('/')}
 const loginSuccess=(newUser:User,token:string)=>{localStorage.setItem('elite_token',token);setUser(newUser);setAuthOpen(false)}
 let content:ReactNode
 if(path.startsWith('/lote/'))content=<LotPage key={path} lotId={Number(path.split('/')[2])} user={user} onLogin={()=>setAuthOpen(true)} now={now}/>
 else if(path.startsWith('/auditoria/'))content=<AuditPage key={path} lotId={Number(path.split('/')[2])}/>
 else if(path.startsWith('/comprovante/'))content=<ReceiptPage key={path} receiptToken={path.split('/')[2]}/>
 else if(path==='/carteira')content=<WalletPage user={user} onLogin={()=>setAuthOpen(true)}/>
 else if(path==='/meus-lances')content=<MyBids user={user} onLogin={()=>setAuthOpen(true)}/>
 else if(path==='/painel')content=user?.role==='auctioneer'?<SellerPanel user={user}/>:<div className="container auth-required"><Empty title="Acesso exclusivo do leiloeiro" detail="Entre com a conta de leiloeiro para gerenciar os lotes." action={<button className="btn btn-dark" onClick={()=>setAuthOpen(true)}>Entrar</button>}/></div>
 else if(path==='/como-funciona')content=<HowItWorks/>
 else content=<Home now={now}/>
 return <><header className="site-header"><div className="container nav-container"><button className="brand" onClick={()=>go('/')} aria-label="Elite Leilões"><span className="brand-icon"><Gavel size={23}/></span>elite<span>.</span><small>LEILÕES</small></button>
 <nav className={mobileOpen?'nav-links opened':'nav-links'}><button onClick={()=>{go('/');setMobileOpen(false)}}>Explorar</button><button onClick={()=>{go('/como-funciona');setMobileOpen(false)}}>Como funciona</button>{user?.role==='auctioneer'?<button onClick={()=>{go('/painel');setMobileOpen(false)}}>Painel do leiloeiro</button>:user&&<button onClick={()=>{go('/meus-lances');setMobileOpen(false)}}>Meus lances</button>}{user&&<button onClick={()=>{go('/carteira');setMobileOpen(false)}}>Minha carteira</button>}</nav>
 <div className="nav-actions">{user?<><button className="nav-user" onClick={()=>go(user.role==='auctioneer'?'/painel':'/carteira')}><span className="user-bubble">{user.name.charAt(0).toUpperCase()}</span><span className="user-name">{user.name.split(' ')[0]}</span></button><button className="icon-button logout" title="Sair" onClick={logout}><LogOut size={18}/></button></>:<><button className="login-link" onClick={()=>setAuthOpen(true)}>Entrar</button><button className="btn btn-nav" onClick={()=>setAuthOpen(true)}>Criar conta <ArrowUpRight size={17}/></button></>}
 <button className="icon-button mobile-toggle" aria-label="Abrir menu" onClick={()=>setMobileOpen(!mobileOpen)}>{mobileOpen?<X/>:<Menu/>}</button></div></div></header>
 <div className="app-main">{ready?content:<div className="loading">Iniciando...</div>}</div>
 <footer className="site-footer"><div className="container footer-content"><div><button className="brand footer-brand" onClick={()=>go('/')}><span className="brand-icon"><Gavel size={22}/></span>elite<span>.</span><small>LEILÕES</small></button><p>Onde grandes histórias encontram novos donos.</p></div><div className="footer-links"><button onClick={()=>go('/')}>Leilões</button><button onClick={()=>go('/como-funciona')}>Como funciona</button><span>Projeto técnico demonstrativo · Verzel</span></div></div><div className="container footer-bottom">© 2026 Elite Leilões. Ambiente de demonstração — sem movimentação financeira real.<span><ShieldCheck size={16}/> Integridade verificável</span></div></footer>
 {authOpen&&<LoginModal onClose={()=>setAuthOpen(false)} onSuccess={loginSuccess}/>}</>
}
