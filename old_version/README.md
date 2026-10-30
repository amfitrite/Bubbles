# Bubbles — Hybrid Micro/Macro Order Flow Terminal

> **Status:** DOKUMENTASI PERENCANAAN — belum ada kode, belum di-build.
> **Tanggal:** 28 Oktober 2026
> **Lokasi proyek:** `D:\Bubbles`
> **Sumber data:** `multi port bridge EA.mq5` v5.50 (TCP client dari MT5)
> **Referensi desain:** Tick Map (Python/PySide6) — tanpa mengubah proyek tersebut.

---

## 1. Ringkasan

Bubbles adalah aplikasi desktop **khusus visualisasi volume order flow** dalam bentuk
bubble. Tidak ada candle, heatmap, volume profile, footprint table, axis, grid, atau
panel chart lain. Yang tampil hanya bubble di atas canvas gelap, ditambah HUD tipis
dan tooltip.

Keunikan utama: **satu tampilan yang berubah resolusi saat di-zoom**.

- **Zoom in** → bubble volume mikro, tersebar di setiap price level.
- **Zoom out** → bubble volume makro, satu bubble VWAP per blok waktu.
- Peralihan mikro → makro terjadi bertahap, bukan pindah mode mendadak.

Tiga mode tampilan:

1. **Classic** — total volume, satu warna cyan.
2. **Delta** — net buy/sell, hijau/merah/abu-abu.
3. **Imbalance** — diagonal footprint imbalance, cyan/amber.

Aplikasi ini adalah **alat baca**, bukan alat prediksi. Tidak ada sinyal entry,
marker buy/sell, alert, atau eksekusi order. Keputusan trading tetap manual.

Untuk memudahkan entry, aplikasi memakai tiga **lensa tampilan** yang bisa
diganti cepat: **Context** (Classic, 2–4 jam), **Pressure** (Delta, 10–15 menit),
dan **Trigger** (Imbalance, 60–120 detik). Lensa adalah preset tampilan, bukan
sinyal. Semua metrik diturunkan dari tick mentah dengan formula terdokumentasi,
sample guard, dan label deskriptif — tanpa DOM sintetis, tanpa interpolasi, dan
tanpa klaim prediktif.

---

## 2. Keputusan yang Sudah Dikunci

| Area | Keputusan |
|---|---|
| Stack | Python 3.14 + PySide6 6.12 + numpy 2.5 |
| Rendering | `QWidget` + `QPainter` + sprite cache (bukan QML/WebGL) |
| Posisi bubble | Hybrid: price-level cells saat mikro, VWAP bucket saat makro |
| Mode Classic | Total volume, satu warna cyan `#22D3EE` |
| Mode Delta | Net delta per bubble, hijau/merah/netral |
| Mode Imbalance | Diagonal footprint imbalance (micro dan macro) |
| Entry | Visual saja; tanpa sinyal, alert, atau eksekusi |
| Data | SQLite lokal; retensi tick dan bar dapat diatur |
| Replay | Schema DB disiapkan, replay UI menyusul setelah live stabil |
| UI | Hanya bubbles + HUD tipis + tooltip |
| Multi-port | Listen 5555–5559; primary/standby per symbol |
| EA | Tidak perlu diubah; tetap TCP client |
| Entry workflow | Tiga lensa: Context (Classic), Pressure (Delta), Trigger (Imbalance) |
| Visual | Design token, bubble glass/marble, HUD tipis, motion 120–240 ms |
| Accuracy | Tick mentah = sumber kebenaran; robust percentile; sample guard; tanpa DOM sintetis |
| Label | Deskriptif: “high volume”, “buy imbalance”; bukan “smart money” atau prediksi |

Environment yang sudah terverifikasi di mesin pengguna:

```text
Python  3.14.7
PySide6 6.12.0
numpy   2.5.3
```

---

## 3. Arsitektur

```text
MT5 + EA (TCP client)
        │
        │  #SYMBOL / #META / #HIST_START
        │  timestamp,bid,ask,last,volume,flags
        │  #HIST_END
        ▼
┌─────────────────────────────────────────────────────────┐
│ BridgeServer (thread)                                   │
│  - listen 127.0.0.1:5555..5559                          │
│  - parser per koneksi (bukan global)                    │
│  - primary/standby per symbol                           │
│  - dedupe timestamp                                     │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
  TickStore        BarStore       DB writer
  (ring buffer)    (1s / 1m)      (SQLite, batch)
        │              │
        └──────┬───────┘
               ▼
        version counter
               │
        UI timer 60 FPS
               ▼
        LOD selector
        ├── MicroGrid  (time × price)
        └── MacroSeries (VWAP per bucket)
               │
               ▼
        BubbleRenderer (sprite cache)
               │
               ▼
        BubbleCanvas + HUD + Tooltip
```

### Prinsip arsitektur

- **Single writer**: hanya BridgeServer/ingest thread yang menulis TickStore dan BarStore.
- **UI tidak pernah query DB** dan tidak pernah menunggu socket.
- **Render tidak dipanggil per tick**; UI timer yang melakukan coalesced repaint.
- **Snapshot immutable** untuk data yang dibaca UI.
- **Bounded queue** untuk DB writer dan replay; jika penuh, drop batch tertua dan catat counter.
- **L0 transport / L1 data / L2 engine / L3 UI** — tidak ada import UI dari engine.

---

## 4. Protokol EA

EA `multi port bridge EA.mq5` v5.50 berjalan sebagai **TCP client**. Ia melakukan
koneksi ke `InpServerHost` (default `127.0.0.1`) pada port yang diaktifkan
(default 5555 dan 5556). Aplikasi Bubbles harus menjadi **TCP server**.

### 4.1 Urutan pesan

```text
#SYMBOL:XAUUSD
#META:XAUUSD,2,0.01,0.01,100.00
#HIST_START:5000
1700000000123,2400.10,2400.20,2400.15,1.0,32
1700000000456,2400.09,2400.19,2400.14,1.0,64
...
#HIST_END
```

### 4.2 Format baris tick

```text
timestamp_ms,bid,ask,last,volume,flags
```

| Field | Tipe | Keterangan |
|---|---|---|
| `timestamp_ms` | int64 | Waktu tick MT5 dalam milidetik (server time) |
| `bid` | double | Harga bid |
| `ask` | double | Harga ask |
| `last` | double | Harga last; bisa 0 untuk CFD |
| `volume` | double | Volume; EA memakai `volume_real` jika > 0, jika tidak `volume`, jika <= 0 menjadi 1.0 |
| `flags` | uint | Bit flag MT5; `32` = buy, `64` = sell |

