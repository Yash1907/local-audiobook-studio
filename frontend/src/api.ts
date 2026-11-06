export type Segment={id:string;chapter_id?:string;chapter_title?:string;original_text:string;page_number?:number}
export type Chapter={id:string;title:string;position:number}
export type Document={id:string;title:string;author:string;source_type:string;imported_at:string;source_path?:string;progress_segment?:string;chapters?:Chapter[];segments?:Segment[];progress?:{segment_id:string;offset:number};bookmarks?:{id:string;segment_id:string;label:string}[];warnings?:string}
export type Settings={voice:string;playback_speed:number;mode:string;citations:string;footnotes:string;lfm_enabled:boolean;theme:string;offline_only:boolean}
export type Generated={audio_id:string;duration:number;normalized_text:string;method:string;warnings:string[]}
let token=''
export async function api<T>(path:string, init:RequestInit={}):Promise<T>{
  if(!token && path!='/session') token=(await (await fetch('/api/session')).json()).token
  const headers:Record<string,string>={...(init.headers as Record<string,string>||{})}
  if(init.method && init.method!=='GET') headers['x-studio-token']=token
  if(init.body && !(init.body instanceof FormData)) headers['content-type']='application/json'
  const response=await fetch('/api'+path,{...init,headers})
  if(!response.ok){const error=await response.json().catch(()=>({detail:response.statusText}));throw new Error(error.detail||'Request failed')}
  return response.json()
}
export const post=<T>(path:string,data:unknown)=>api<T>(path,{method:'POST',body:JSON.stringify(data)})
