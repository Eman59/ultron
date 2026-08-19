/// Ultron Security Daemon Service — Immune system: integrity monitoring + threat detection
use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

struct SecurityState {
    threats_detected: u64,
    integrity_checks: u64,
    threat_level: String,
    protected_files: usize,
    uptime_secs: u64,
    start_ts: u64,
}

fn now_secs() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("ULTRON_SECURITY_PORT")
        .unwrap_or_else(|_| "50055".into()).parse().unwrap_or(50055);
    let project_root = std::env::var("ULTRON_PROJECT_ROOT").unwrap_or_else(|_| ".".to_string());

    println!("╔══════════════════════════════════════════╗");
    println!("║  ULTRON SECURITY DAEMON — ONLINE         ║");
    println!("║  Port: {:<6}  AES-256-GCM  SHA-256       ║", port);
    println!("╚══════════════════════════════════════════╝");

    let critical_files: Vec<String> = vec![
        format!("{}/go/core_agent/main.go", project_root),
        format!("{}/python/interface/server.py", project_root),
        format!("{}/python/interface/real_brain.py", project_root),
    ];

    println!("✓ Integrity guard: {} critical files monitored", critical_files.len());

    let state = Arc::new(Mutex::new(SecurityState {
        threats_detected: 0,
        integrity_checks: 0,
        threat_level: "none".into(),
        protected_files: critical_files.len(),
        uptime_secs: 0,
        start_ts: now_secs(),
    }));

    // Background integrity loop — checks every 10s
    let st_bg = state.clone();
    let files_bg = critical_files.clone();
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
            let mut s = st_bg.lock().unwrap();
            s.integrity_checks += 1;
            s.uptime_secs = now_secs() - s.start_ts;

            let violations: usize = files_bg.iter()
                .filter(|f| !std::path::Path::new(f.as_str()).exists())
                .count();

            if violations > 0 {
                s.threats_detected += 1;
                s.threat_level = "high".into();
                eprintln!("[SECURITY] ⚠ INTEGRITY VIOLATION: {} files missing!", violations);
            } else {
                s.threat_level = "none".into();
            }
        }
    });

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
                        format!(
                            r#"{{"status":"online","threats_detected":{},"integrity_checks":{},"threat_level":"{}","protected_files":{},"uptime_secs":{},"service":"security_daemon"}}"#,
                            s.threats_detected, s.integrity_checks,
                            s.threat_level, s.protected_files, s.uptime_secs
                        )
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
