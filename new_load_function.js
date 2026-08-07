async function load() {
  try {
    const r = await fetch(API);
    const d = await r.json();
    savedData = d;

    document.getElementById("updateTime").textContent = formatDeutsch(d.aktualisiert) + " · " +
      d.depots.length + " Aktien · " + (d.etf_depots||[]).length + " ETF · " + d.spec_depots.length + " Spek";

    // ── Kategorien ──
    const aktienTotal = d.depots.reduce((s,x) => s + x.wert, 0);
    const aktienInvest = d.depots.reduce((s,x) => s + x.start, 0);
    const aktienRendite = aktienInvest > 0 ? ((aktienTotal - aktienInvest) / aktienInvest * 100) : 0;
    const etfTotal = (d.etf_depots||[]).reduce((s,x) => s + x.wert, 0);
    const etfInvest = (d.etf_depots||[]).reduce((s,x) => s + x.start, 0);
    const etfRendite = etfInvest > 0 ? ((etfTotal - etfInvest) / etfInvest * 100) : 0;
    const specTotal = d.spec_depots.reduce((s,x) => s + x.wert, 0);
    const specInvest = d.spec_depots.reduce((s,x) => s + (x.start||100), 0);
    const specRendite = specInvest > 0 ? ((specTotal - specInvest) / specInvest * 100) : 0;
    const total = aktienTotal + etfTotal + specTotal;
    const totalInvest = aktienInvest + etfInvest + specInvest;
    const gesRendite = totalInvest > 0 ? ((total - totalInvest) / totalInvest * 100) : 0;

    // ── Market Status ──
    const mkEl = document.getElementById("marketStatus");
    if (mkEl) {
      const mk = d.markt_status || "unknown";
      const icons = {open: "🟢", pre: "🟡", closed: "🔴", unknown: "⚪"};
      mkEl.innerHTML = `${icons[mk]||'⚪'} ${d.markt_label||'?'}`;
    }

    // ── Börsenzeiten ──
    const boEl = document.getElementById("boersenDisplay");
    if (boEl && d.boersen) {
      const labels = {open:"offen", pre:"Voröffnung", closed:"geschlossen"};
      const colors = {open:"\u{1F7E2}", pre:"\u{1F7E1}", closed:"\u{1F534}"};
      boEl.innerHTML = d.boersen.map(b =>
        `<span style="margin-right:6px;white-space:nowrap">${colors[b.status]||''} ${b.flag||''} ${b.name}: <b>${labels[b.status]||b.status}</b> (${b.open}–${b.close})</span>`
      ).join(' · ');
    }

    // ── Notifications ──
    const notifs = d.notifications || [];
    const badge = document.getElementById("notifBadge");
    if (badge) {
      badge.style.display = notifs.length ? "inline" : "none";
      if (notifs.length) badge.title = notifs.map(n => n.text).join(" | ");
    }

    // ══════════════════════════════════════════════════════
    // 📊 ÜBERSICHT (3 Kategorien)
    // ══════════════════════════════════════════════════════
    const best = d.depots.reduce((a,b) => a.rendite > b.rendite ? a : b);
    const worst = d.depots.reduce((a,b) => a.rendite < b.rendite ? a : b);
    const active = d.depots.filter(x => x.positionen > 0).length;
    const trades = d.depots.reduce((s,x) => s + x.trades, 0);

    document.getElementById("panel-overview").innerHTML = `
      <div class="search-box">
        <input type="text" id="tickerSearch" placeholder="🔍 Ticker suchen (z.B. AAPL, LCID...)" onkeyup="searchTicker(this.value)">
        <div id="searchResults" class="search-results"></div>
      </div>
      <div class="summary-row">
        <div class="stat"><div class="num" style="font-size:18px">$${total.toFixed(0)}</div><div class="lbl">Gesamtwert</div></div>
        <div class="stat"><div class="num ${gesRendite>=0?'positiv':'negativ'}">${gesRendite>=0?'+':''}${gesRendite.toFixed(2)}%</div><div class="lbl">Gesamt-Rendite</div></div>
        <div class="stat"><div class="num ${(total-totalInvest)>=0?'positiv':'negativ'}">${(total-totalInvest)>=0?'+':''}$${(total-totalInvest).toFixed(0)}</div><div class="lbl">Gewinn/Verlust</div></div>
        <div class="stat"><div class="num">${active}</div><div class="lbl">Akt. Aktien</div></div>
        <div class="stat"><div class="num">${(d.etf_depots||[]).filter(x=>x.positionen>0).length}</div><div class="lbl">Akt. ETF</div></div>
        <div class="stat"><div class="num">${(d.spec_depots||[]).filter(x=>x.shares>0).length}</div><div class="lbl">Akt. Spec</div></div>
      </div>

      <!-- Drei Kategorie-Kacheln -->
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0">
        <div class="glass" style="padding:14px">
          <div style="font-size:13px;font-weight:600;margin-bottom:8px">📈 Aktien (${d.depots.length} Depots)</div>
          <div style="font-size:22px;font-weight:700">$${aktienTotal.toFixed(0)}</div>
          <div style="font-size:13px;margin:4px 0"><span class="${aktienRendite>=0?'positiv':'negativ'}">${aktienRendite>=0?'+':''}${aktienRendite.toFixed(2)}%</span> <span style="color:var(--text-dim)">· ${active} aktiv</span></div>
          <div style="height:6px;background:var(--card-border);border-radius:3px;margin-top:8px;overflow:hidden">
            <div style="height:100%;width:${Math.min(100,Math.max(0,aktienRendite/3+50))}%;background:${aktienRendite>=0?'#22c55e':'#ef4444'};border-radius:3px"></div>
          </div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:6px">Bester: Risk ${best.risk} <span class="positiv">${best.rendite.toFixed(1)}%</span> · Schlecht.: Risk ${worst.risk} <span class="negativ">${worst.rendite.toFixed(1)}%</span></div>
        </div>
        <div class="glass" style="padding:14px;cursor:pointer" onclick="showTab('etf')">
          <div style="font-size:13px;font-weight:600;margin-bottom:8px">📦 ETF (${(d.etf_depots||[]).length} Depots)</div>
          <div style="font-size:22px;font-weight:700">$${etfTotal.toFixed(0)}</div>
          <div style="font-size:13px;margin:4px 0"><span class="${etfRendite>=0?'positiv':'negativ'}">${etfRendite>=0?'+':''}${etfRendite.toFixed(2)}%</span> <span style="color:var(--text-dim)">· ${(d.etf_depots||[]).length} aktiv</span></div>
          <div style="height:6px;background:var(--card-border);border-radius:3px;margin-top:8px;overflow:hidden">
            <div style="height:100%;width:${Math.min(100,Math.max(0,etfRendite/3+50))}%;background:${etfRendite>=0?'#22c55e':'#ef4444'};border-radius:3px"></div>
          </div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:6px">Trades: ${(d.etf_depots||[]).reduce((s,x)=>s+x.trades,0)}</div>
        </div>
        <div class="glass" style="padding:14px;cursor:pointer" onclick="showTab('spec')">
          <div style="font-size:13px;font-weight:600;margin-bottom:8px">🔥 Spekulation (${d.spec_depots.length} aktiv)</div>
          <div style="font-size:22px;font-weight:700">$${specTotal.toFixed(0)}</div>
          <div style="font-size:13px;margin:4px 0"><span class="${specRendite>=0?'positiv':'negativ'}">${specRendite>=0?'+':''}${specRendite.toFixed(2)}%</span> <span style="color:var(--text-dim)">· ${d.spec_depots.filter(x=>x.shares>0).length} in Position</span></div>
          <div style="height:6px;background:var(--card-border);border-radius:3px;margin-top:8px;overflow:hidden">
            <div style="height:100%;width:${Math.min(100,Math.max(0,specRendite/3+50))}%;background:${specRendite>=0?'#22c55e':'#ef4444'};border-radius:3px"></div>
          </div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:6px">Trades: ${d.spec_depots.reduce((s,x)=>s+x.trades.length,0)}</div>
        </div>
      </div>

      <!-- Depot-Ranking-Tabelle (nur Aktien) -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div class="glass">
          <h3 style="font-size:13px;font-weight:600;margin-bottom:8px">🏆 Aktien-Ranking</h3>
          <div style="overflow-x:auto">
          <table class="ranking-tbl">
            <tr><th>#</th><th>Risk</th><th>Rendite</th><th>Wert</th><th>Pos</th><th>DD</th></tr>
            ${d.ranking.map(r => {
              const dep = d.depots.find(x=>x.risk==r.risk);
              return `<tr onclick="showDepot(JSON.parse('${esc(JSON.stringify(dep))}'),'main')" style="cursor:pointer">
                <td class="rank-nr${r.platz<=3?' top3':''}">${r.platz}.</td>
                <td><b>Risk ${r.risk}</b></td>
                <td class="${r.rendite>=0?'positiv':'negativ'}">${r.rendite>=0?'+':''}${r.rendite.toFixed(2)}%</td>
                <td>$${r.wert.toFixed(2)}</td>
                <td>${r.positionen}</td>
                <td class="negativ">${Math.abs(r.max_dd||0).toFixed(1)}%</td>
              </tr>`;
            }).join('')}
          </table>
          </div>
        </div>
        <div class="glass">
          <h3 style="font-size:13px;font-weight:600;margin-bottom:8px">📊 ETF-Übersicht</h3>
          <div style="overflow-x:auto">
          <table class="ranking-tbl">
            <tr><th>Risk</th><th>Stufe</th><th>Wert</th><th>Rendite</th><th>Pos</th></tr>
            ${(d.etf_depots||[]).map(e => {
              const stufen = ['Geldmarkt','Anleihen','Markt','Sektor','Thema','Hebel'];
              const stufe = Math.min(5, Math.floor(e.risk/20));
              return `<tr onclick="showTab('etf')" style="cursor:pointer">
                <td><b>${e.risk}</b></td>
                <td style="font-size:11px;color:var(--text-dim)">${stufen[stufe]}</td>
                <td>$${e.wert.toFixed(2)}</td>
                <td class="${e.rendite>=0?'positiv':'negativ'}">${e.rendite>=0?'+':''}${e.rendite.toFixed(2)}%</td>
                <td>${e.positionen}</td>
              </tr>`;
            }).join('')}
          </table>
          </div>
        </div>
      </div>
    `;

    // ══════════════════════════════════════════════════════
    // 📈 AKTIEN TAB (Einzeldepots)
    // ══════════════════════════════════════════════════════
    const stocksHtml = d.depots.map(dep => renderCard(dep, "stocks")).join("");
    document.getElementById("panel-stocks").innerHTML = `
      <div class="grid">${stocksHtml}</div>
    `;

    // ══════════════════════════════════════════════════════
    // 📦 ETF TAB
    // ══════════════════════════════════════════════════════
    const etfStufen = ['Geldmarkt','Anleihen','Breiter Markt','Sektor/Rohstoff','Thema/Innovation','Gehebelt'];
    const etfHtml = (d.etf_depots||[]).map(e => {
      const stufe = Math.min(5, Math.floor(e.risk/20));
      const farbe = e.rendite >= 0 ? 'positiv' : 'negativ';
      const pos_list = e.positions||[];
      return `<div class="glass" style="position:relative;cursor:pointer;padding:14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <div><b style="font-size:15px">Risk ${e.risk}</b> <span style="font-size:11px;color:var(--text-dim)">${etfStufen[stufe]}</span></div>
          <div class="${farbe}" style="font-weight:600">${e.rendite>=0?'+':''}${e.rendite.toFixed(2)}%</div>
        </div>
        <div style="display:flex;gap:16px;font-size:12px;margin-bottom:8px">
          <span>$${e.wert.toFixed(2)} <span style="color:var(--text-dim)">von $${e.start}</span></span>
          <span>${e.positionen} Pos · ${e.trades} Trades</span>
          <span class="${e.max_dd>10?'negativ':'positiv'}">DD: ${e.max_dd.toFixed(1)}%</span>
        </div>
        ${pos_list.length ? `<div style="border-top:1px solid var(--card-border);padding-top:6px;font-size:11px">
          ${pos_list.map(p => {
            const pName = p.name||p.ticker;
            return `<div style="display:flex;justify-content:space-between;padding:2px 0">
              <span><b>${p.ticker}</b> ${pName.substring(0,28)}</span>
              <span>${p.shares}st @ $${p.avg_price?.toFixed(2)||'?'}</span>
            </div>`;
          }).join('')}
        </div>` : ''}
        ${e.gesperrt ? '<div style="margin-top:6px;font-size:11px;color:#dc2626">🔒 Gesperrt (Drawdown-Limit)</div>' : ''}
        <div style="height:4px;background:var(--card-border);border-radius:2px;margin-top:8px;overflow:hidden">
          <div style="height:100%;width:${Math.min(100,Math.max(0,e.rendite/3+50))}%;background:${e.rendite>=0?'#22c55e':'#ef4444'};border-radius:2px"></div>
        </div>
      </div>`;
    }).join('');

    document.getElementById("panel-etf").innerHTML = `
      <div class="summary-row" style="margin-bottom:10px">
        <div class="stat"><div class="num">$${etfTotal.toFixed(0)}</div><div class="lbl">ETF-Gesamtwert</div></div>
        <div class="stat"><div class="num ${etfRendite>=0?'positiv':'negativ'}">${etfRendite>=0?'+':''}${etfRendite.toFixed(2)}%</div><div class="lbl">ETF-Rendite</div></div>
        <div class="stat"><div class="num">${(d.etf_depots||[]).length}</div><div class="lbl">ETF-Depots</div></div>
      </div>
      <div class="grid">${etfHtml}</div>
    `;

    // ══════════════════════════════════════════════════════
    // 📊 ANALYSE TAB (CSS-Bars statt Chart.js)
    // ══════════════════════════════════════════════════════
    let analyseHtml = `<div class="summary-row" style="margin-bottom:10px">
      <div class="stat"><div class="num">$${total.toFixed(0)}</div><div class="lbl">Gesamtwert</div></div>
      <div class="stat"><div class="num ${gesRendite>=0?'positiv':'negativ'}">${gesRendite>=0?'+':''}${gesRendite.toFixed(2)}%</div><div class="lbl">Gesamt-Rendite</div></div>
      <div class="stat"><div class="num">${trades + (d.etf_depots||[]).reduce((s,x)=>s+x.trades,0) + d.spec_depots.reduce((s,x)=>s+x.trades.length,0)}</div><div class="lbl">Trades Total</div></div>
    </div>`;

    // Analyse-Daten laden (falls verfügbar)
    try {
      const ar = await fetch("/api/analysis");
      if (ar.ok) {
        const aData = await ar.json();
        // Aktien-Analyse
        const ak = aData.aktien || {};
        if (ak.total_trades) {
          analyseHtml += cssBar("📈 Aktien", ak.total_trades, ak.rendite, ak.top_ticker||[], ak.grund_stats||{});
        }
        // ETF-Analyse
        const et = aData.etf || {};
        if (et.total_trades) {
          analyseHtml += cssBar("📦 ETF", et.total_trades, et.rendite, et.top_ticker||[], et.grund_stats||{});
        }
        // Spekulation-Analyse
        const sp = aData.spekulation || {};
        if (sp.total_trades) {
          analyseHtml += cssBar("🔥 Spekulation", sp.total_trades, sp.rendite, sp.top_ticker||[], sp.grund_stats||{});
        }
      }
    } catch(e) {
      analyseHtml += `<div class="glass" style="padding:12px;font-size:12px;color:var(--text-dim)">Analyse-Daten noch nicht verfügbar (erster Lauf)</div>`;
    }

    document.getElementById("panel-analyse").innerHTML = analyseHtml;

    // ══════════════════════════════════════════════════════
    // 🔥 SPEKULATION TAB (unverändert)
    // ══════════════════════════════════════════════════════
    const specDepots = d.spec_depots || [];
    const specKeys = Object.keys(d.spec_watch||{});
    const specWatchData = d.spec_watch||{};
    
    document.getElementById("panel-spec").innerHTML = renderSpecTab(specDepots, specKeys, specWatchData);

    // ══════════════════════════════════════════════════════
    // 📰 NEWS TAB (unverändert)
    // ══════════════════════════════════════════════════════
    const newsEl = document.getElementById("newsBox");
    if (newsEl && d.news && d.news.length) {
      newsEl.innerHTML = d.news.map(n => {
        const link = n.link || n.url || "#";
        const source = n.source || n.quelle || "Unbekannt";
        const time = n.zeit || n.pubDate || "";
        return `<div class="news-item">
          <a href="${link}" target="_blank" rel="noopener" style="text-decoration:none;color:inherit">
            <div class="news-title">${n.titel || n.title || "?"}</div>
            <div class="news-source">${source} · ${time.substring(0,10)}</div>
          </a>
        </div>`;
      }).join('');
    }

    // ══════════════════════════════════════════════════════
    // 🤖 KI-LOG TAB (unverändert)
    // ══════════════════════════════════════════════════════
    const kiEl = document.getElementById("kiBox");
    if (kiEl && d.ki_log && d.ki_log.length) {
      kiEl.innerHTML =
        '<table class="ki-table"><thead><tr>' +
        '<th>Zeit</th><th>Score</th><th>News-Ticker</th><th>Grund</th>' +
        '<th>Link</th></tr></thead><tbody>' +
        d.ki_log.slice(0, 50).map(e =>
          `<tr>
            <td style="white-space:nowrap">${(e.zeit||'').substring(0,16).replace('T',' ')}</td>
            <td><b>${e.score||e.bewertung||'?'}</b></td>
            <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${e.ticker||e.instrument||'?'}</td>
            <td class="title-col" title="${esc(e.grund||'')}">${e.grund||''}</td>
            <td>${e.link ? `<a href="${e.link}" target="_blank" style="color:var(--accent);text-decoration:none">🔗</a>` : ''}</td>
          </tr>`
        ).join('') +
        '</tbody></table>';
    }

  } catch(e) {
    document.getElementById("panel-overview").innerHTML = '<div class="glass" style="padding:20px;color:#dc2626">Fehler: ' + e.message + '</div>';
  }
}