Format lama 5-field (`timestamp,bid,ask,volume,flags`) dan baris `META,` tetap
didukung untuk kompatibilitas.

### 4.3 Perilaku EA yang perlu ditangani

- EA mengirim history **setiap kali koneksi baru** dibuat.
- History dibatasi `InpHistoryDays` (default 1 hari) dan `InpMaxHistoryTicks`
  (default 5000 tick).
- Reconnect otomatis setiap `InpReconnectSec` (default 2 detik).
- EA mem-broadcast tick yang sama ke semua port aktif. Jika app listen di lebih
  dari satu port, data bisa duplikat.
- Jika `last <= 0`, EA mengisi harga fallback dari bid/ask dan menambahkan flag
  buy/sell berdasarkan pergerakan bid/ask.
- `FormatTick` untuk history ikut memperbarui state `g_prev_*`; ini bisa membuat
  arah tick pertama setelah history sedikit bergeser. App tetap menurunkan side
  dari flags dan tick rule, jadi tidak kritis.
- Timeout `SocketConnect` 300 ms. Jika app belum siap, EA akan retry.

### 4.4 Interpretasi volume

MT5 CFD (termasuk XAUUSD retail) umumnya tidak menyediakan real volume. EA akan
mengirim `1.0` per tick. Artinya:

> **Bubble = tick volume (jumlah tick), bukan lot volume.**

Tooltip akan memberi label “Tick volume” bila terdeteksi volume seragam 1.0.
Jika broker/feed menyediakan real volume, nilai itu dipakai dan label berubah
menjadi “Volume”.

---

## 5. Model Hybrid Mikro–Makro

### 5.1 Pemilihan resolusi

| Rentang waktu terlihat | Time bucket | Tampilan |
|---|---|---|
| 2–10 detik | 25–100 ms | Mikro sangat halus, bubble per price level |
| 10 detik–2 menit | 100–500 ms | Mikro padat, price level |
| 2–5 menit | 500 ms–2 s | Mikro, mulai lebih renggang |
| 5–30 menit | 2–15 s | Transisi: price row menyusut 24 → 4, bubble makro muncul |
| 30 menit–1 hari | 15 s–15 m | Makro: 1 bubble VWAP per bucket |
| 1–30 hari | 15 m–6 jam | Makro dari `bars_1m` di database |

### 5.2 Rumus

```text
timeSpan     = lebar_canvas_px × ms_per_pixel
bucketMs     = niceTimeStep(timeSpan / 120)
macroWeight  = smoothstep((timeSpan - 5 menit) / (30 menit - 5 menit))
targetRows   = round(lerp(24, 4, macroWeight))
priceBin     = niceTickStep(visiblePriceRange / targetRows, tickSize)
```

`niceTimeStep` memakai ladder:

```text
25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2s, 5s, 10s, 15s, 30s,
1m, 2m, 5m, 10m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
```

`niceTickStep` memakai kelipatan tick size:

```text
1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, ...
```

### 5.3 Layer mikro

- Grid 2D: `time bucket × price bin`.
- Setiap sel menyimpan: total volume, buy volume, sell volume, VWAP, tick count.
- Posisi bubble:
  - X = volume-weighted time center di dalam bucket.
  - Y = VWAP sel.
- Ukuran = total volume sel.
- Sel kosong tidak digambar.
- Jika jumlah bubble > 3.000, buang sel dengan volume terkecil.

### 5.4 Layer makro

- Satu bubble per `time bucket`.
- X = pusat bucket (atau volume-weighted time center).
- Y = VWAP bucket.
- Ukuran = total volume bucket.
- Sumber data:
  - Sesi berjalan: `BarStore` 1 detik.
  - Multi-hari: `bars_1m` dari SQLite, diagregasi ke bucket yang dipilih.

### 5.5 Transisi

- `macroWeight` naik dari 0 ke 1 saat `timeSpan` bergerak dari 5 menit ke 30 menit.
- Layer mikro: `alpha = 1 - macroWeight`, dan `targetRows` menyusut dari 24 ke 4.
  Efeknya bubble-bubble kecil bergabung vertikal.
- Layer makro: `alpha = macroWeight`, muncul di VWAP bucket.
- Di `macroWeight >= 0.98`, layer mikro tidak dihitung sama sekali.
- Morph posisi penuh (setiap sel bergerak ke VWAP) adalah polish opsional setelah
  versi crossfade stabil.

### 5.6 Skala radius

```text
norm   = clamp(volume / p95_visible, 0, 1.5)
radius = rMin + (rMax - rMin) × sqrt(norm)
```

- `p95_visible` = persentil 95 volume bubble yang terlihat.
- `rMin = 3 px`.
- `rMax` mikro = 26 px; makro = 44 px.
- Radius di-clamp agar tidak menutupi seluruh layar.
- Intensitas opacity/glow mengikuti volume; outlier (top 2%) mendapat glow ekstra.

### 5.7 Auto-fit harga

- Range harga diambil dari posisi bubble yang terlihat, bukan dari high/low mentah.
- Range melebar langsung saat ada bubble di luar viewport; mengecil perlahan
  (hysteresis) agar tidak jitter.
- Minimum range = 10 tick, untuk mencegah pembagian nol.
- Manual zoom harga atau drag vertikal mematikan auto-fit; double-click
  mengaktifkannya kembali.

---

## 6. Tiga Mode

### 6.1 Classic

- Warna tunggal cyan `#22D3EE`.
- Ukuran dan opacity/glow menunjukkan total volume.
- Tidak ada split pie, tidak ada angka di dalam bubble.
- Paling bersih untuk melihat lokasi volume menumpuk.

### 6.2 Delta

- `delta = buyVolume - sellVolume`.
- `deltaRatio = delta / totalVolume`.
- Warna:
  - `deltaRatio >= +0.15` → hijau `#34D399`
  - `deltaRatio <= -0.15` → merah `#F87171`
  - di antaranya → abu-abu `#64748B`
- Intensitas warna mengikuti `abs(deltaRatio)`.
- Ukuran bubble tetap mengikuti total volume, bukan delta.

### 6.3 Imbalance — Diagonal

