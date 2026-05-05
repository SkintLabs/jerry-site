const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// Fonts
const kenjaku   = fs.readFileSync(path.join(__dirname, '../assets/Kenjaku DEMO.otf')).toString('base64');
const neonFuture = fs.readFileSync(path.join(__dirname, '../wonderwallai-site/assets/NeonFuture.ttf')).toString('base64');
const retroByte  = fs.readFileSync(path.join(__dirname, 'docs/assets/fonts/RetroByte.ttf')).toString('base64');

const meteoriteBg = `
  repeating-linear-gradient(58deg,  rgba(170,179,194,0.04) 0px, rgba(170,179,194,0.04) 1px, transparent 1px, transparent 14px),
  repeating-linear-gradient(-62deg, rgba(170,179,194,0.03) 0px, rgba(170,179,194,0.03) 1px, transparent 1px, transparent 19px),
  repeating-linear-gradient(12deg,  rgba(170,179,194,0.02) 0px, rgba(170,179,194,0.02) 1px, transparent 1px, transparent 33px),
  radial-gradient(ellipse at 15% 20%, rgba(90,60,55,0.3),  transparent 50%),
  radial-gradient(ellipse at 85% 80%, rgba(60,44,38,0.35), transparent 55%),
  radial-gradient(ellipse at 50% 50%, rgba(30,18,14,0.65), transparent 70%),
  #0c0b0a
`;

