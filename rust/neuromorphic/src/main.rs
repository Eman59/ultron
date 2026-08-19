/// Ultron Neuromorphic Computing Service — Spike-based LIF neural simulation
use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use std::sync::{Arc, Mutex};
use ultron_neuromorphic::{NeuromorphicProcessor, NeuromorphicConfig};

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("ULTRON_NEURO_PORT").unwrap_or("50056".into()).parse().unwrap_or(50056);
    println!("╔══════════════════════════════════════════╗");
    println!("║  ULTRON NEUROMORPHIC ENGINE — ONLINE     ║");
    println!("║  Port: {:<6}  LIF neurons  STDP         ║", port);
    println!("╚══════════════════════════════════════════╝");

    let cfg = NeuromorphicConfig { neuron_count: 1000, ..Default::default() };
    let proc = Arc::new(Mutex::new(NeuromorphicProcessor::new(cfg)));

    // Background spike loop
    let proc_bg = proc.clone();
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
            if let Ok(mut p) = proc_bg.try_lock() {
                let input = vec![0.5f64; 1000];
                p.step(&input);
            }
        }
    });

    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).await.unwrap();
    println!("Neuromorphic HTTP listening on :{}", port);

    loop {
        if let Ok((mut stream, _)) = listener.accept().await {
            let proc_c = proc.clone();
            tokio::spawn(async move {
                let mut buf = vec![0u8; 2048];
                let n = match stream.read(&mut buf).await { Ok(n) => n, Err(_) => return };
                let req = String::from_utf8_lossy(&buf[..n]);
                let path = req.lines().next().and_then(|l| l.split_whitespace().nth(1)).unwrap_or("/");

                let body = match path {
                    "/metrics" | "/status" => {
                        let guard = proc_c.lock().unwrap();
                        let s = guard.get_stats();
                        format!(r#"{{"status":"online","neurons":{},"active_neurons":{},"total_spikes":{},"avg_firing_rate_hz":{:.4},"sim_time_ms":{:.1},"service":"neuromorphic"}}"#,
                            s.total_neurons, s.active_neurons, s.total_spikes,
                            s.avg_firing_rate_hz, s.simulation_time_ms)
                    }
                    "/health" => r#"{"alive":true,"service":"neuromorphic"}"#.to_string(),
                    _ => r#"{"error":"not found"}"#.to_string(),
                };

                let resp = format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nAccess-Control-Allow-Origin: *\r\n\r\n{}", body.len(), body);
                let _ = stream.write_all(resp.as_bytes()).await;
            });
        }
    }
}
