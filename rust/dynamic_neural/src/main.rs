/// Ultron Dynamic Neural Architecture — HTTP Service
use anyhow::Result;
use dynamic_neural::NeuralMesh;
use std::sync::{Arc, Mutex};
use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tracing::{info, Level};
use serde_json::json;

type SharedMesh = Arc<Mutex<Option<NeuralMesh>>>;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt().with_max_level(Level::INFO).with_target(false).init();

    let port: u16 = std::env::var("ULTRON_NEURAL_HTTP_PORT")
        .unwrap_or_else(|_| "50053".to_string())
        .parse().unwrap_or(50053);

    info!("╔══════════════════════════════════════════╗");
    info!("║  ULTRON DYNAMIC NEURAL MESH — ONLINE     ║");
    info!("║  Port: {:<6}                           ║", port);
    info!("╚══════════════════════════════════════════╝");

    let mesh: SharedMesh = Arc::new(Mutex::new(None));
    {
        let cfg = dynamic_neural::neural_types::NeuralConfig {
            initial_neurons: 256,
            max_neurons: 4096,
            initial_connections: 512,
            max_connections: 16384,
            plasticity_rate: 0.01,
            pruning_threshold: 0.001,
            growth_rate: 0.005,
            learning_rate: 0.01,
        };
        match NeuralMesh::new(cfg) {
            Ok(m) => {
                *mesh.lock().unwrap() = Some(m);
                info!("✓ Neural mesh: 256 neurons, 512 connections, Hebbian plasticity ON");
            }
            Err(e) => info!("⚠ Neural mesh init partial: {}", e),
        }
    }

    // Background plasticity loop — evolves every 10s
    let mesh_bg = mesh.clone();
    tokio::spawn(async move {
        let mut tick: u64 = 0;
        loop {
            tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
            tick += 1;
            if tick % 100 == 0 {
                if let Ok(mut guard) = mesh_bg.try_lock() {
                    if let Some(ref mut m) = *guard {
                        let _ = m.evolve(0.75);
                    }
                }
            }
        }
    });

    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).await?;
    info!("Neural mesh HTTP listening on :{}", port);

    loop {
        if let Ok((mut stream, _)) = listener.accept().await {
            let mesh_conn = mesh.clone();
            tokio::spawn(async move {
                let mut buf = vec![0u8; 4096];
                let n = match stream.read(&mut buf).await { Ok(n) => n, Err(_) => return };
                let req = String::from_utf8_lossy(&buf[..n]);
                let path = req.lines().next()
                    .and_then(|l| l.split_whitespace().nth(1))
                    .unwrap_or("/");

                let body = match path {
                    "/metrics" | "/status" => {
                        let guard = mesh_conn.lock().unwrap();
                        if let Some(ref m) = *guard {
                            let mx = m.get_metrics();
                            serde_json::to_string(&json!({
                                "status": "online",
                                "neurons": mx.total_neurons,
                                "connections": mx.total_connections,
                                "avg_activation": mx.average_activation,
                                "plasticity_events": mx.plasticity_changes,
                                "evolution_cycles": mx.architecture_changes,
                                "latency_ms": mx.processing_latency_ms,
                                "memory_mb": mx.memory_usage_mb,
                            })).unwrap_or_default()
                        } else {
                            json!({"status":"initializing"}).to_string()
                        }
                    }
                    "/health" => json!({"alive":true,"service":"neural_mesh"}).to_string(),
                    _ => json!({"error":"not found"}).to_string(),
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
