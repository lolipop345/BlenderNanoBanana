use axum::{extract::Json, http::StatusCode, response::IntoResponse};
use tracing::{info, error};

use super::protocol::*;
use crate::operations::{mesh_analysis, uv_analysis, image_processing};

// ── Health ────────────────────────────────────────────────────────────────────

pub async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
    })
}

// ── Mesh Analysis ─────────────────────────────────────────────────────────────

pub async fn analyze_mesh(
    Json(req): Json<AnalyzeMeshRequest>,
) -> impl IntoResponse {
    info!("analyze_mesh: {} verts, {} faces", req.vertices.len(), req.faces.len());

    let bounds = mesh_analysis::compute_bounds(&req.vertices);
    let has_symmetry = mesh_analysis::check_x_symmetry(&req.vertices, 0.001);
    let is_manifold = mesh_analysis::check_manifold(&req.faces);

    let response = MeshAnalysisResponse {
        vertex_count: req.vertices.len(),
        face_count: req.faces.len(),
        has_symmetry,
        symmetry_axis: if has_symmetry { Some("X".to_string()) } else { None },
        bounds: MeshBounds {
            min: bounds.0,
            max: bounds.1,
        },
        is_manifold,
    };

    (StatusCode::OK, Json(response))
}

// ── UV Island Analysis ────────────────────────────────────────────────────────

pub async fn analyze_uv_islands(
    Json(req): Json<AnalyzeUVRequest>,
) -> impl IntoResponse {
    info!("analyze_uv_islands: {} UV coords", req.uv_coordinates.len());

    let islands = uv_analysis::detect_islands(&req.uv_coordinates, req.seams.as_deref());
    let total_area: f64 = islands.iter().map(|i| i.area).sum();
    let island_count = islands.len();

    let response = UVAnalysisResponse {
        islands,
        total_uv_area: total_area,
        island_count,
    };

    (StatusCode::OK, Json(response))
}

// ── UV Island Packing ────────────────────────────────────────────────────────

pub async fn pack_uv_islands(
    Json(req): Json<PackUVRequest>,
) -> impl IntoResponse {
    info!("pack_uv_islands: {} islands", req.islands.len());

    let canvas_size = req.canvas_size.unwrap_or(1024);
    let margin = req.margin.unwrap_or(0.005);

    // Simple shelf-packing algorithm
    let packed = uv_analysis::pack_islands_simple(&req.islands, canvas_size, margin);
    let utilization = packed.iter()
        .map(|p| p.transform.scale * p.transform.scale)
        .sum::<f64>()
        .min(1.0);

    let response = PackUVResponse {
        packed_islands: packed,
        utilization,
    };

    (StatusCode::OK, Json(response))
}

// ── Texture Processing ────────────────────────────────────────────────────────

pub async fn process_texture(
    Json(req): Json<ProcessTextureRequest>,
) -> impl IntoResponse {
    info!("process_texture: target_size={}", req.target_size);

    let format = req.output_format.as_deref().unwrap_or("png");
    let color_space = req.color_space.as_deref().unwrap_or("sRGB");

    match image_processing::process_texture_image(
        &req.image_data,
        req.target_size,
        format,
        color_space,
    ) {
        Ok(result) => (StatusCode::OK, Json(serde_json::to_value(result).unwrap())),
        Err(e) => {
            error!("process_texture error: {}", e);
            let err = ErrorResponse { error: e.to_string() };
            (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::to_value(err).unwrap()))
        }
    }
}

// ── Batch Map Optimization ────────────────────────────────────────────────────

pub async fn optimize_maps(
    Json(req): Json<OptimizeMapsRequest>,
) -> impl IntoResponse {
    info!("optimize_maps: {} maps", req.maps.len());

    let mut result_maps = std::collections::HashMap::new();
    let mut result_sizes = std::collections::HashMap::new();

    for (map_name, image_b64) in &req.maps {
        let size = req.sizes.get(map_name).copied().unwrap_or(2048);
        let format = req.formats.get(map_name).map(|s| s.as_str()).unwrap_or("sRGB");

        let file_ext = match map_name.as_str() {
            "emission" | "displacement" => "exr",
            _ => "png",
        };

        match image_processing::process_texture_image(image_b64, size, file_ext, format) {
            Ok(r) => {
                result_sizes.insert(map_name.clone(), [r.width, r.height]);
                result_maps.insert(map_name.clone(), r.image_data);
            }
            Err(e) => {
                error!("optimize_maps: failed to process '{}': {}", map_name, e);
                // Return original on failure
                result_maps.insert(map_name.clone(), image_b64.clone());
                result_sizes.insert(map_name.clone(), [size, size]);
            }
        }
    }

    let response = OptimizeMapsResponse {
        maps: result_maps,
        sizes: result_sizes,
    };

    (StatusCode::OK, Json(response))
}