// Jerry robot SVG — inline, terracotta/gold palette
const jerryRobot = `<svg width="320" height="430" viewBox="0 0 120 160" fill="none" xmlns="http://www.w3.org/2000/svg">
  <line x1="60" y1="10" x2="60" y2="26" stroke="#c1666b" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="60" cy="7" r="4" fill="#d4943a" opacity="0.9"/>
  <circle cx="60" cy="7" r="7" fill="#d4943a" opacity="0.15"/>
  <rect x="28" y="26" width="64" height="50" rx="10" fill="#1a1714" stroke="#a84e52" stroke-width="1.5" stroke-opacity="0.8"/>
  <rect x="38" y="38" width="16" height="12" rx="3" fill="#d4943a" opacity="0.95"/>
  <rect x="66" y="38" width="16" height="12" rx="3" fill="#d4943a" opacity="0.95"/>
  <rect x="44" y="41" width="5" height="6" rx="1.5" fill="#0a0908"/>
  <rect x="72" y="41" width="5" height="6" rx="1.5" fill="#0a0908"/>
  <rect x="40" y="58" width="40" height="7" rx="3.5" fill="#c1666b" opacity="0.4"/>
  <rect x="44" y="59.5" width="6" height="4" rx="1" fill="#c1666b" opacity="0.8"/>
  <rect x="53" y="59.5" width="6" height="4" rx="1" fill="#c1666b" opacity="0.8"/>
  <rect x="62" y="59.5" width="6" height="4" rx="1" fill="#c1666b" opacity="0.8"/>
  <rect x="71" y="59.5" width="6" height="4" rx="1" fill="#c1666b" opacity="0.8"/>
  <rect x="52" y="76" width="16" height="8" rx="3" fill="#141210" stroke="#c1666b" stroke-width="1" stroke-opacity="0.4"/>
  <rect x="20" y="84" width="80" height="52" rx="10" fill="#141210" stroke="#c1666b" stroke-width="1.5" stroke-opacity="0.5"/>
  <rect x="32" y="94" width="56" height="30" rx="5" fill="#1a1714" stroke="#d4943a" stroke-width="0.8" stroke-opacity="0.35"/>
  <rect x="34" y="97" width="52" height="24" rx="4" fill="#d4943a" opacity="0.14"/>
  <rect x="34" y="97" width="52" height="24" rx="4" stroke="#d4943a" stroke-width="1" stroke-opacity="0.6"/>
  <text x="60" y="113" font-family="monospace" font-size="9" fill="#d4943a" text-anchor="middle" opacity="0.95" letter-spacing="2" font-weight="bold">JERRY</text>
  <rect x="3" y="88" width="17" height="34" rx="7" fill="#141210" stroke="#c1666b" stroke-width="1.2" stroke-opacity="0.4"/>
  <rect x="100" y="88" width="17" height="34" rx="7" fill="#141210" stroke="#c1666b" stroke-width="1.2" stroke-opacity="0.4"/>
  <circle cx="11" cy="127" r="4" fill="#1a1714" stroke="#c1666b" stroke-width="1" stroke-opacity="0.5"/>
  <circle cx="109" cy="127" r="4" fill="#1a1714" stroke="#c1666b" stroke-width="1" stroke-opacity="0.5"/>
  <rect x="35" y="136" width="19" height="20" rx="5" fill="#141210" stroke="#c1666b" stroke-width="1.2" stroke-opacity="0.4"/>
  <rect x="66" y="136" width="19" height="20" rx="5" fill="#141210" stroke="#c1666b" stroke-width="1.2" stroke-opacity="0.4"/>
  <rect x="31" y="152" width="27" height="8" rx="4" fill="#1a1714" stroke="#c1666b" stroke-width="1" stroke-opacity="0.4"/>
  <rect x="62" y="152" width="27" height="8" rx="4" fill="#1a1714" stroke="#c1666b" stroke-width="1" stroke-opacity="0.4"/>
  <rect x="24" y="44" width="72" height="9" rx="1.5" fill="#3a3530" opacity="0.85" transform="rotate(-4 60 48)"/>
  <circle cx="34" cy="31" r="3" fill="#252220" stroke="#c1666b" stroke-width="0.8" stroke-opacity="0.5"/>
  <line x1="32" y1="31" x2="36" y2="31" stroke="#c1666b" stroke-width="0.7" stroke-opacity="0.4"/>
  <line x1="34" y1="29" x2="34" y2="33" stroke="#c1666b" stroke-width="0.7" stroke-opacity="0.4"/>
  <circle cx="86" cy="31" r="3" fill="#252220" stroke="#c1666b" stroke-width="0.8" stroke-opacity="0.5"/>
  <line x1="84" y1="31" x2="88" y2="31" stroke="#c1666b" stroke-width="0.7" stroke-opacity="0.4"/>
  <line x1="86" y1="29" x2="86" y2="33" stroke="#c1666b" stroke-width="0.7" stroke-opacity="0.4"/>
  <path d="M48 136 Q44 142 47 148 Q50 154 46 158" stroke="#d4943a" stroke-width="1" fill="none" opacity="0.4" stroke-linecap="round"/>
</svg>`;

const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
@font-face { font-family:'Kenjaku';    src:url(data:font/opentype;base64,${kenjaku}) format('opentype'); }
@font-face { font-family:'NeonFuture'; src:url(data:font/truetype;base64,${neonFuture}) format('truetype'); }
@font-face { font-family:'RetroByte';  src:url(data:font/truetype;base64,${retroByte}) format('truetype'); }

* { margin:0; padding:0; box-sizing:border-box; }
body {
  width:2400px; height:1260px;
  background: ${meteoriteBg};
  display:flex; align-items:center; justify-content:center;
  position:relative; overflow:hidden;
}

/* warm terracotta glow center */
.glow-center {
  position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
  width:1400px; height:900px;
  background:radial-gradient(ellipse, rgba(193,102,107,0.14) 0%, rgba(212,160,64,0.08) 40%, transparent 70%);
  pointer-events:none;
}
.glow-left {
  position:absolute; top:50%; left:0; transform:translateY(-50%);
  width:600px; height:800px;
  background:radial-gradient(ellipse at left, rgba(193,102,107,0.1) 0%, transparent 70%);
  pointer-events:none;
}

