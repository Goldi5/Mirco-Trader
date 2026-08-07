function renderSpecTab(specDepots, specKeys, specData) {
  const catOrder = ['index','crypto','lev-bull','lev-bear','inverse','volatility','commodity','meme','ai','ev','biotech','space'];
  const catNames = {
    'index':'📊 Indizes','crypto':'₿ Crypto','lev-bull':'📈 Lev. Bull (3x)','lev-bear':'📉 Lev. Bear (-3x)',
    'inverse':'🔻 Inverse','volatility':'🌪️ Volatility','commodity':'🛢️ Commodity','meme':'🎮 Meme','ai':'🤖 AI',
    'ev':'🚗 EV','biotech':'🧬 Biotech','space':'🚀 Space'
  };
  const catColors = {
    'index':'#06b6d4','crypto':'#f59e0b','lev-bull':'#16a34a','lev-bear':'#dc2626',
    'inverse':'#8b5cf6','volatility':'#ea580c','commodity':'#84cc16','meme':'#d946ef',
    'ai':'#3b82f6','ev':'#06b6d4','biotech':'#6366f1','space':'#f97316'
  };
  const specTotal = specDepots.reduce((s, sd) => s + (sd.wert || 0), 0);
  const specInvest = specDepots.reduce((s, sd) => s + (sd.start || 100), 0);
  const specRend = specInvest > 0 ? ((specTotal / specInvest) - 1) * 100 : 0;
  const specBest = specDepots.length ? specDepots.reduce((a,b) => (a.wert||0)/a.start > (b.wert||0)/b.start ? a : b) : null;
  const specWorst = specDepots.length ? specDepots.reduce((a,b) => (a.wert||0)/a.start < (b.wert||0)/b.start ? a : b) : null;

  let html = `<div class="spec-subtabs" style="display:flex;gap:2px;margin-bottom:10px">
    <button class="spec-subtab active" onclick="switchSpecTab('spec-overview',this)">📊 Übersicht</button>
    <button class="spec-subtab" onclick="switchSpecTab('spec-positions',this)">💰 Positionen (${specDepots.length})</button>
    <button class="spec-subtab" onclick="switchSpecTab('spec-watchlist',this)">📋 Watchlist (${specKeys.length})</button>
  </div>
  <div id="spec-overview" class="spec-pane active"></div>
  <div id="spec-positions" class="spec-pane"></div>
  <div id="spec-watchlist" class="spec-pane"></div>`;

  // We need to populate panes after they're in the DOM
  setTimeout(() => {
    // Übersicht
    const specOvHtml = `
      <div class="summary-row" style="margin-bottom:10px">
        <div class="stat"><div class="num" style="font-size:18px">$${specTotal.toFixed(0)}</div><div class="lbl">Spec-Gesamtwert</div></div>
        <div class="stat"><div class="num ${specRend >= 0 ? 'positiv' : 'negativ'}" style="font-size:18px">${specRend >= 0 ? '+' : ''}${specRend.toFixed(2)}%</div><div class="lbl">Ø Rendite</div></div>
        <div class="stat"><div class="num" style="font-size:18px">${specDepots.length}</div><div class="lbl">Aktive Pos.</div></div>
        <div class="stat"><div class="num" style="font-size:18px">${specKeys.length}</div><div class="lbl">Beobachtet</div></div>
        ${specBest ? `<div class="stat"><div class="num" style="font-size:13px">${specBest.ticker} <span class="positiv">${((specBest.wert/specBest.start-1)*100).toFixed(1)}%</span></div><div class="lbl">Bester</div></div>` : ''}
        ${specWorst ? `<div class="stat"><div class="num" style="font-size:13px">${specWorst.ticker} <span class="negativ">${((specWorst.wert/specWorst.start-1)*100).toFixed(1)}%</span></div><div class="lbl">Schlechtester</div></div>` : ''}
      </div>
      <div class="two-col">
        <div class="glass" style="padding:10px 12px">
          <h4 style="font-size:11px;font-weight:600;color:var(--green);margin-bottom:6px">📈 Top-Gewinner (24h)</h4>
          ${(() => {
            const items = Object.entries(specData).sort((a,b) => (b[1].tagesrendite||0) - (a[1].tagesrendite||0));
            const maxGain = Math.max(...items.slice(0,5).map(([_,v]) => v.tagesrendite), 5);
            return '<div style="display:flex;flex-direction:column;gap:3px">' + items.slice(0,5).map(([t,v]) => {
              const pct = Math.min(v.tagesrendite / maxGain * 100, 100);
              return `<div style="display:flex;align-items:center;gap:6px;font-size:11px">
                <b style="width:38px">${t}</b>
                <div style="flex:1;height:14px;background:rgba(0,0,0,0.04);border-radius:4px;overflow:hidden">
                  <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,var(--green),rgba(52,211,153,0.7));border-radius:4px"></div>
                </div>
                <span style="color:var(--green);font-weight:500;width:48px;text-align:right">+${v.tagesrendite.toFixed(1)}%</span>
                <span style="color:var(--text-dim);width:40px;text-align:right">$${v.aktuell.toFixed(2)}</span>
              </div>`;
            }).join('') + '</div>';
          })()}
        </div>
        <div class="glass" style="padding:10px 12px">
          <h4 style="font-size:11px;font-weight:600;color:var(--red);margin-bottom:6px">📉 Top-Verlierer (24h)</h4>
          ${(() => {
            const items = Object.entries(specData).sort((a,b) => (a[1].tagesrendite||0) - (b[1].tagesrendite||0));
            const maxLoss = Math.max(...items.slice(0,5).map(([_,v]) => Math.abs(v.tagesrendite)), 5);
            return '<div style="display:flex;flex-direction:column;gap:3px">' + items.slice(0,5).map(([t,v]) => {
              const pct = Math.min(Math.abs(v.tagesrendite) / maxLoss * 100, 100);
              return `<div style="display:flex;align-items:center;gap:6px;font-size:11px">
                <b style="width:38px">${t}</b>
                <div style="flex:1;height:14px;background:rgba(0,0,0,0.04);border-radius:4px;overflow:hidden">
                  <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,var(--red),rgba(248,113,113,0.7));border-radius:4px"></div>
                </div>
                <span style="color:var(--red);font-weight:500;width:48px;text-align:right">${v.tagesrendite.toFixed(1)}%</span>
                <span style="color:var(--text-dim);width:40px;text-align:right">$${v.aktuell.toFixed(2)}</span>
              </div>`;
            }).join('') + '</div>';
          })()}
        </div>
      </div>`;
    const specOv = document.getElementById("spec-overview");
    if (specOv) specOv.insertAdjacentHTML("beforeend", specOvHtml);

    // Positionen
    const posPane = document.getElementById("spec-positions");
    if (posPane) {
      if (specDepots.length) {
        posPane.innerHTML = `<div class="grid">${specDepots.map(sd => renderCard(sd, "spec")).join("")}</div>`;
      } else {
        posPane.innerHTML = '<div class="glass" style="color:var(--text-dim)">Noch keine aktiven Spec-Positionen.</div>';
      }
    }

    // Watchlist
    const watchPane = document.getElementById("spec-watchlist");
    if (watchPane) {
      watchPane.innerHTML = `
      <div class="glass" style="padding:8px 12px;margin-bottom:8px">
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          <button class="spec-filter active" data-cat="all" onclick="filterSpecWatch('all',this)">Alle (${specKeys.length})</button>
          ${catOrder.map(cat => {
            const count = Object.values(specData).filter(v => v.kategorie === cat).length;
            if (!count) return '';
            return `<button class="spec-filter" data-cat="${cat}" onclick="filterSpecWatch('${cat}',this)" style="border-color:${catColors[cat]||'#94a3b8'}">${catNames[cat]||cat} (${count})</button>`;
          }).join('')}
        </div>
      </div>
      <div class="glass" style="overflow-x:auto;padding:0">
        <table class="spec-watch-tbl" id="specWatchTbl">
          <thead><tr>
            <th onclick="sortSpecWatch('ticker')" class="sortable" style="padding:5px 6px;font-size:10px">Ticker</th>
            <th onclick="sortSpecWatch('name')" class="sortable" style="padding:5px 6px;font-size:10px">Name</th>
            <th onclick="sortSpecWatch('aktuell')" class="sortable" style="padding:5px 6px;font-size:10px">Preis</th>
            <th onclick="sortSpecWatch('tagesrendite')" class="sortable" style="padding:5px 6px;font-size:10px">24h</th>
            <th onclick="sortSpecWatch('woche')" class="sortable" style="padding:5px 6px;font-size:10px">5T</th>
            <th onclick="sortSpecWatch('volatilitaet')" class="sortable" style="padding:5px 6px;font-size:10px">Vola</th>
            <th onclick="sortSpecWatch('hebel')" class="sortable" style="padding:5px 6px;font-size:10px">Hebel</th>
            <th onclick="sortSpecWatch('kategorie')" class="sortable" style="padding:5px 6px;font-size:10px">Kat.</th>
          </tr></thead>
          <tbody id="specWatchBody">
            ${Object.entries(specData).sort((a,b) => (b[1].tagesrendite||0) - (a[1].tagesrendite||0)).map(([t, v]) => {
              const rendCls = v.tagesrendite > 1 ? "positiv" : v.tagesrendite < -1 ? "negativ" : "";
              const wocheCls = (v.woche||0) > 2 ? "positiv" : (v.woche||0) < -2 ? "negativ" : "";
              const amp = v.tagesrendite > 3 ? '🟢' : v.tagesrendite > 0.5 ? '🟡' : v.tagesrendite > -0.5 ? '⚪' : v.tagesrendite > -3 ? '🟠' : '🔴';
              const trend = (v.woche||0) > 1 ? '↗' : (v.woche||0) < -1 ? '↘' : '➡';
              const bgTint = v.tagesrendite > 5 ? 'rgba(52,211,153,0.06)' : v.tagesrendite < -5 ? 'rgba(248,113,113,0.06)' : '';
              return `<tr class="spec-row" data-cat="${v.kategorie||'?'}" style="cursor:pointer;${bgTint ? 'background:'+bgTint : ''}" onclick="showTickerChart('${t}','specChart_${t}','specRow_${t}')">
                <td><b>${amp} ${t}</b></td>
                <td style="color:var(--text-dim);font-size:10px;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(v.name||'')}">${esc(v.name||'')}</td>
                <td>$${(v.aktuell||0).toFixed(2)}</td>
                <td class="${rendCls}" style="font-weight:500">${v.tagesrendite >= 0 ? '+' : ''}${(v.tagesrendite||0).toFixed(1)}%</td>
                <td class="${wocheCls}" style="font-size:10px">${trend} ${(v.woche||0) >= 0 ? '+' : ''}${(v.woche||0).toFixed(1)}%</td>
                <td style="color:var(--text-dim);font-size:10px">${(v.volatilitaet||0).toFixed(0)}%</td>
                <td style="font-size:10px">${v.hebel > 1 ? v.hebel+'x' : v.hebel < -1 ? Math.abs(v.hebel)+'x Short' : '-'}</td>
                <td><span class="badge" style="font-size:9px;background:${catColors[v.kategorie]||'#94a3b8'}20;color:${catColors[v.kategorie]||'#64748b'};padding:1px 6px;border-radius:4px">${catNames[v.kategorie]||v.kategorie||'?'}</span></td>
              </tr><tr id="specRow_${t}" style="display:none"><td colspan="8" style="padding:0"><canvas id="specChart_${t}" height="70"></canvas></td></tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>`;
    }
  }, 50);
  return html;
}