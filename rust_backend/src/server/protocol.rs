use serde::{Deserialize, Serialize};

// ── Request Types ──────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct AnalyzeMeshRequest {
    pub vertices: Vec<[f64; 3]>,
    pub faces: Vec<Vec<usize>>,
    pub normals: Option<Vec<[f64; 3]>>,
}

#[derive(Debug, Deserialize)]
pub struct AnalyzeUVRequest {
    pub uv_coordinates: Vec<[f64; 2]>,
    pub seams: Option<Vec<[usize; 2]>>,
}

#[derive(Debug, Deserialize)]
pub struct UVIsland {
    pub id: String,
    pub area: f64,
    pub bounds: UVBounds,
    pub face_indices: Option<Vec<usize>>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct UVBounds {
    pub min: [f64; 2],
    pub max: [f64; 2],
}

#[derive(Debug, Deserialize)]
pub struct PackUVRequest {
    pub islands: Vec<serde_json::Value>,
    pub canvas_size: Option<u32>,
    pub margin: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct ProcessTextureRequest {
    pub image_data: String,   // base64
    pub target_size: u32,
    pub output_format: Option<String>,
    pub color_space: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct OptimizeMapsRequest {
    pub maps: std::collections::HashMap<String, String>,   // map_name → base64
    pub sizes: std::collections::HashMap<String, u32>,
    pub formats: std::collections::HashMap<String, String>,
}

// ── Response Types ─────────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct MeshAnalysisResponse {
    pub vertex_count: usize,
    pub face_count: usize,
    pub has_symmetry: bool,
    pub symmetry_axis: Option<String>,
    pub bounds: MeshBounds,
    pub is_manifold: bool,
}

#[derive(Debug, Serialize)]
pub struct MeshBounds {
    pub min: [f64; 3],
    pub max: [f64; 3],
}

#[derive(Debug, Serialize)]
pub struct UVIslandInfo {
    pub id: String,
    pub area: f64,
    pub center: [f64; 2],
    pub bounds: UVBounds,
    pub face_count: usize,
    pub symmetrical_to: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct UVAnalysisResponse {
    pub islands: Vec<UVIslandInfo>,
    pub total_uv_area: f64,
    pub island_count: usize,
}

#[derive(Debug, Serialize)]
pub struct IslandTransform {
    pub id: String,
    pub transform: PackTransform,
}

#[derive(Debug, Serialize)]
pub struct PackTransform {
    pub offset: [f64; 2],
    pub scale: f64,
}

#[derive(Debug, Serialize)]
pub struct PackUVResponse {
    pub packed_islands: Vec<IslandTransform>,
    pub utilization: f64,
}

#[derive(Debug, Serialize)]
pub struct TextureResponse {
    pub image_data: String,  // base64
    pub width: u32,
    pub height: u32,
    pub format: String,
}

#[derive(Debug, Serialize)]
pub struct OptimizeMapsResponse {
    pub maps: std::collections::HashMap<String, String>,  // map_name → base64
    pub sizes: std::collections::HashMap<String, [u32; 2]>,
}

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
}