#### Mikro

Untuk setiap sel (`t`, `p`):

```text
Buy imbalance  : buy[t,p]  >= ratio × sell[t,p-1]  dan buy[t,p]  >= minVol
Sell imbalance : sell[t,p] >= ratio × buy[t,p+1]   dan sell[t,p] >= minVol
```

- Default `ratio = 3.0`, `minVol = 5.0`.
- Perbandingan dilakukan terhadap price bin tepat di bawah (buy) atau di atas (sell).
- Jika kedua sisi nol atau volume di bawah `minVol`, sel dianggap balanced.
- Jika sebuah sel memenuhi buy dan sell imbalance sekaligus, pilih sisi dengan
  rasio lebih besar; tooltip tetap menampilkan keduanya.

#### Makro

1. Bangun price profile 1D per bucket: `buy[p] = sum over time`, `sell[p] = sum over time`.
2. Terapkan uji diagonal yang sama pada profile tersebut.
3. Hitung `buyImbVol` = total buy volume pada level yang buy-imbalance, dan
   `sellImbVol` = total sell volume pada level yang sell-imbalance.
4. Sisi dominan menentukan warna bubble makro.
5. Intensitas = `abs(buyImbVol - sellImbVol) / max(buyImbVol + sellImbVol, 1)`.
6. `stack_count` = jumlah price level yang imbalance searah. Jika >=2, bubble
   makro mendapat glow stack; tooltip menampilkan jumlah level.

#### Warna

| Kondisi | Warna |
|---|---|
| Buy imbalance | Sky `#38BDF8` |
| Sell imbalance | Amber `#FBBF24` |
| Balanced | Redup `#1E293B` |

Bubble imbalance mendapat glow lebih kuat. Tidak ada ring, panah, atau marker.

### 6.4 Tanpa sinyal

Tidak ada:
- marker entry buy/sell,
- alert suara/popup,
- teks sinyal di chart,
- eksekusi order.

Mode hanya mengubah cara volume divisualisasikan.

### 6.5 Entry Lenses & Playbook

Tiga lensa adalah **preset tampilan**, bukan sinyal. Setiap lensa menggabungkan
mode + rentang waktu agar perpindahan dari konteks ke trigger cepat.

| Lensa | Mode | Zoom default | Yang dibaca | Fungsi |
|---|---|---|---|---|
| **Context** | Classic | 2–4 jam | Aktivitas volume makro, lintasan VWAP, regime | Menentukan regime/partisipasi, bukan arah |
| **Pressure** | Delta | 10–15 menit | High-volume price level + delta per level | Menentukan node dan siapa yang menguasai |
| **Trigger** | Imbalance | 60–120 detik | Diagonal imbalance + stack | Menentukan timing entry dan invalidasi |

- `Tab` = lensa berikutnya; `Shift+Tab` = sebelumnya.
- `Q` / `W` / `E` = langsung ke Context / Pressure / Trigger.
- HUD menampilkan `CONTEXT · CLASSIC · 4H`; jika user mengubah mode/zoom manual,
  label berubah menjadi `CUSTOM`.
- Perpindahan lensa dianimasikan 240 ms (zoom + crossfade warna).
- Lensa tidak menambahkan marker, panah, alert, atau teks sinyal.

#### Playbook discretionary

1. **Context** — baca aktivitas dan regime. Bubble makro membesar = partisipasi
   naik; mengecil = pasar sepi. Lintasan VWAP naik/turun/flat menunjukkan bias
   periode. Jangan mencari price node di sini; ini konteks, bukan lokasi.
2. **Pressure** — zoom ke 10–15 menit. Cari bubble besar di price level = node.
   Warna delta menunjukkan siapa yang menguasai level itu: hijau = net buy,
   merah = net sell. Jangan melawan delta yang kuat.
3. **Trigger** — zoom ke 60–120 detik. Tunggu 2+ diagonal imbalance searah
   dengan bias Pressure di node tersebut. Entry saat harga hold/retest; stop di
   luar node; target node berikutnya.
4. **Invalidasi** — volume besar tetapi harga tidak bergerak (absorption), atau
   delta berbalik → stand aside. Jangan entry saat sample tick tipis atau feed
   stale.

Playbook ini adalah panduan discretionary, bukan jaminan profit.

#### Fitur pendukung entry

- **Stack glow** — 2+ price bin berurutan imbalance searah mendapat glow lebih
  kuat. Untuk macro, stack count = jumlah level imbalance di dalam bucket.
  Tooltip: `Stack: 3 levels`. Tanpa garis penghubung.
- **Hover focus** — bubble lain diredupkan ke ±55%; bubble aktif membesar 1.06×.
- **Pinned readout** (opsional) — klik bubble untuk mengunci metrik di kartu
  kecil kanan atas; klik area kosong untuk melepas.
- **Forming bucket** — bucket terakhir yang belum selesai digambar 65% opacity
  + rim tipis, dan tidak dihitung dalam p95/baseline. Tooltip: `FORMING`.
- **Sample guard** — sel <3 tick (micro) atau bucket <10 tick (macro) diberi
  warna netral/redup; tooltip `n=2 (low sample)`.
- **Stale/gap indicator** — tick terakhir >5 detik → HUD `STALE` amber; tidak
  ada interpolasi atau bubble palsu.
- **Zoom preset** — `Q/W/E` atau chip HUD; `Tab` untuk siklus lensa.
- **Snapshot** (`Ctrl+Shift+S`, opsional) — export PNG untuk jurnal.

---

## 7. Rendering & UI

### 7.1 Canvas

- Background `#06080C` dengan vignette radial sangat halus dan noise texture 1.5%.
- Tidak ada axis, grid, candle, heatmap, garis, atau teks di canvas.
- Bubble digambar dengan sprite pre-render:
  - radial gradient,
  - specular highlight di offset ±35%,
  - rim gelap tipis,
  - soft glow.
- Satu draw call per bubble; bubble besar digambar lebih dulu, bubble kecil di atas.
- Top 2% volume mendapat glow ekstra.
- Target 60 FPS pada 2560×1440 dengan maksimal 3.000 bubble.
- Culling: hanya bubble yang bounding box-nya menyentuh viewport yang digambar.

### 7.2 HUD

