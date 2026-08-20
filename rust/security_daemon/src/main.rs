/// Ultron Security Daemon — real SHA-256 integrity monitoring
///
/// Every 10 seconds:
///   - Reads each critical file and computes SHA-256
///   - Compares against a baseline captured at first run
///   - Reports tampering (content changed) separately from missing files
///   - Logs tampered files with old vs new hash
use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use sha2::{Sha256, Digest};

struct SecurityState {
    threats_detected: u64,
    integrity_checks: u64,
    threat_level: String,
    protected_files: usize,
    tampered_files: Vec<String>,
    missing_files: Vec<String>,
    uptime_secs: u64,
    start_ts: u64,
    last_check_ts: u64,
    // file path → baseline SHA-256 hex
    baselines: HashMap<String, String>,
    // file path → current SHA-256 hex (updated each check)
    current_hashes: HashMap<String, String>,
}

fn now_secs() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
}

fn sha256_file(path: &str) -> Option<String> {
    let bytes = std::fs::read(path).ok()?;
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    Some(format!("{:x}", hasher.finalize()))
}

/// Build initial SHA-256 baselines for all critical files.
fn build_baselines(files: &[String]) -> HashMap<String, String> {
    let mut map = HashMap::new();
    for f in files {
        if let Some(hash) = sha256_file(f) {
            println!("  [BASELINE] {} → {}…", f, &hash[..16]);
            map.insert(f.clone(), hash);
        } else {
            eprintln!("  [WARN] Could not hash baseline for: {}", f);
        }
    }
    map
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("ULTRON_SECURITY_PORT")
        .unwrap_or_else(|_| "50055".into()).parse().unwrap_or(50055);
    let project_root = std::env::var("ULTRON_PROJECT_ROOT")
        .unwrap_or_else(|_| ".".to_string());

    println!("╔══════════════════════════════════════════╗");
    println!("║  ULTRON SECURITY DAEMON — ONLINE         ║");
    println!("║  Port: {:<6}  SHA-256 content hashing    ║", port);
    println!("╚══════════════════════════════════════════╝");

    // Files to guard — expand as system grows
    let critical_files: Vec<String> = vec![
        format!("{}/python/interface/server.py",    project_root),
        format!("{}/python/interface/real_brain.py", project_root),
        format!("{}/python/interface/chat.html",    project_root),
        format!("{}/python/global_reach/supply_chain.py", project_root),
        format!("{}/rust/security_daemon/src/main.rs", project_root),
    ];

    println!("Building SHA-256 baselines for {} files…", critical_files.len());
    let baselines = build_baselines(&critical_files);
    println!("✓ Baselines captured. Monitoring active.");

    let state = Arc::new(Mutex::new(SecurityState {
        threats_detected: 0,
        integrity_checks: 0,
        threat_level: "none".into(),
        protected_files: critical_files.len(),
        tampered_files: vec![],
        missing_files: vec![],
        uptime_secs: 0,
        start_ts: now_secs(),
        last_check_ts: now_secs(),
        baselines,
        current_hashes: HashMap::new(),
    }));

    // ── Background integrity loop — every 10s ─────────────────
    let st_bg = state.clone();
    let files_bg = critical_files.clone();
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
            let mut s = st_bg.lock().unwrap();
            s.integrity_checks += 1;
            s.uptime_secs = now_secs() - s.start_ts;
            s.last_check_ts = now_secs();

            let mut tampered: Vec<String> = vec![];
            let mut missing:  Vec<String> = vec![];

            for path in &files_bg {
                match sha256_file(path) {
                    None => {
                        // File gone
                        missing.push(path.clone());
                        eprintln!("[SECURITY] ✗ MISSING: {}", path);
                    }
                    Some(hash) => {
                        s.current_hashes.insert(path.clone(), hash.clone());
                        if let Some(baseline) = s.baselines.get(path) {
                            if &hash != baseline {
                                // Content changed
                                tampered.push(path.clone());
                                eprintln!("[SECURITY] ⚠ TAMPERED: {}", path);
                                eprintln!("  baseline: {}…", &baseline[..24]);
                                eprintln!("  current:  {}…", &hash[..24]);
                            }
                        } else {
                            // New file (appeared after daemon started) — add to baseline
                            s.baselines.insert(path.clone(), hash);
                        }
                    }
                }
            }

            let violations = tampered.len() + missing.len();
            s.tampered_files = tampered;
            s.missing_files  = missing;

            if violations > 0 {
                s.threats_detected += 1;
                s.threat_level = if s.tampered_files.len() > 0 {
                    "critical".into()   // Content tampering is worse than missing
                } else {
                    "high".into()
                };
            } else {
                s.threat_level = "none".into();
            }
        }
    });

    // ── HTTP server ────────────────────────────────────────────
    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).await.unwrap();
    println!("Security daemon HTTP listening on :{}", port);

    loop {
        if let Ok((mut stream, _)) = listener.accept().await {
            let st = state.clone();
            tokio::spawn(async move {
                let mut buf = vec![0u8; 2048];
                let n = match stream.read(&mut buf).await { Ok(n) => n, Err(_) => return };
                let req = String::from_utf8_lossy(&buf[..n]);
                let path = req.lines().next()
                    .and_then(|l| l.split_whitespace().nth(1))
                    .unwrap_or("/");

                let body = match path {
                    "/metrics" | "/status" => {
                        let s = st.lock().unwrap();
                        // Build per-file status JSON
                        let file_status: Vec<serde_json::Value> = s.baselines.iter().map(|(fp, baseline)| {
                            let current = s.current_hashes.get(fp).cloned().unwrap_or_default();
                            let ok = !current.is_empty() && &current == baseline;
                            serde_json::json!({
                                "file": fp.split('/').last().unwrap_or(fp),
                                "ok": ok,
                                "baseline": &baseline[..16],
                                "current": if current.is_empty() { "MISSING".into() } else { current[..16].to_string() }
                            })
                        }).collect();

                        serde_json::json!({
                            "status": "online",
                            "threats_detected": s.threats_detected,
                            "integrity_checks": s.integrity_checks,
                            "threat_level": s.threat_level,
                            "protected_files": s.protected_files,
                            "tampered_files": s.tampered_files,
                            "missing_files": s.missing_files,
                            "uptime_secs": s.uptime_secs,
                            "last_check_ts": s.last_check_ts,
                            "file_status": file_status,
                            "service": "security_daemon"
                        }).to_string()
                    }
                    "/health" => r#"{"alive":true,"service":"security_daemon"}"#.to_string(),
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