/* Top border */
body::before {
  content:'';
  position:absolute; top:0; left:0; right:0; height:6px;
  background:linear-gradient(90deg, #c1666b, #d4943a, #c1666b);
}

.robot-wrap {
  position:absolute; left:220px; top:50%; transform:translateY(-50%);
  filter: drop-shadow(0 0 40px rgba(193,102,107,0.5)) drop-shadow(0 0 80px rgba(212,148,58,0.3));
}

.content {
  position:relative; z-index:1;
  display:flex; flex-direction:column; align-items:flex-start;
  margin-left:220px;
}

.eyebrow {
  font-family:'RetroByte',sans-serif;
  font-size:2.4rem; letter-spacing:0.18em; text-transform:uppercase;
  color:rgba(193,102,107,0.8); margin-bottom:24px;
}

.wordmark {
  font-family:'Kenjaku',sans-serif;
  font-size:10rem; letter-spacing:0.04em; color:#ede8e0;
  margin-bottom:32px;
  filter:drop-shadow(0 0 30px rgba(212,160,64,0.3));
}

.tagline {
  font-family:'NeonFuture',sans-serif;
  font-size:4.8rem; letter-spacing:0.04em; line-height:1.15;
  background:linear-gradient(135deg, #c1666b, #d4943a, #e9c46a);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  max-width:1500px; margin-bottom:60px;
}

.pills {
  display:flex; gap:24px; flex-wrap:wrap; max-width:1600px; margin-bottom:72px;
}
.pill {
  font-family:'RetroByte',sans-serif;
  font-size:2.2rem; letter-spacing:0.05em;
  padding:18px 38px;
  border:1.5px solid rgba(193,102,107,0.4);
  border-radius:12px; color:#ede8e0;
}
.pill.gold  { border-color:rgba(212,160,64,0.55); color:#e9c46a; }
.pill.teal  { border-color:rgba(74,158,255,0.4);  color:#4a9eff; }

.stats {
  display:flex; gap:90px; align-items:flex-start;
}
.stat-val {
  font-family:'Kenjaku',sans-serif;
  font-size:5rem; color:#d4943a; text-align:center;
}
.stat-label {
  font-family:'RetroByte',sans-serif;
  font-size:1.75rem; color:#9e7a5a; letter-spacing:0.06em; text-align:center; margin-top:8px;
}

.footer {
  position:absolute; bottom:50px; left:220px; right:80px;
  display:flex; justify-content:space-between;
  font-family:'RetroByte',sans-serif;
  font-size:2rem; color:rgba(210,190,160,0.35); letter-spacing:0.07em; text-transform:uppercase;
}
</style>
</head><body>
<div class="glow-center"></div>
<div class="glow-left"></div>
<div class="robot-wrap">${jerryRobot}</div>

<div class="content">
  <div class="eyebrow">A Skint Labs Product</div>
  <div class="wordmark">Jerry</div>
  <div class="tagline">The AI that knows your store,<br>tracks every order, handles returns.</div>
  <div class="pills">
    <div class="pill">Shopify Native</div>
    <div class="pill">8 Languages</div>
    <div class="pill">Voice Chat</div>
    <div class="pill">Order Tracking</div>
    <div class="pill gold">No Revenue Share</div>
    <div class="pill teal">From $49/mo</div>
  </div>
  <div class="stats">
    <div><div class="stat-val">8</div><div class="stat-label">Languages<br>auto-detected</div></div>
    <div><div class="stat-val">24/7</div><div class="stat-label">Always on<br>no days off</div></div>
    <div><div class="stat-val">0</div><div class="stat-label">Revenue<br>share</div></div>
    <div><div class="stat-val">v4</div><div class="stat-label">Current<br>version</div></div>
  </div>
</div>

<div class="footer">
  <span>jerry.skintlabs.ai</span>
  <span>skintlabs.ai</span>
</div>
</body></html>`;

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.setViewport({ width: 2400, height: 1260 });
  await page.setContent(html, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({ path: path.join(__dirname, 'docs/og-image.png'), type: 'png' });
  await browser.close();
  console.log('Jerry OG image generated → docs/og-image.png');
})();
