p = 'dashboard.html'
s = open(p, encoding='utf-8').read()

old = '''function histTable(liste, limit) {
  if (!liste || !liste.length) return '<div style="color:var(--text-dim);font-size:12px">Keine Trades in diesem Zeitraum</div>';
  const rows = liste.slice(0, limit || 20).map(t => {
    const typ = t.typ || t.aktion || '?';
    const farbe = String(typ).toLowerCase().includes("kauf") || String(typ).toLowerCase() === "buy" ? "🟢" : "🔴";
    const menge = (t.menge || 0).toFixed(2);
    const preis = t.preis ? "$" + Number(t.preis).toFixed(2) : "-";
    return `<tr>
      <td style="white-space:nowrap">${t.zeit ? String(t.zeit).slice(0,16).replace("T"," ") : "-"}</td>
      <td><b>${esc(t.depot_label || "")}</b></td>
      <td>${farbe} ${esc(typ)}</td>
      <td><b>${esc(t.ticker || "")}</b></td>
      <td>${menge}</td>
      <td>${preis}</td>
      <td style="color:var(--text-dim);max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(t.grund || "")}">${esc(t.grund || "")}</td>
    </tr>`;
  }).join('');
  return `<div style="max-height:260px;overflow-y:auto"><table style="font-size:11px"><tr>
    <th>Datum</th><th>Depot</th><th>Typ</th><th>Ticker</th><th>Menge</th><th>Preis</th><th>Grund</th>
  </tr>${rows}</table></div>`;
}'''

new = '''// ── Zentrale Typ→Farbe (konsistent bei allen Kategorien) ──
function typStyle(typ) {
  const t = String(typ || '').toLowerCase();
  if (t.includes('kauf') || t === 'buy' || t.includes('long')) {
    return { color: 'var(--green)', bg: 'rgba(48,209,88,0.14)', icon: '🟢', label: 'KAUFEN' };
  }
  if (t.includes('verkauf') || t === 'sell' || t.includes('short')) {
    return { color: 'var(--red)', bg: 'rgba(255,69,58,0.14)', icon: '🔴', label: 'VERKAUFEN' };
  }
  if (t.includes('blockiert') || t.includes('blocked')) {
    return { color: 'var(--orange)', bg: 'rgba(255,159,10,0.14)', icon: '🛑', label: 'BLOCKIERT' };
  }
  return { color: 'var(--text-dim)', bg: 'rgba(142,142,147,0.14)', icon: '⚪', label: String(typ || '?').toUpperCase() };
}

function histTable(liste, limit) {
  if (!liste || !liste.length) return '<div style="color:var(--text-dim);font-size:12px">Keine Trades in diesem Zeitraum</div>';
  const rows = liste.slice(0, limit || 20).map(t => {
    const typ = t.typ || t.aktion || '?';
    const ts = typStyle(typ);
    const menge = (t.menge || 0).toFixed(2);
    const preis = t.preis ? "$" + Number(t.preis).toFixed(2) : "-";
    const tag = `<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:.03em;color:${ts.color};background:${ts.bg}">${ts.icon} ${ts.label}</span>`;
    return `<tr>
      <td style="white-space:nowrap">${t.zeit ? String(t.zeit).slice(0,16).replace("T"," ") : "-"}</td>
      <td><b>${esc(t.depot_label || "")}</b></td>
      <td>${tag}</td>
      <td><b>${esc(t.ticker || "")}</b></td>
      <td>${menge}</td>
      <td>${preis}</td>
      <td style="color:var(--text-dim);max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(t.grund || "")}">${esc(t.grund || "")}</td>
    </tr>`;
  }).join('');
  return `<div style="max-height:260px;overflow-y:auto"><table style="font-size:11px"><tr>
    <th>Datum</th><th>Depot</th><th>Typ</th><th>Ticker</th><th>Menge</th><th>Preis</th><th>Grund</th>
  </tr>${rows}</table></div>`;
}'''

assert old in s, 'histTable nicht gefunden (whitespace?)'
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('histTable: konsistente Farb-Tags eingebaut')