function cssBar(titel, trades, rendite, topTicker, grundStats) {
  const top = (topTicker||[]).slice(0, 6);
  const gruende = (grundStats||{});
  const grundArr = Object.entries(gruende).slice(0, 6);
  return `<div class="glass" style="margin-bottom:10px;padding:14px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <h3 style="font-size:14px;font-weight:600;margin:0">${titel}</h3>
      <span style="font-size:12px;color:var(--text-dim)">${trades} Trades · ${rendite.toFixed(2)}% Rendite</span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">Meistgehandelte Ticker</div>
        ${top.map(t => {
          const maxTrades = Math.max(...top.map(x=>x[1].trades), 1);
          const w = (t[1].trades / maxTrades * 100).toFixed(0);
          return `<div style="display:flex;align-items:center;margin:2px 0;font-size:11px">
            <span style="width:60px;font-weight:500">${t[0]}</span>
            <div style="height:14px;width:${w}%;background:var(--accent);border-radius:3px;min-width:4px"></div>
            <span style="margin-left:6px;color:var(--text-dim)">${t[1].trades}</span>
          </div>`;
        }).join('')}
      </div>
      <div>
        <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px">Trades nach Grund</div>
        ${grundArr.map(([g, n]) => {
          const maxG = Math.max(...grundArr.map(x=>x[1]), 1);
          const w = (n / maxG * 100).toFixed(0);
          return `<div style="display:flex;align-items:center;margin:2px 0;font-size:11px">
            <span style="width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${g}</span>
            <div style="height:14px;width:${w}%;background:#a78bfa;border-radius:3px;min-width:4px"></div>
            <span style="margin-left:6px;color:var(--text-dim)">${n}</span>
          </div>`;
        }).join('')}
      </div>
    </div>
  </div>`;
}