| Posisi | Isi |
|---|---|
| Kiri atas | Symbol, harga terakhir, dot koneksi, status history |
| Tengah atas | Segmented control lensa `CONTEXT / PRESSURE / TRIGGER` + label kecil `CLASSIC · 4H` |
| Kanan atas | `LIVE` pill, label `MICRO/MACRO`, tombol settings |
| Bawah | Hint shortcut, memudar setelah 5 detik |
| Tooltip | Kartu kecil saat hover bubble |

HUD memakai widget overlay transparan, bukan bagian dari canvas. Settings drawer
muncul dari kanan dan menutup kembali tanpa mengubah layout chart.

### 7.3 Tooltip

Isi tooltip:

- Waktu (server time)
- Harga / VWAP
- Total volume
- Buy volume
- Sell volume
- Delta dan delta %
- Rasio imbalance
- Jumlah tick / sample quality (`low sample` bila di bawah guard)
- Volume type (`Tick volume` atau `Real volume`)
- Status bucket (`FORMING` atau selesai)
- Stack count untuk imbalance (`Stack: 3 levels`)
- Time bucket dan price bin

Tooltip muncul hanya jika kursor berada dalam radius ±12 px dari bubble. Tidak
ada crosshair line.

### 7.4 Interaksi

| Aksi | Fungsi |
|---|---|
| Wheel | Zoom seragam (waktu + harga) |
| Shift + Wheel | Zoom waktu saja |
| Ctrl + Wheel | Zoom harga saja |
| Drag | Pan; mematikan follow-live |
| Double-click | Reset ke 5 menit terakhir, auto-fit harga |
| Space | Kembali ke live |
| `Tab` / `Shift+Tab` | Lensa berikutnya / sebelumnya |
| `Q` / `W` / `E` | Context / Pressure / Trigger |
| `1` / `2` / `3` | Classic / Delta / Imbalance (mode manual, label jadi `CUSTOM`) |
| `S` | Buka settings |
| `F` | Fullscreen |
| `+` / `-` | Zoom in/out |
| `Esc` | Keluar fullscreen / tutup drawer |

### 7.5 Multi-symbol

- Jika ada lebih dari satu symbol aktif, dropdown symbol muncul di kiri atas.
- Jika hanya satu, dropdown disembunyikan.
- Setiap symbol punya TickStore, BarStore, camera state, dan DB rows sendiri.
- Mode dan threshold berlaku global.

### 7.6 Visual Design System

Kesan “mahal” berasal dari konsistensi, ruang kosong, dan presisi — bukan dari
banyak efek. Palet dibatasi, glow hanya untuk outlier, dan semua elemen memakai
grid 4/8 px.

#### Token warna

| Elemen | Nilai |
|---|---|
| Background | `#06080C` |
| Surface HUD | `#0D121A` @ 86% |
| Border | `rgba(255,255,255,0.07)` |
| Text primary | `#E8EEF6` |
| Text secondary | `#94A3B8` |
| Text muted | `#5B6B7F` |
| Accent | `#22D3EE` |
| Classic | core `#A5F3FC`, edge `#0891B2` |
| Delta buy | core `#A7F3D0`, edge `#059669` |
| Delta sell | core `#FECACA`, edge `#B91C1C` |
| Delta neutral | `#64748B` |
| Imbalance buy | core `#BAE6FD`, edge `#0284C7` |
| Imbalance sell | core `#FDE68A`, edge `#B45309` |
| Balanced | `#1E293B` |
| Stale | `#F59E0B` |

#### Tipografi, spacing, radius

- Font: **Inter** atau **Segoe UI Variable**.
- Harga/volume wajib memakai **tabular numbers**.
- Ukuran: 10px label uppercase, 11px hint, 13px value, 18px symbol.
- Letter-spacing label ±0.08em.
- Spacing: kelipatan 4/8/12/16/24 px.
- Radius: panel 12px, tombol 8px, pill 999px.
- Shadow hanya untuk drawer, bukan semua elemen.

#### Resep material bubble

1. Radial gradient: core color di tengah, edge color di 70%, lebih gelap di tepi.
2. Inner shadow di bawah, hitam 18% opacity.
3. Specular highlight putih 55% opacity, offset -35% x/y, radius ±25% bubble.
4. Rim light tipis di kanan-bawah, warna bubble 35% opacity.
5. Contact shadow hitam 20% opacity, offset 1–2px, hanya untuk radius >10px.
6. Glow luar hanya untuk top 1–2% volume; jangan semua bubble menyala.
7. Tidak ada outline hitam keras, tidak ada putih murni, tidak ada flat fill.

#### HUD

- Top bar 44px, bottom hint 28px, padding 12px, gap 8px.
- Panel semi-transparan gelap dengan 1px border dan top highlight tipis.
- Tanpa blur berat; blur canvas mahal secara performa.
- Ikon line 16px, stroke 1.5px. Jangan pakai emoji.
- Segmented control dengan indikator geser 180ms.
- Tooltip maksimal 220px, padding 10px, radius 8px, fade 80ms.
- Tombol minimal 28px height, hover fill halus, active accent.
- Window title bar gelap native; jangan frameless di v1.

#### Motion

- Hover 120ms, mode switch 180ms, lens switch 240ms, live dot breathing 2s.
- Easing `cubic-bezier(0.2, 0.8, 0.2, 1)`. Tidak ada bounce.
- Zoom selalu cursor-anchored, tidak melompat.
- Warna mode crossfade, bukan hard switch.
- Animasi hanya untuk transisi; nilai data tidak di-smooth sampai berubah.

#### Do / Don't

| Do | Don't |
|---|---|
| Satu accent color | Rainbow UI |
| Tinted gray | Hitam/putih murni |
| 1px border + elevation halus | Drop shadow berat |
| Glow selektif | Semua bubble glow |
| Tabular numbers | Angka proporsional |
| Line icons | Emoji |
| Radius konsisten | Campur 4/6/10/14 |
| Noise 1.5% + vignette 12% | Gradient flat yang banding |
| 60 FPS | Animasi layout |

Background gelap perlu noise texture halus (pre-render 256×256, opacity 1–2%)
supaya gradient tidak banding. Vignette cukup 10–15%.

---

## 8. Database & Histori

### 8.1 Lokasi

```text
D:\Bubbles\data\bubbles.db
```

Path dapat diubah lewat `config.json`.

### 8.2 Schema

