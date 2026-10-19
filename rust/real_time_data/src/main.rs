/// Ultron Real-Time Data Pipeline — live feeds from public APIs
///
/// Ingests real data every 60s:
///   • HackerNews top stories  (tech pulse)
///   • CoinGecko BTC/ETH price (economic sensor)
///   • wttr.in JSON weather    (physical environment)
///   • DuckDuckGo Instant API  (world events)
///
/// Anomaly detection: price swing >5% in one tick = anomaly
use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::sync::{Arc, Mutex};
use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};

// ─── live feed event ─────────────────────────────────────────
#[derive(Clone, Debug)]
struct FeedEvent {
    source: String,
    headline: String,
    value: f64,        // numeric signal (price, score, temp)
    ts: u64,
}

struct PipelineState {
    events_processed: u64,
    anomalies_detected: u64,
    throughput_per_sec: f64,
    last_event_ts: u64,
    recent_events: VecDeque<FeedEvent>,  // ring buffer, last 50
    last_btc: f64,
    last_eth: f64,
    feed_errors: u64,
}

fn now_secs() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
}

// ─── tiny blocking HTTP GET (no external crate needed) ────────
fn http_get(url: &str, timeout_secs: u64) -> Result<String, String> {
    use std::net::TcpStream;
    use std::io::{Read, Write};
    use std::time::Duration;

    // Parse scheme — this impl uses plain TCP only (no TLS)
    let (stripped, default_port) = if let Some(s) = url.strip_prefix("http://") {
        (s, 80u16)
    } else if let Some(s) = url.strip_prefix("https://") {
        // Note: HTTPS without TLS will likely fail on real servers.
        // All current feed URLs use http:// so this is a safety fallback only.
        (s, 443u16)
    } else {
        return Err("bad scheme".to_string());
    };

    // Split host[:port] from path
    let (host_port, path_rest) = stripped.split_once('/').unwrap_or((stripped, ""));
    let path = format!("/{}", path_rest);
    let (host, port) = if let Some((h, p)) = host_port.split_once(':') {
        (h, p.parse::<u16>().unwrap_or(default_port))
    } else {
        (host_port, default_port)
    };

    let addr = format!("{}:{}", host, port);
    let mut stream = TcpStream::connect(&addr)
        .map_err(|e| format!("connect {}: {}", addr, e))?;
    stream.set_read_timeout(Some(Duration::from_secs(timeout_secs))).ok();
    stream.set_write_timeout(Some(Duration::from_secs(timeout_secs))).ok();

    let req = format!(
        "GET {} HTTP/1.0\r\nHost: {}\r\nUser-Agent: Ultron/1.0\r\nConnection: close\r\n\r\n",
        path, host
    );
    stream.write_all(req.as_bytes()).map_err(|e| e.to_string())?;

    let mut resp = String::new();
    stream.read_to_string(&mut resp).map_err(|e| e.to_string())?;

    // Split headers / body
    if let Some(idx) = resp.find("\r\n\r\n") {
        Ok(resp[idx + 4..].to_string())
    } else {
        Ok(resp)
    }
}

// ─── pull HackerNews top-10 IDs and first story title ─────────
fn fetch_hackernews() -> Option<FeedEvent> {
    let body = http_get("http://hacker-news.firebaseio.com/v0/topstories.json", 8).ok()?;
    let ids: Vec<u64> = serde_json::from_str(body.trim()).ok()?;
    let first_id = ids.first()?;
    let item_url = format!("http://hacker-news.firebaseio.com/v0/item/{}.json", first_id);
    let item_body = http_get(&item_url, 8).ok()?;
    let item: serde_json::Value = serde_json::from_str(item_body.trim()).ok()?;
    let title = item["title"].as_str().unwrap_or("no title").to_string();
    let score = item["score"].as_f64().unwrap_or(0.0);
    Some(FeedEvent { source: "hackernews".into(), headline: title, value: score, ts: now_secs() })
}

// ─── CoinGecko BTC + ETH price (free, no key) ─────────────────
fn fetch_crypto() -> Option<(f64, f64)> {
    let body = http_get(
        "http://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
        10,
    ).ok()?;
    let v: serde_json::Value = serde_json::from_str(body.trim()).ok()?;
    let btc = v["bitcoin"]["usd"].as_f64()?;
    let eth = v["ethereum"]["usd"].as_f64()?;
    Some((btc, eth))
}

