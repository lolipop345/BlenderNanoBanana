use axum::{Router, routing::post, routing::get};
use clap::Parser;
use std::net::SocketAddr;
use tower_http::cors::CorsLayer;
use tracing::info;

mod server;
mod operations;
mod models;
mod utils;

#[derive(Parser, Debug)]
#[command(name = "nano_banana_backend", about = "NanoBanana Blender Addon - Rust Backend")]
struct Args {
    /// Port to listen on
    #[arg(long, default_value_t = 7823)]
    port: u16,

    /// Host to bind to
    #[arg(long, default_value = "127.0.0.1")]
    host: String,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("nano_banana_backend=info".parse()?)
        )
        .init();

    let args = Args::parse();
    let addr: SocketAddr = format!("{}:{}", args.host, args.port).parse()?;

    let app = Router::new()
        .route("/health", get(server::handlers::health))
        .route("/analyze_mesh", post(server::handlers::analyze_mesh))
        .route("/analyze_uv_islands", post(server::handlers::analyze_uv_islands))
        .route("/pack_uv_islands", post(server::handlers::pack_uv_islands))
        .route("/process_texture", post(server::handlers::process_texture))
        .route("/optimize_maps", post(server::handlers::optimize_maps))
        .layer(CorsLayer::permissive());

    info!("NanoBanana Rust backend listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