```sql
CREATE TABLE ticks (
    id       INTEGER PRIMARY KEY,
    symbol   TEXT    NOT NULL,
    ts       INTEGER NOT NULL,
    bid      REAL,
    ask      REAL,
    last     REAL,
    volume   REAL,
    flags    INTEGER,
    side     INTEGER
);

CREATE INDEX idx_ticks_symbol_ts ON ticks(symbol, ts);

CREATE TABLE bars_1m (
    symbol    TEXT    NOT NULL,
    ts        INTEGER NOT NULL,
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL,
    volume    REAL,
    buy_vol   REAL,
    sell_vol  REAL,
    vwap      REAL,
    ticks     INTEGER,
    PRIMARY KEY (symbol, ts)
);

CREATE TABLE meta (
    symbol        TEXT PRIMARY KEY,
    digits        INTEGER,
    point         REAL,
    tick_size     REAL,
    contract_size REAL,
    updated_at    INTEGER
);

CREATE TABLE schema_version (
    version INTEGER NOT NULL
);
```

### 8.3 Pengaturan SQLite

- `journal_mode = WAL`
- `synchronous = NORMAL`
- `temp_store = MEMORY`
- `cache_size = -64000`
- Batch insert 500 tick atau 250 ms, di thread writer terpisah.
- Upsert `bars_1m` setiap menit dan saat app ditutup.

### 8.4 Retensi

| Data | Default | Config |
|---|---|---|
| Raw tick | 7 hari | `db.tick_retention_days` |
| Bar 1m | 365 hari | `db.bar_retention_days` |

Retensi dijalankan saat startup dan sekali sehari. Data lama dihapus, lalu
`VACUUM`/incremental vacuum saat idle.

### 8.5 Load saat connect

- Load `bars_1m` 30 hari terakhir untuk symbol tersebut.
- Load raw tick 2 jam terakhir ke ring buffer.
- Data lebih lama di-query on-demand di worker thread saat user zoom/pan.
- Jika raw tick untuk periode lama sudah dihapus, mode mikro menampilkan
  data yang tersedia; mode makro tetap memakai `bars_1m`.

### 8.6 Dedupe

- Setiap symbol menyimpan `last_ts`.
- Tick dengan `ts <= last_ts` dari koneksi live/reconnect diabaikan.
- Saat startup, `last_ts` diambil dari DB.
- History yang dikirim ulang EA tidak menggandakan baris.
- Catatan: beberapa tick dalam milidetik yang sama bisa terlewat saat dedupe;
  untuk v1 ini diterima.

### 8.7 Replay

- Replay UI **belum** masuk v1.
- Schema, loader, dan format bar sudah disiapkan agar replay bisa ditambahkan
  tanpa migrasi.
- Rencana replay: date range, play/pause, speed 1×/10×/60×/300×, feed ke
  TickStore terpisah, canvas mengikuti virtual clock.

### 8.8 Keterbatasan data

- App hanya menyimpan tick saat app berjalan.
- Jika app mati, tidak ada data baru; EA hanya mengirim history 1 hari/5.000
  tick saat reconnect.
- Untuk capture 24/7, app harus berjalan terus atau ditambahkan mode headless
  recorder di masa depan.
- Timezone: `time_msc` adalah server time MT5. UI memberi label “Server time”.
  Offset lokal dapat ditambahkan di config.

---

## 9. Multi-Port & Integrasi EA

### 9.1 Listener

- Default bind: `127.0.0.1`, port `5555, 5556, 5557, 5558, 5559`.
- Port yang gagal bind (dipakai app lain) dicatat di log dan dilewati.
- App tidak crash jika tidak ada port yang bisa dibuka; HUD menampilkan error.
- `SO_EXCLUSIVEADDRUSE` di Windows, `SO_REUSEADDR` di platform lain.
- `TCP_NODELAY` dan keepalive aktif.

### 9.2 Primary / standby

- EA mem-broadcast tick yang sama ke semua port.
- Untuk setiap symbol, koneksi pertama menjadi **primary** dan di-ingest.
- Koneksi lain dengan symbol yang sama menjadi **standby**: socket tetap dibaca,
  tetapi tick tidak di-ingest.
- Jika primary putus, standby dipromosikan.
- Jika standby masih dalam mode history saat promosi, sisa history tetap diproses.
- Jika dua EA berbeda mengirim symbol berbeda, keduanya menjadi primary.

### 9.3 Reconnect

- EA reconnect setiap 2 detik.
- App menerima koneksi baru, mengirim handshake? Tidak — EA yang mengirim
  `#SYMBOL`/`#META`; app hanya membaca.
- Socket mati dideteksi dari `recv() == 0` atau error; app menutup dan menandai
  status.
- History yang terputus di tengah jalan diakhiri saat socket close; state history
  per koneksi dibersihkan.

### 9.4 Kompatibilitas

- Format 6-field, 5-field legacy, dan baris `META,` didukung.
- `#META` field: symbol, digits, point, tick_size, contract_size.
- Jika `tick_size` 0 atau tidak ada, fallback ke `point`.
- Jika `symbol` belum dikirim, tick diabaikan sampai handshake datang.

---

## 10. Struktur File Rencana

```text
D:\Bubbles\
  app.py
  requirements.txt
  config.json
  README.md
  Start_Bubbles.bat
  src\
    __init__.py
    config.py
    logging_setup.py
    network\
      __init__.py
      protocol.py
      bridge_server.py
    data\
      __init__.py
      tick_store.py
      bar_store.py
      database.py
    engine\
      __init__.py
      camera.py
      lod.py
      micro_grid.py
      macro_series.py
      bubble_engine.py
      modes.py
    ui\
      __init__.py
      main_window.py
      bubble_canvas.py
      bubble_renderer.py
      hud.py
      settings_drawer.py
      theme.py
      tooltip.py
    util\
      __init__.py
      time_utils.py
      math_utils.py
  tools\
    sim_feed.py
    db_inspect.py
  tests\
    test_protocol.py
    test_lod.py
    test_micro_grid.py
    test_imbalance.py
    test_database.py
  data\
    bubbles.db        (gitignored)
  logs\               (gitignored)
```

---

## 11. Threading & Performance

### 11.1 Thread

| Thread | Tugas |
|---|---|
| Main/UI | Qt event loop, camera, render, HUD |
| BridgeServer | Accept, recv, parse, append TickStore/BarStore |
| DB writer | Batch insert/upsert SQLite |
| DB reader | Query bars/ticks on-demand (worker) |
| Replay (nanti) | Feed tick historis ke store terpisah |