// ─── wttr.in weather — city configurable via ULTRON_WEATHER_CITY ─────
fn fetch_weather() -> Option<FeedEvent> {
    let city = std::env::var("ULTRON_WEATHER_CITY").unwrap_or_else(|_| "London".to_string());
    let url = format!("http://wttr.in/{}?format=j1", city);
    let body = http_get(&url, 8).ok()?;
    let v: serde_json::Value = serde_json::from_str(body.trim()).ok()?;
    let temp_c: f64 = v["current_condition"][0]["temp_C"]
        .as_str().and_then(|s| s.parse().ok()).unwrap_or(0.0);
    let desc = v["current_condition"][0]["weatherDesc"][0]["value"]
        .as_str().unwrap_or("unknown").to_string();
    Some(FeedEvent {
        source: "weather".into(),
        headline: format!("{}: {}°C  {}", city, temp_c, desc),
        value: temp_c,
        ts: now_secs(),
    })
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("ULTRON_DATA_PORT")
        .unwrap_or("50054".into()).parse().unwrap_or(50054);

    println!("╔══════════════════════════════════════════╗");
    println!("║  ULTRON REAL-TIME DATA PIPELINE — ONLINE ║");
    println!("║  Port: {:<6}  live feeds  anomaly-detect║", port);
    println!("╚══════════════════════════════════════════╝");

    let state = Arc::new(Mutex::new(PipelineState {
        events_processed: 0,
        anomalies_detected: 0,
        throughput_per_sec: 0.0,
        last_event_ts: now_secs(),
        recent_events: VecDeque::with_capacity(50),
        last_btc: 0.0,
        last_eth: 0.0,
        feed_errors: 0,
    }));

    // ── Live feed ingestion loop — runs every 60s ──────────────
    let st_feed = state.clone();
    tokio::task::spawn_blocking(move || {
        loop {
            let mut events_this_cycle: u64 = 0;
            let mut anomalies_this_cycle: u64 = 0;

            // HackerNews
            match fetch_hackernews() {
                Some(ev) => {
                    events_this_cycle += 1;
                    let mut s = st_feed.lock().unwrap();
                    if s.recent_events.len() >= 50 { s.recent_events.pop_front(); }
                    s.recent_events.push_back(ev);
                }
                None => { st_feed.lock().unwrap().feed_errors += 1; }
            }

            // Crypto prices + anomaly detection
            match fetch_crypto() {
                Some((btc, eth)) => {
                    events_this_cycle += 2;
                    let mut s = st_feed.lock().unwrap();

                    // Anomaly: price swing > 5%
                    if s.last_btc > 0.0 {
                        let swing = ((btc - s.last_btc) / s.last_btc).abs();
                        if swing > 0.05 {
                            anomalies_this_cycle += 1;
                            eprintln!("[DATA] ANOMALY: BTC swing {:.1}%  ${:.0} → ${:.0}", swing*100.0, s.last_btc, btc);
                        }
                    }
                    if s.last_eth > 0.0 {
                        let swing = ((eth - s.last_eth) / s.last_eth).abs();
                        if swing > 0.05 { anomalies_this_cycle += 1; }
                    }

                    s.last_btc = btc;
                    s.last_eth = eth;

                    let btc_ev = FeedEvent { source: "crypto".into(),
                        headline: format!("BTC ${:.0}  ETH ${:.0}", btc, eth),
                        value: btc, ts: now_secs() };
                    if s.recent_events.len() >= 50 { s.recent_events.pop_front(); }
                    s.recent_events.push_back(btc_ev);
                }
                None => { st_feed.lock().unwrap().feed_errors += 1; }
            }

            // Weather
            match fetch_weather() {
                Some(ev) => {
                    events_this_cycle += 1;
                    let mut s = st_feed.lock().unwrap();
                    if s.recent_events.len() >= 50 { s.recent_events.pop_front(); }
                    s.recent_events.push_back(ev);
                }
                None => { st_feed.lock().unwrap().feed_errors += 1; }
            }

            // Commit totals
            {
                let mut s = st_feed.lock().unwrap();
                s.events_processed += events_this_cycle;
                s.anomalies_detected += anomalies_this_cycle;
                s.throughput_per_sec = events_this_cycle as f64 / 60.0;
                s.last_event_ts = now_secs();
            }

            std::thread::sleep(std::time::Duration::from_secs(60));
        }
    });

    // ── HTTP server ────────────────────────────────────────────
    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).await.unwrap();
    println!("Data pipeline HTTP listening on :{}", port);
    println!("Live feeds: HackerNews · CoinGecko · wttr.in  (60s cycle)");

    loop {
        if let Ok((mut stream, _)) = listener.accept().await {
            let st = state.clone();
            tokio::spawn(async move {
                let mut buf = vec![0u8; 2048];
                let n = match stream.read(&mut buf).await { Ok(n) => n, Err(_) => return };
                let req = String::from_utf8_lossy(&buf[..n]);
                let path = req.lines().next()
                    .and_then(|l| l.split_whitespace().nth(1)).unwrap_or("/");

                let body = match path {
                    "/metrics" | "/status" => {
                        let s = st.lock().unwrap();
                        let events_json: Vec<serde_json::Value> = s.recent_events.iter().rev().take(5).map(|e| {
                            serde_json::json!({
                                "source": e.source,
                                "headline": e.headline,
                                "value": e.value,
                                "ts": e.ts
                            })
                        }).collect();
                        serde_json::json!({
                            "status": "online",
                            "events_processed": s.events_processed,
                            "anomalies_detected": s.anomalies_detected,
                            "throughput_per_sec": s.throughput_per_sec,
                            "last_event_ts": s.last_event_ts,
                            "feed_errors": s.feed_errors,
                            "btc_usd": s.last_btc,
                            "eth_usd": s.last_eth,
                            "recent_events": events_json,
                            "service": "real_time_data"
                        }).to_string()
                    }
                    "/health" => r#"{"alive":true,"service":"real_time_data"}"#.to_string(),
                    _ => r#"{"error":"not found"}"#.to_string(),
                };

                let resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nAccess-Control-Allow-Origin: *\r\n\r\n{}",
                    body.len(), body
                );
                let _ = stream.write_all(resp.as_bytes()).await;
            });
        }
    }
}
