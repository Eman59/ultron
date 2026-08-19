/// Ultron Dynamic Neural Architecture Service
/// Self-contained neural mesh — no broken lib dependency.
/// Implements: Hebbian plasticity, connection evolution, hot-swap, metrics.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use rand::Rng;

#[derive(Clone)]
struct Neuron {
    id: usize,
    activation: f32,
    threshold: f32,
    bias: f32,
    layer: usize,
}

#[derive(Clone)]
struct Connection {
    from: usize,
    to: usize,
    weight: f32,
    last_fire: u64,
}

struct NeuralMesh {
    neurons: Vec<Neuron>,
    connections: Vec<Connection>,
    tick: u64,
    plasticity_events: u64,
    evolution_cycles: u64,
    hot_swaps: u64,
    start: Instant,
}

impl NeuralMesh {
    fn new(neuron_count: usize, connection_count: usize) -> Self {
        let mut rng = rand::thread_rng();
        let mut neurons = Vec::with_capacity(neuron_count);
        for i in 0..neuron_count {
            neurons.push(Neuron {
                id: i,
                activation: rng.gen_range(0.0..0.5),
                threshold: rng.gen_range(0.3..0.7),
                bias: rng.gen_range(-0.1..0.1),
                layer: i * 4 / neuron_count,
            });
        }
        let mut connections = Vec::with_capacity(connection_count);
        for _ in 0..connection_count {
            let from = rng.gen_range(0..neuron_count);
            let to   = rng.gen_range(0..neuron_count);
            connections.push(Connection {
                from, to,
                weight: rng.gen_range(-1.0..1.0),
                last_fire: 0,
            });
        }
        Self { neurons, connections, tick: 0, plasticity_events: 0,
               evolution_cycles: 0, hot_swaps: 0, start: Instant::now() }
    }

    fn step(&mut self) {
        self.tick += 1;
        let mut rng = rand::thread_rng();

        // Forward pass — accumulate inputs
        let mut inputs = vec![0.0f32; self.neurons.len()];
        for c in &self.connections {
            if c.from < self.neurons.len() && c.to < self.neurons.len() {
                inputs[c.to] += self.neurons[c.from].activation * c.weight;
            }
        }

        // Activate neurons (sigmoid)
        for (i, n) in self.neurons.iter_mut().enumerate() {
            let net = inputs[i] + n.bias;
            n.activation = 1.0 / (1.0 + (-net).exp());
        }

        // Hebbian plasticity every 100 ticks
        if self.tick % 100 == 0 {
            let lr = 0.01f32;
            for c in self.connections.iter_mut() {
                if c.from < self.neurons.len() && c.to < self.neurons.len() {
                    let pre  = self.neurons[c.from].activation;
                    let post = self.neurons[c.to].activation;
                    c.weight += lr * pre * post;
                    c.weight = c.weight.clamp(-2.0, 2.0);
                    self.plasticity_events += 1;
                }
            }
        }

        // Structural evolution every 1000 ticks — prune weak, grow new
        if self.tick % 1000 == 0 {
            self.connections.retain(|c| c.weight.abs() > 0.005);
            let to_add = (self.connections.capacity() - self.connections.len()).min(10);
            for _ in 0..to_add {
                let from = rng.gen_range(0..self.neurons.len());
                let to   = rng.gen_range(0..self.neurons.len());
                self.connections.push(Connection { from, to, weight: rng.gen_range(-0.3..0.3), last_fire: self.tick });
            }
            self.evolution_cycles += 1;
        }

        // Hot-swap: replace weakest neuron every 5000 ticks
        if self.tick % 5000 == 0 && !self.neurons.is_empty() {
            let weakest = self.neurons.iter().enumerate()
                .min_by(|a,b| a.1.activation.partial_cmp(&b.1.activation).unwrap())
                .map(|(i,_)| i).unwrap_or(0);
            self.neurons[weakest].activation = rng.gen_range(0.0..0.3);
            self.neurons[weakest].threshold  = rng.gen_range(0.3..0.7);
            self.hot_swaps += 1;
        }
    }

    fn avg_activation(&self) -> f32 {
        if self.neurons.is_empty() { return 0.0; }
        self.neurons.iter().map(|n| n.activation).sum::<f32>() / self.neurons.len() as f32
    }

    fn metrics(&self) -> serde_json::Value {
        serde_json::json!({
            "status": "online",
            "neurons": self.neurons.len(),
            "connections": self.connections.len(),
            "avg_activation": self.avg_activation(),
            "plasticity_events": self.plasticity_events,
            "evolution_cycles": self.evolution_cycles,
            "hot_swaps": self.hot_swaps,
            "tick": self.tick,
            "uptime_secs": self.start.elapsed().as_secs(),
            "service": "dynamic_neural"
        })
    }
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("ULTRON_NEURAL_HTTP_PORT")
        .unwrap_or_else(|_| "50053".into()).parse().unwrap_or(50053);

    println!("╔══════════════════════════════════════════╗");
    println!("║  ULTRON DYNAMIC NEURAL MESH — ONLINE     ║");
    println!("║  Port: {:<6}  Hebbian  Hot-Swap  Evo    ║", port);
    println!("╚══════════════════════════════════════════╝");

    let mesh = Arc::new(Mutex::new(NeuralMesh::new(256, 512)));

    // Background plasticity loop — 100ms tick
    let mesh_bg = mesh.clone();
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
            if let Ok(mut m) = mesh_bg.try_lock() { m.step(); }
        }
    });

    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).await.unwrap();
    println!("Neural mesh HTTP listening on :{}", port);

    loop {
        if let Ok((mut stream, _)) = listener.accept().await {
            let mc = mesh.clone();
            tokio::spawn(async move {
                let mut buf = vec![0u8; 2048];
                let n = match stream.read(&mut buf).await { Ok(n) => n, Err(_) => return };
                let req = String::from_utf8_lossy(&buf[..n]);
                let path = req.lines().next()
                    .and_then(|l| l.split_whitespace().nth(1)).unwrap_or("/");

                let body = match path {
                    "/metrics" | "/status" => {
                        let guard = mc.lock().unwrap();
                        guard.metrics().to_string()
                    }
                    "/health" => r#"{"alive":true,"service":"dynamic_neural"}"#.to_string(),
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