### 11.2 Aturan

- Hanya BridgeServer yang menulis TickStore/BarStore.
- UI membaca snapshot di bawah lock singkat; tidak ada operasi DB di UI.
- Render memakai QTimer 60 FPS; data berubah ditandai `version`.
- Display list dibangun ulang hanya jika `version` atau camera berubah.
- DB writer memakai queue bounded; penuh → drop batch tertua + counter.
- Tidak ada `sleep()` di UI thread; tidak ada `processEvents()` di loop.

### 11.3 Target

| Metrik | Target |
|---|---|
| FPS | 60 FPS @ 2560×1440, 3.000 bubble |
| UI frame | < 16 ms |
| History burst | 5.000 tick tanpa freeze |
| Ingest | 5.000 tick/detik |
| Startup | < 2 detik dengan DB |
| Memori | < 500 MB untuk sesi 8 jam |
| DB write | > 10.000 tick/detik (batch) |

### 11.4 Fallback performa

Jika QPainter tidak mencapai target:
1. Kurangi jumlah bubble maksimum.
2. Glow hanya untuk top 10% volume.
3. Pindah ke `QOpenGLWidget` dengan textured quad batch.
4. Turunkan FPS render ke 30 saat idle.

---

## 12. Milestone

| Milestone | Isi | Kriteria selesai |
|---|---|---|
| **M0** | Skeleton, config, logging, TCP server, parser, TickStore, simulator, DB dasar | EA connect, 5.000 history tick masuk, live tick terhitung, reconnect aman, DB terisi |
| **M1** | Camera, LOD, micro grid, Classic mode, sprite renderer, pan/zoom, follow-live | Bubble mikro muncul di 2 detik–2 menit, 60 FPS, hanya bubble + HUD |
| **M2** | Bar store, macro series, transisi hybrid, auto-fit harga, macro dari DB | Zoom 10 detik → 30 hari mulus, transisi mikro→makro terlihat, bubble count bounded |
| **M3** | Delta, imbalance diagonal (micro & macro), stack glow, entry lenses, settings threshold, tooltip lengkap | Skenario sintetis trend/imbalance/range tampil benar; lensa Context/Pressure/Trigger bekerja; threshold bisa diubah |
| **M4** | Persistence hardening, dedupe hash, sample guard, forming bucket, data panel, retensi, multi-symbol, primary/standby, soak test | Restart tidak kehilangan data, tidak ada duplikat, memori stabil 8 jam, data quality terpantau |
| **M5** | Polish HUD, design system, animasi, settings drawer, hotkey, DPI, fullscreen, PyInstaller | Exe one-click, 1440p/4K scaling benar, visual konsisten, checklist EA lolos |
| **M6** | Replay UI (date range, play/pause, speed) | Replay dari DB berjalan tanpa mengubah engine |

Urutan build tidak boleh diacak: M0 → M1 → M2 → M3 → M4 → M5.

Entry Lenses, Visual Design System, dan Data Integrity bukan milestone terpisah;
pekerjaannya menyatu di M1–M3 dan diverifikasi ulang di M5.

---

## 13. Kriteria Sukses

1. App listen di 5555, EA connect, bubble live muncul dalam < 1 detik.
2. History 5.000 tick diproses tanpa freeze.
3. Tiga mode tampil benar dan bisa diganti via HUD/hotkey.
4. Zoom dari 10 detik sampai 30 hari berjalan mulus; transisi mikro→makro terlihat.
5. Jumlah bubble per frame ≤ 3.000; tidak ada lag berarti saat pan/zoom.
6. Tidak ada candle, axis, grid, heatmap, panel, marker, atau teks sinyal di canvas.
7. Tooltip menampilkan volume/delta/imbalance dengan benar.
8. DB menyimpan tick dan bar; restart tidak menggandakan data.
9. Multi-port/primary-standby bekerja; tidak ada duplikasi saat EA broadcast.
10. Sesi 8 jam stabil: memori tidak naik tanpa batas, DB tidak corrupt.
11. DPI 125%/150% dan fullscreen tidak memotong HUD.
12. Build PyInstaller bisa dijalankan tanpa Python terpasang.
13. Tiga lensa Context/Pressure/Trigger bekerja dan bisa diganti via `Tab`/`Q`/`W`/`E`.
14. Visual memakai design token, material bubble, HUD glass, dan motion yang konsisten.
15. Panel Data menampilkan volume type, last tick age, gaps, dropped tick, dan DB size.
16. Forming bucket, sample guard, dan stale indicator bekerja sesuai definisi.
17. Invariant test lolos; tidak ada random/synthetic DOM; cross-check MT5 tidak menemukan mismatch.

---

## 14. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Tick volume disangka lot volume | Label “Tick volume”; dukung real volume jika tersedia |
| SQLite membengkak | Retensi tick 7 hari, batch write, WAL, vacuum saat idle |
| Transisi hybrid terlihat aneh | Crossfade + penyusutan price row; morph posisi sebagai polish |
| QPainter lambat | Sprite cache, culling, glow selektif, fallback QOpenGLWidget |
| Port bentrok dengan Tick Map | Resilient bind, log, default satu port per app |
| EA hanya kirim 5.000 tick/1 hari | DB mengakumulasi; macro tumbuh seiring pemakaian |
| Timezone MT5 | Label “Server time”; offset lokal di config |
| Dua EA mengirim symbol sama | Primary/standby + dedupe timestamp |
| Failover primary→standby ada gap | Gap kecil; history reconnect EA mengisi; buffer standby bisa ditambahkan nanti |
| App mati = tidak ada data | Jalankan app terus; mode headless recorder di masa depan |
| Visual terlihat ramai/murah | Design token, palet terbatas, glow selektif, grid 4/8 px |
| Algoritma dianggap prediksi | Label deskriptif, tanpa sinyal, panel Data + limitasi eksplisit |
| Bucket forming disalahartikan | Gaya 65% opacity + rim, exclude dari p95/baseline |
| Sample tipis memberi warna menyesatkan | Sample guard 3 tick (micro) / 10 tick (macro), netral/redup |
| Data dianggap real volume/DOM | Label “Tick volume”, “No DOM”, cross-check MT5 |

---

## 15. Testing & Data Integrity

### 15.1 Unit test

