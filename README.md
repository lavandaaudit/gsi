# GSI · Global Situational Awareness Platform

> **Платформа ситуаційної обізнаності в реальному часі**  
> 128+ незалежних сигналів → 10 індексів → Глобальний індекс стану (GSI)

🌐 **Live Dashboard:** [https://lavandaaudit.github.io/gsi/](https://lavandaaudit.github.io/gsi/)

---

## Що це таке

Це **не** симуляція і **не** Math.random().

Кожен показник має:
- ✅ **Перевірюване джерело** (NOAA, USGS, Yahoo Finance, Open-Meteo тощо)
- ✅ **Прозору формулу нормалізації** (0–100, де 100 = оптимально)
- ✅ **Пояснення** через Signal Explorer (клік на будь-яку категорію)

---

## Архітектура даних

```
128+ незалежних сигналів
       ↓
Нормалізація (лінійна або логарифмічна, 0–100)
       ↓
10 тематичних категорій (зважена агрегація)
       ↓
Global State Index (GSI)
```

---

## Джерела даних (реальні API)

| Категорія | Джерела | Кількість сигналів |
|---|---|---|
| 🌌 Space Weather | NOAA SWPC RTSW (rtsw_wind_1m, rtsw_mag_1m, noaa-scales) | 5 |
| 🌍 Biosphere Resilience | USGS Earthquake GeoJSON (all_day) | 4 |
| 💹 Economic Stress | Yahoo Finance Chart API (v8) — 20+ тікерів | 20+ |
| 🌿 Supply Chain | Yahoo Finance commodities (Crude Oil, Natural Gas, Gold, Wheat...) | 8 |
| 📰 Geopolitics & Conflicts | Google News RSS (war/conflict/sanctions), ReliefWeb RSS | 3 |
| 📊 Social Sentiment | Wikimedia Pageviews API, Mastodon public timeline | 13 |
| 🌐 Internet Stability | TCP latency to 5 global DNS resolvers (8.8.8.8, 1.1.1.1...) | 10 |
| 🌦 Climate Risk | Open-Meteo Current Weather для 10 міст | 80 |
| ⚡ Energy Stability | Розрахований з Supply Chain + Economic Stress | composite |
| 📡 Information Pressure | Інверсія Social Sentiment density | composite |

---

## Вагові коефіцієнти (Global State Index)

| Категорія | Вага |
|---|---|
| Geopolitics & Conflicts | 18% |
| Economic Stress | 15% |
| Biosphere Resilience | 14% |
| Social Sentiment | 14% |
| Information Pressure | 10% |
| Internet Stability | 8% |
| Supply Chain | 8% |
| Energy Stability | 7% |
| Climate Risk | 3% |
| Space Weather | 3% |

---

## Запуск локально

```powershell
# Один раз збираємо дані
py fetch_data.py

# Запускаємо сервер і відкриваємо браузер
.\start.ps1
```

Або вручну:
```powershell
py -m http.server 8080
# → відкрийте http://localhost:8080/index.html
```

---

## GitHub Pages + автооновлення

Репозиторій налаштовано так, що GitHub Actions:
1. Запускає `fetch_data.py` **кожні 15 хвилин**
2. Записує `data/gsi_state.json` і `data/gsi_history.json`
3. Комітить зміни назад у репозиторій
4. GitHub Pages автоматично оновлює сайт

### Кроки розгортання на GitHub:
```bash
git init
git add .
git commit -m "initial: GSI Situational Awareness Platform"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/gsi.git
git push -u origin main
```

Потім у Settings → Pages → Source: `main` / `/ (root)`

---

## Формули нормалізації (приклади)

**Earthquake Count (24h):**
$$S = \text{clamp}\left(100 - \frac{N - 20}{180} \times 100,\ 0,\ 100\right)$$

**VIX (Market Fear Index):**
$$S = \text{clamp}\left(100 - \frac{\text{VIX} - 12}{23} \times 100,\ 0,\ 100\right)$$

**Solar Wind Speed:**
$$S = \text{clamp}\left(100 - \frac{v - 300}{500} \times 100,\ 0,\ 100\right)$$

**Wikipedia Pageviews (log scale):**
$$S = \text{clamp}\left(100 - \frac{\log_{10}(\text{views}) - 2.5}{1.8} \times 100,\ 0,\ 100\right)$$

---

## Signal Explorer

Клікніть на будь-яку категорію на дашборді, щоб побачити:
- Назву сигналу
- Необроблене (raw) значення з одиницями виміру
- Джерело з посиланням
- Формулу нормалізації
- Пояснення що цей сигнал вимірює

---

## Ліцензія

MIT — вільне використання, адаптація та публікація з посиланням.

---

*IBONARIUM · CHRONOS 7D · lavandaaudit.project.2026*
