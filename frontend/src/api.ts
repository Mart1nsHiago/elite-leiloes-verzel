export type Role = 'bidder' | 'auctioneer'
export type User = { id:number; name:string; email:string; role:Role; public_alias:string }
export type Lot = { id:number; title:string; author:string; description:string; image_url:string; external_id:string;
  initial_cents:number; increment_cents:number; current_cents:number; minimum_next_cents:number;
  status:'scheduled'|'live'|'closed'|'cancelled'; bid_count:number; starts_at:string; ends_at:string;
  seller_id:number; leader_alias:string|null; winner_alias:string|null; is_leader:boolean; is_owner:boolean }
export type Wallet = {total_cents:number; reserved_cents:number; available_cents:number}
export type Audit = {lot_id:number; title:string; valid:boolean; bid_count:number; head:string; issues:string[];
  bids:{id:number;alias:string;amount_cents:number;created_at:string;signature:string;previous_hash:string}[]}
export type CatalogItem = {external_id:string;title:string;author:string;year?:number;image_url:string}
export type Activity = {lot:Lot;won:boolean;receipt_token:string|null}
export type Receipt = {token:string;lot_id:number;title:string;winner_alias:string;final_cents:number;closed_at:string;valid:boolean;signature:string}

export const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export const getToken = () => localStorage.getItem('elite_token')

export async function request<T>(path:string, init:RequestInit = {}):Promise<T> {
  const auth = getToken()
  const headers:Record<string,string> = {...(init.headers as Record<string,string> || {})}
  if (init.body) headers['Content-Type'] = 'application/json'
  if (auth) headers.Authorization = `Bearer ${auth}`
  let res:Response
  try {res = await fetch(`${API}/api${path}`, {...init, headers})}
  catch {throw Error('Não foi possível conectar ao servidor. Verifique sua internet ou tente novamente.')}
  if (!res.ok) {
    let message = `Erro ${res.status}`
    try {const result = await res.json(); message = typeof result.detail === 'string' ? result.detail : message} catch { /* fallback */ }
    throw Error(message)
  }
  return res.json() as Promise<T>
}

export function brl(cents:number){return (cents/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}
export function formatDate(value:string){return new Date(value).toLocaleString('pt-BR',{dateStyle:'medium',timeStyle:'short'})}
export function timeLeft(value:string, now:number){
  const seconds = Math.max(0, Math.floor((new Date(value).getTime()-now)/1000))
  if(seconds===0) return 'Encerrado'
  const days = Math.floor(seconds/86400), h=Math.floor((seconds%86400)/3600),m=Math.floor((seconds%3600)/60),s=seconds%60
  return `${days?days+'d ':''}${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}
export function go(page:string){window.location.hash = page; window.scrollTo({top:0,behavior:'smooth'})}