- `test_protocol.py` — handshake, 6-field, 5-field, partial line, malformed line, CRLF.
- `test_lod.py` — pemilihan bucket/price bin, macroWeight, clamp.
- `test_micro_grid.py` — binning volume, VWAP, buy/sell, culling.
- `test_imbalance.py` — diagonal buy/sell, denominator nol, minVol, macro aggregation.
- `test_database.py` — schema, insert batch, upsert bar, dedupe, retention.

### 15.2 Simulator

`tools/sim_feed.py` menyediakan skenario:

- `range` — harga mean-reverting, buy/sell seimbang.
- `trend` — arah jelas, delta dominan.
- `news` — lonjakan volume satu sisi.
- `imbalance` — stacked diagonal imbalance di level tertentu.

Simulator mengirim handshake + history + live tick ke port app, sehingga visual
bisa diuji tanpa MT5.

### 15.3 Checklist manual dengan EA

1. Jalankan app; HUD menunjukkan `LISTENING 127.0.0.1:5555`.
2. Attach EA ke chart XAUUSD M1; cek log EA connected.
3. App menampilkan symbol, progress history, lalu live tick.
4. Bubble muncul; zoom in/out mengubah mikro/makro.
5. Matikan EA; app menunjukkan reconnect.
6. Nyalakan EA lagi; history tidak menggandakan data.
7. Ganti mode Classic/Delta/Imbalance; warna berubah benar.
8. Ganti lensa Context/Pressure/Trigger; mode dan zoom ikut berubah.
9. Cek panel Data: volume type, last tick age, gaps, dropped tick, DB size.
10. Biarkan 8 jam; cek memori, DB size, FPS.

### 15.4 Hirarki kebenaran & limitasi

1. **Raw tick** dari EA = sumber utama: timestamp, bid, ask, last, volume, flags.
2. **Metrik turunan** = formula terdokumentasi: VWAP, delta, imbalance, percentile.
3. **Label** = deskriptif, bukan prediksi.

Batasan yang wajib ditampilkan di panel **Settings → Data**:

- MT5 CFD tick volume **bukan real traded volume**; sering hanya jumlah tick.
- Klasifikasi buy/sell bisa berasal dari flags MT5 atau uptick/downtick,
  **bukan true aggressor**.
- Tidak ada DOM/order book/resting liquidity.
- History EA hanya 1 hari / 5.000 tick saat connect; DB hanya terisi saat app
  berjalan.
- Waktu adalah **server time MT5**, bukan local time.
- Tidak ada data saat app mati.

Contoh isi panel Data:

```text
Source        : MT5 EA v5.50 · 127.0.0.1:5555
Volume type   : Tick volume (CFD proxy)
Side          : MT5 flags + uptick/downtick fallback
Order book    : Not available
Last tick     : 0.8s ago
Ticks today   : 1,234,567
Gaps / dropped: 3 / 0
DB size       : 420 MB
```

### 15.5 Aturan anti-halu

- **Tidak ada random/synthetic DOM** di jalur produksi. Random hanya boleh di
  simulator.
- **Tidak ada interpolasi** melewati gap. Bucket kosong = tidak ada bubble.
- Jangan pakai istilah “smart money”, “institutional”, “whale”. Pakai
  **“high volume”**, **“volume outlier”**, **“buy imbalance”**.
- Tidak ada entry score, panah buy/sell, alert, atau klaim “akurat 90%”.
- **Minimum sample**: micro minimal 3 tick, macro minimal 10 tick. Di bawah itu
  → netral/redup, tooltip `low sample`.
- **Forming bucket** tidak dihitung dalam p95/baseline. Normalisasi hanya dari
  bucket selesai.
- **Robust statistics**: median/MAD/percentile, bukan mean/max. Satu outlier
  tidak boleh membuat semua bubble kecil.
- **Jangan bandingkan volume mikro dengan makro secara langsung**. Normalisasi
  per LOD.
- **Jangan sampling/downsampling tick** untuk agregasi. Semua tick dihitung;
  kalau berat, agregasi per chunk dengan penjumlahan exact.
- **Dedupe overlap** memakai hash `(ts,bid,ask,last,volume,flags)` untuk window
  terakhir, bukan hanya `last_ts`, supaya tick sah di milidetik yang sama tidak
  hilang.
- **Deterministik**: bucket `floor(ts/bucketMs)*bucketMs`, price bin
  `floor(price/tickSize)`, tanpa randomness. Input sama → output sama.
- **DB integrity**: `PRAGMA quick_check` saat startup; backup sebelum migrasi.
- **Stale feed**: jika tidak ada tick >5 detik, HUD `STALE`; jangan menampilkan
  data seolah hidup.
- **Label deskriptif**, bukan prediktif: “positive delta”, bukan “bullish”;
  “buy imbalance”, bukan “buy signal”.

### 15.6 Formula yang wajib didokumentasikan

- `VWAP = Σ(price × volume) / Σvolume`
- `delta = buyVolume − sellVolume`
- `deltaRatio = delta / totalVolume`
- Diagonal imbalance:
  - Buy: `buy[t,p] >= ratio × sell[t,p−1]` dan `buy[t,p] >= minVol`
  - Sell: `sell[t,p] >= ratio × buy[t,p+1]` dan `sell[t,p] >= minVol`
  - Sisi pembanding minimal `minOtherVol` (mis. 1 tick), agar satu trade
    sendirian tidak otomatis dianggap imbalance.
- Macro imbalance: agregasi price profile per bucket, lalu uji diagonal yang
  sama; jangan menjumlahkan flag mikro mentah-mentah.
- Radius: `r = rMin + (rMax − rMin) × sqrt(clamp(vol/p95, 0, 1.5))`
- `p95` hanya dari bucket selesai, bukan forming.
- Bucket alignment: `floor(ts/bucketMs)*bucketMs`; price bin:
  `floor(price/tickSize)`; pusat bin: `(bin+0.5)*tickSize`.
- Absorption (opsional, deskriptif): volume percentile >= 95 **dan** range
  bucket <= 0.5 × median range pada LOD yang sama, dengan sample di atas guard.
  Tooltip menulis “high volume, low displacement”; bukan sinyal.

### 15.7 Accuracy invariants & test tambahan

- Jumlah volume semua sel = total volume tick di range (toleransi 1e-6),
  dihitung sebelum cap tampilan 3.000 bubble.
