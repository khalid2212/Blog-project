const API = '/api';
const token = () => sessionStorage.getItem('blog_token');
const storedUser = () => { try { return JSON.parse(sessionStorage.getItem('blog_user') || 'null'); } catch { return null; } };
function logout(){ sessionStorage.removeItem('blog_token'); sessionStorage.removeItem('blog_user'); location.href='/'; }
function escapeHtml(v){ return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
async function api(path,{method='GET',body,auth=false}={}){
  const headers={}; if(body!==undefined)headers['Content-Type']='application/json';
  if(auth && token())headers['Authorization']=`Bearer ${token()}`;
  let response;
  try { response=await fetch(API+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body)}); }
  catch{throw Error('Cannot reach the server. Please try again.');}
  let data; try{data=await response.json();}catch{data={};}
  if(!response.ok){let detail=data.detail;if(Array.isArray(detail))detail=detail.map(x=>x.msg).join('; ');if(response.status===401&&auth){sessionStorage.removeItem('blog_token');sessionStorage.removeItem('blog_user');renderNav();}throw Error(detail||`Request failed (${response.status})`);}
  return data;
}
function showMessage(text,type='error'){const el=document.querySelector('#message');if(el){el.textContent=text;el.className='notice '+type;el.classList.remove('hidden');}}
function renderNav(){const target=document.querySelector('#navlinks');if(!target)return;const user=storedUser();target.innerHTML=token()&&user?`<a href="/">Home</a><a href="/editor.html">+ Write</a><span class="muted">${escapeHtml(user.name)}</span><button type="button" id="logout" class="btn outline">Logout</button>`:`<a href="/">Home</a><a href="/login.html">Login</a><a class="btn" href="/register.html">Register</a>`;document.querySelector('#logout')?.addEventListener('click',logout);}
function requireLogin(){if(!token()||!storedUser()){location.href='/login.html';return false;}return true;}
function queryId(){const v=new URLSearchParams(location.search).get('id');return v && /^[1-9]\d*$/.test(v)?Number(v):null;}
renderNav();
