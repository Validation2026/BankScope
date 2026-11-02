'use strict';
(()=>{
const DATA=window.BANKSCOPE_DATA||{weekly:[],monthly:[],banks:[],sources:{},quality:{},generated_at:null};
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const trNumber=(n,d=2)=>Number.isFinite(Number(n))?Number(n).toLocaleString('tr-TR',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
const dateText=s=>s?new Date(s+'T12:00:00').toLocaleDateString('tr-TR',{day:'2-digit',month:'long',year:'numeric'}):'—';
const names={overview:'Genel görünüm',weekly:'BDDK haftalık',monthly:'BDDK aylık',banks:'Banka finansalları',compare:'Karşılaştırma',quality:'Veri güvenilirliği',sources:'Kaynaklar ve yöntem'};
let active='overview',curr='TOTAL',weekDate='',weekSearch='',bankDate='',bankScope='solo',compDate='',compScope='solo',compMetric='assets',selectedBanks=new Set();
const dates=[...new Set(DATA.weekly.map(x=>x.period))].sort().reverse();weekDate=dates[0]||'';
const bankPeriods=[...new Set(DATA.banks.map(x=>x.period))].sort().reverse();bankDate=compDate=bankPeriods[0]||'';
function togglePage(page){active=names[page]?page:'overview';document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id===active));document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===active));$('breadcrumb').textContent=names[active];history.replaceState(null,'','#'+active);render();window.scrollTo({top:0,behavior:'smooth'});}
function empty(title,desc,href,label){return `<div class="empty"><div class="empty-symbol">⌁</div><h3>${esc(title)}</h3><p>${esc(desc)}</p>${href?`<a href="${esc(href)}" rel="noopener noreferrer" target="_blank">${esc(label||'Resmî kaynak')} ↗</a>`:''}</div>`}
function weekFacts(id,p=weekDate){return DATA.weekly.filter(x=>x.period===p&&x.metric_id===id&&x.currency===curr)[0]}
function val(id,p=weekDate){return weekFacts(id,p)?.value}
function trill(v){return v==null?'—':trNumber(v/1e6,2)+' <small style="font-size:12px;color:#8997a8;letter-spacing:0">trilyon ₺</small>'}
function short(v){return v==null?'—':trNumber(v/1e6,2)}
function rowsForWeek(){return DATA.weekly.filter(x=>x.period===weekDate&&x.currency==='TOTAL')}
function bars(target,rows,scale=1,unit=''){const max=Math.max(0,...rows.map(x=>x.value));$(target).innerHTML=rows.map(x=>`<div class="bar-row"><div class="bar-label-row"><span>${esc(x.label)}</span><strong>${trNumber(x.value/scale,2)} ${esc(unit)}</strong></div><div class="track"><div class="fill" style="width:${max>0?Math.max(0,100*x.value/max):0}%"></div></div></div>`).join('')||'<p class="muted">Gösterilecek doğrulanmış veri yok.</p>'}
function renderOverview(){
 $('overview-date').textContent='Dönem sonu • '+dateText(dates[0]);
 const blocks=[['total_loans','TOPLAM KREDİLER'],['consumer_loans','TÜKETİCİ KREDİLERİ'],['retail_cards','BİREYSEL KREDİ KARTLARI'],['sme_loans','KOBİ KREDİLERİ']];
 $('overview-kpis').innerHTML=blocks.map(([key,label])=>`<div class="kpi"><div class="kpi-top">${label}</div><div class="kpi-val">${trill(DATA.weekly.find(x=>x.period===dates[0]&&x.metric_id===key&&x.currency==='TOTAL')?.value)}</div><div class="kpi-foot">${dateText(dates[0])} · BDDK · toplam TL karşılığı</div></div>`).join('');
 const keys=['commercial_other_loans','sme_loans','retail_cards','consumer_loans','personal_loans','retail_overdraft'];const rows=keys.map(key=>DATA.weekly.find(x=>x.metric_id===key&&x.currency==='TOTAL'&&x.period===dates[0])).filter(Boolean).map(x=>({label:x.label,value:x.value}));bars('overview-chart',rows,1e6,'');
 const items=[['BDDK haftalık','Doğrulanmış kredi tablosu · '+dateText(dates[0]),true],['BDDK aylık','Kaynak yayımlanmış; otomatik tablo eşleştirmesi bekleniyor',DATA.monthly.length>0],['Banka finansalları','TBB arşivi için finansal hesap eşleştirmesi bekleniyor',DATA.banks.length>0]];
 $('overview-status').innerHTML=items.map(([title,desc,ok])=>`<div class="status-item"><div class="status-circle ${ok?'':'pending'}">${ok?'✓':'!'}</div><div><b>${title}</b><p>${desc}</p></div></div>`).join('');
}
function fillOptions(id,items){$(id).innerHTML=items.length?items.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join(''):'<option value="">Henüz veri yok</option>'}
function renderWeekly(){
 $('week-date').value=weekDate;$('week-currency').value=curr;$('week-search').value=weekSearch;
 const lines=rowsForWeek().filter(x=>(x.label+' '+x.metric_id).toLocaleLowerCase('tr-TR').includes(weekSearch.toLocaleLowerCase('tr-TR')));
 const mapping=new Map(DATA.weekly.filter(x=>x.period===weekDate).map(x=>[x.metric_id+'|'+x.currency,x.value]));
 $('weekly-table').innerHTML=lines.map(x=>`<tr><td>${esc(x.label)} ${x.label.includes('Bilgi')?'<span style="color:#9faaba">•</span>':''}</td><td class="num">${trNumber(mapping.get(x.metric_id+'|TP'))}</td><td class="num">${trNumber(mapping.get(x.metric_id+'|YP'))}</td><td class="num"><strong>${trNumber(mapping.get(x.metric_id+'|TOTAL'))}</strong></td></tr>`).join('')||'<tr><td colspan="4">Eşleşen veri bulunamadı.</td></tr>';
 $('week-count').textContent=lines.length+' resmi kredi kalemi';$('week-total').textContent=trNumber(val('total_loans'),2);
 const keyList=['total_loans','commercial_other_loans','retail_plus_cards','sme_loans','consumer_loans','retail_cards'];
 const values=keyList.map(id=>({id,metric:DATA.weekly.find(x=>x.period===weekDate&&x.metric_id===id&&x.currency===curr)})).filter(x=>x.metric).map(x=>({label:x.metric.label,value:x.metric.value}));bars('weekly-chart',values,1e6,'trilyon TL');
}
function bankRowSet(p,scope){return DATA.banks.filter(x=>x.period===p&&x.scope===scope)}
function renderMonthly(){
 const rows=DATA.monthly;let d='';if(rows.length){const periods=[...new Set(rows.map(x=>x.period))].sort().reverse();let selected=periods[0];d=`<div class="panel"><div class="panel-title"><div><h3>${esc(selected)} · Resmî aylık kalemler</h3></div></div><div class="table-scroll"><table><thead><tr><th>Gösterge</th><th class="num">Değer</th><th>Birim</th></tr></thead><tbody>${rows.filter(x=>x.period===selected).map(x=>`<tr><td>${esc(x.label)}</td><td class="num">${trNumber(x.value)}</td><td>${esc(x.unit)}</td></tr>`).join('')}</tbody></table></div></div>`}
 else d=empty('Aylık veri henüz doğrulanmadı','BDDK Eylül 2026 aylık bülteni yayımlandı. Ancak interaktif tablodan güvenilir ve kapsayıcı bir aktarım tamamlanmadığı için burada rakam göstermiyoruz.',DATA.sources.bddk_monthly,'BDDK aylık bülteni aç');
 $('monthly-content').innerHTML=d;
}
const bankMetrics=[['assets','Aktifler'],['loans','Krediler'],['deposits','Mevduat'],['equity','Özkaynak'],['npl_ratio','TDO (%)'],['profit_ytd','Net kâr']];
function renderBanks(){
 $('bank-period').value=bankDate;$('bank-scope').value=bankScope;
 const rows=bankRowSet(bankDate,bankScope).filter(x=>Number.isFinite(x.assets)).sort((a,b)=>b.assets-a.assets);
 if(rows.length<10){$('banks-content').innerHTML=empty('Karşılaştırılabilir ilk 10 henüz hazır değil',`Aynı ${bankScope==='solo'?'solo':'konsolide'} dönemde en az 10 bankanın doğrulanmış toplam aktifleri gerekiyor. Şu anda ${rows.length} banka doğrulandı; eksik kayıtlarla ilk 10 sıralaması üretmiyoruz.`,DATA.sources.tbb_index,'TBB bankacılık verileri');return}
 const lines=rows.slice(0,10);$('banks-content').innerHTML=`<div class="panel"><div class="panel-title"><div><h3>${esc(bankDate)} · Aktif büyüklüğüne göre ilk 10</h3><small>Aynı kaynak, aynı dönem ve kapsam</small></div></div><div class="table-scroll"><table><thead><tr><th>#</th><th>Banka</th>${bankMetrics.map(x=>`<th class="num">${x[1]}</th>`).join('')}</tr></thead><tbody>${lines.map((r,i)=>`<tr><td>${i+1}</td><td><strong>${esc(r.name)}</strong></td>${bankMetrics.map(([k])=>`<td class="num">${trNumber(r[k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>`;
}
function renderCompare(){
 $('compare-period').value=compDate;$('compare-scope').value=compScope;$('compare-metric').value=compMetric;
 const rows=bankRowSet(compDate,compScope);if(!rows.length){$('compare-content').innerHTML=empty('Bankalar arası tablo henüz doğrulanmadı','Ortak dönemde, aynı kapsamdaki en az iki bankanın doğrulanmış verisi olmadan karşılaştırma oluşturulmaz.',DATA.sources.tbb_reports,'TBB raporları');return}
 const list=rows.filter(x=>Number.isFinite(x[compMetric]));
 if(!selectedBanks.size)list.slice(0,10).forEach(x=>selectedBanks.add(x.bank_id));
 let chosen=list.filter(x=>selectedBanks.has(x.bank_id)).sort((a,b)=>b[compMetric]-a[compMetric]);
 $('compare-content').innerHTML=`<div class="bank-list">${list.map(x=>`<button data-bank="${esc(x.bank_id)}" class="bank-toggle ${selectedBanks.has(x.bank_id)?'selected':''}">${esc(x.name)}</button>`).join('')}</div><div class="panel"><div class="panel-title"><div><h3>Seçilen banka performansları</h3><small>Metrik ve birim tanımları kaynaklarda korunur</small></div></div><div id="compare-bars" class="bars"></div></div>`;
 document.querySelectorAll('[data-bank]').forEach(b=>b.addEventListener('click',()=>{selectedBanks.has(b.dataset.bank)?selectedBanks.delete(b.dataset.bank):selectedBanks.add(b.dataset.bank);renderCompare()}));
 bars('compare-bars',chosen.map(x=>({label:x.name,value:x[compMetric]})),1,'');
}
function renderQuality(){const q=DATA.quality||{};
 $('quality-grid').innerHTML=[['Haftalık dönem',q.weekly_periods?.length||0,'Kredi sekmesi doğrulandı'],['Aylık sektör',DATA.monthly.length,'Tam tablo doğrulaması bekleniyor'],['Banka sayısı',q.bank_count_verified||0,'En büyük 10 sıralaması bekleniyor']].map(([label,v,note])=>`<div class="q-card"><div class="q-label">${label}</div><div class="big">${v}</div><div class="q-status">${esc(note)}</div></div>`).join('');
 $('quality-missing').innerHTML=(q.missing_modules||[]).map(x=>`<div class="missing"><div>${esc(x)}</div></div>`).join('')||'<p>Tüm modüller doğrulandı.</p>';
}
function renderSources(){const sections=[['BDDK Haftalık Bülten','Kredi ve sektör verileri; resmi kesit ve ayrımlar.',DATA.sources.bddk_weekly],['BDDK Aylık Bülten','Sektör bilançosu, mevduat, kârlılık, SYR, TDO ve diğer aylık tablolar.',DATA.sources.bddk_monthly],['Türkiye Bankalar Birliği','Solo ve konsolide banka bazlı mali tablolar, sıralamalar ve arşiv.',DATA.sources.tbb_index],['TBB İstatistiki Raporlar','Çeyreklik, banka/grup bazlı indirilebilir ortak finansal veri setleri.',DATA.sources.tbb_reports],['KAP','Borsada işlem gören bankaların finansal raporları ve dipnotları.',DATA.sources.kap],['TKBB','Katılım bankalarının yayımladığı sektör raporları.',DATA.sources.tkbb]];
 $('sources-grid').innerHTML=sections.map(([name,descr,url])=>`<div class="source-item"><b>${esc(name)}</b><p>${esc(descr)}</p><a href="${esc(url||'#')}" target="_blank" rel="noopener noreferrer">Kaynağı incele ↗</a></div>`).join('');}
function render(){({overview:renderOverview,weekly:renderWeekly,monthly:renderMonthly,banks:renderBanks,compare:renderCompare,quality:renderQuality,sources:renderSources})[active]();}
function csvExport(){let lines=[];let filename='bankscope_export';
 if(active==='weekly'||active==='overview'){lines=DATA.weekly.filter(x=>x.period===(active==='overview'?dates[0]:weekDate));filename='bddk_haftalik_'+(weekDate||dates[0]);}
 else if(active==='monthly'){lines=DATA.monthly;filename='bddk_aylik';}
 else if(active==='banks'){lines=bankRowSet(bankDate,bankScope);filename='banka_finansallari_'+bankDate;}
 else if(active==='compare'){lines=bankRowSet(compDate,compScope).filter(x=>selectedBanks.has(x.bank_id));filename='banka_karsilastirma';}
 else{alert('Bu sayfada sayısal veri dışa aktarılamıyor.');return;}
 if(!lines.length){alert('İndirilecek doğrulanmış veri bulunmuyor.');return}
 const fields=Object.keys(lines[0]);const quote=x=>{let s=String(x??'');return /[;\n\r"]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s};
 const csv='\uFEFF'+[fields.join(';'),...lines.map(x=>fields.map(k=>quote(x[k])).join(';'))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'}));const a=document.createElement('a');a.href=url;a.download=filename+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function init(){
 fillOptions('week-date',dates);fillOptions('bank-period',bankPeriods);fillOptions('compare-period',bankPeriods);
 const q=DATA.quality||{};$('last-updated').textContent='Doğrulanmış son kesit: '+dateText(dates[0]);
 $('alert-message').textContent='Haftalık kredi kesiti doğrulandı; aylık tablolar ve 10 bankanın finansalları henüz eksik. Eksik alanlara tahmini değer konulmadı.';
 document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>togglePage(b.dataset.page)));
 document.querySelectorAll('[data-target]').forEach(b=>b.addEventListener('click',()=>togglePage(b.dataset.target)));
 $('showQuality').addEventListener('click',()=>togglePage('quality'));
 $('print').addEventListener('click',()=>window.print());$('export').addEventListener('click',csvExport);
 $('week-date').addEventListener('change',e=>{weekDate=e.target.value;renderWeekly()});
 $('week-currency').addEventListener('change',e=>{curr=e.target.value;renderWeekly()});
 $('week-search').addEventListener('input',e=>{weekSearch=e.target.value;renderWeekly();$('week-search').focus()});
 $('bank-period').addEventListener('change',e=>{bankDate=e.target.value;renderBanks()});
 $('bank-scope').addEventListener('change',e=>{bankScope=e.target.value;renderBanks()});
 $('compare-period').addEventListener('change',e=>{compDate=e.target.value;selectedBanks=new Set();renderCompare()});
 $('compare-scope').addEventListener('change',e=>{compScope=e.target.value;selectedBanks=new Set();renderCompare()});
 $('compare-metric').addEventListener('change',e=>{compMetric=e.target.value;renderCompare()});
 togglePage(location.hash?.slice(1)||'overview');
}
init();
})();