- `buy + sell = total`; tidak ada volume negatif.
- VWAP sel = VWAP tick; VWAP makro = weighted average tick.
- Tidak ada bubble dengan volume <= 0.
- Bucket boundaries monotonik dan tidak overlap.
- **Brute-force reference** untuk imbalance: implementasi O(n²) dibandingkan
  dengan versi numpy.
- **Parser fuzz**: potongan data acak, partial line, CRLF, malformed, reconnect.
- **DB round-trip**: tulis 100k tick, baca lagi, bandingkan.
- **Reconnect dedupe**: kirim history dua kali, jumlah baris tidak berubah.
- **Deterministic replay**: input sama → output sama.
- **Soak test** 8 jam: memori stabil, DB linear, FPS stabil.
- **Visual regression**: screenshot dataset tetap untuk tiap mode, bandingkan
  pixel diff.

### 15.8 Cross-check MT5

Validasi paling kuat: bandingkan data app dengan MT5.

- Manual: ambil 10 tick acak dari DB, bandingkan timestamp/bid/ask/last/volume/
  flags dengan Tick History MT5.
- Otomatis (opsional): `tools/verify_mt5.py` memakai package `MetaTrader5`
  untuk `copy_ticks_range` dan membandingkan dengan DB. Laporkan mismatch,
  missing, dan duplikat.
- Bandingkan juga total tick harian; selisih besar berarti ada gap atau dedupe
  yang salah.

### 15.9 Tuning EA (opsional, bukan wajib)

- Naikkan `InpMaxHistoryTicks` ke 20.000 jika MT5 sanggup, supaya tampilan awal
  lebih kaya.
- Matikan port yang tidak dipakai, atau biarkan app memakai primary/standby.
- Tambahkan `#HEARTBEAT:<server_ms>` tiap detik agar app bisa membedakan
  “market sepi” dan “feed mati”.
- Tambahkan flag `volume_mode` di `#META` agar app tidak menebak tick volume vs
  real volume.
- Perbaiki efek samping `g_prev_*` saat format history, supaya arah tick pertama
  setelah history lebih akurat.

Untuk v1, EA yang sekarang sudah cukup.

---

## 16. Catatan Desain

- **Hanya bubble** adalah aturan keras. HUD dan tooltip adalah overlay minimal,
  bukan elemen chart.
- Tidak ada angka volume di dalam bubble; detail hanya di tooltip.
- Tidak ada split pie. Classic sengaja satu warna agar bentuk volume murni.
- Tidak ada garis VWAP, POC, CVD, atau level harga. Posisi bubble sudah
  menyampaikan informasi tersebut.
- Warna dan glow adalah satu-satunya pembeda mode; bentuk bubble tetap sama.
- Animasi harus halus dan tidak mengganggu: scale-in 120 ms, camera easing 120 ms,
  crossfade mengikuti zoom.
- Semua threshold dan retensi dapat diubah lewat `config.json` dan settings drawer.
- Bahasa kode: komentar Indonesia, identifier Inggris, label UI Inggris
  (konsisten dengan Tick Map).
- Tidak ada label “smart money”, “institutional”, atau “whale”; gunakan
  “high volume” / “volume outlier”.
- Tidak ada random/synthetic DOM di jalur produksi; random hanya di simulator.
- Forming bucket dan sample guard adalah bagian akurasi, bukan dekorasi.
- Tidak ada interpolasi melewati gap; bucket kosong tetap kosong.
- Lensa Context/Pressure/Trigger adalah preset tampilan, bukan sinyal.
- Semua angka di tooltip menyertakan sample size agar bisa dinilai.

---

## 17. Yang Belum Diputuskan / Ditunda

- Replay UI detail (date picker, speed, seek) → M6.
- Morph posisi penuh saat transisi mikro→makro → polish setelah M2.
- Headless recorder 24/7 → ide masa depan.
- Sinkronisasi waktu lokal vs server → config offset, default server time.
- Dukungan real volume dari feed non-MT5 → di luar scope v1.
- Eksekusi order dari app → tidak termasuk (visual only).
- Pinned readout default on/off → opsional v1.1.
- Session stats di HUD (VWAP/POC/delta sebagai teks, bukan garis) → opsional v1.1.
- Absorption descriptive metric → opsional v1.1, dengan definisi ketat.
- Colorblind palette (biru/oranye) → opsional v1.1.
- Screenshot export → opsional v1.1.
- `tools/verify_mt5.py` → opsional, tetapi sangat disarankan untuk validasi.

---

## 18. Prioritas Implementasi

### Wajib v1

- Tiga lensa: Context / Pressure / Trigger.
- Forming bucket + sample guard + stale/gap indicator.
- Stack glow + hover focus + tooltip lengkap.
- Design token, material bubble, HUD glass, motion.
- Panel Data + formula + invariant test.
- Deterministik bucket/price alignment + robust percentile.

### Opsional v1.1

- Pinned readout.
- Session stats di HUD (VWAP/POC/delta sebagai teks).
- Absorption descriptive metric (high volume + low displacement).
- Colorblind palette (biru/oranye).
- Screenshot export.
- Replay UI.
- `tools/verify_mt5.py`.

### Jangan dilakukan

- Entry score, panah buy/sell, alert, atau klaim “akurat 90%”.
- Random DOM / liquidity palsu.
- Label “smart money” / “institutional” / “whale”.
- Interpolasi gap.
- Normalisasi pakai max volume.
- Menyamakan volume mikro dan makro.
- Menyembunyikan sample size atau limitasi data.

---

## 19. Status Saat Ini

```text
Dokumentasi : selesai — termasuk Entry Lenses, Visual Design System,
              Data Integrity & Accuracy, dan Prioritas
Kode        : belum ada
Build       : belum dimulai (sesuai instruksi)
Milestone   : belum mulai; berikutnya M0 setelah instruksi build
```

Jangan membuat file source, konfigurasi, atau menjalankan build sebelum ada
instruksi eksplisit untuk masuk tahap implementasi.

---

## 20. Changelog Dokumen

| Tanggal | Perubahan |
|---|---|
| 28 Okt 2026 | README awal: keputusan, arsitektur, protokol EA, model hybrid, tiga mode, database, milestone |
| 28 Okt 2026 | Tambah Entry Lenses & Playbook, Visual Design System, Data Integrity & Accuracy, dan Prioritas Implementasi |
