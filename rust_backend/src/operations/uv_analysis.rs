use crate::server::protocol::{UVIslandInfo, UVBounds, IslandTransform, PackTransform};

/// Detect UV islands using flood-fill on UV connectivity.
/// Each disconnected UV component becomes one island.
pub fn detect_islands(
    uv_coords: &[[f64; 2]],
    seams: Option<&[[usize; 2]]>,
) -> Vec<UVIslandInfo> {
    if uv_coords.is_empty() {
        return vec![];
    }

    // Build seam edge set for quick lookup
    let seam_set: std::collections::HashSet<(usize, usize)> = seams
        .unwrap_or(&[])
        .iter()
        .map(|e| if e[0] < e[1] { (e[0], e[1]) } else { (e[1], e[0]) })
        .collect();

    // Group nearby UV points as one island (simplified: cluster by proximity)
    let mut visited = vec![false; uv_coords.len()];
    let mut islands: Vec<Vec<usize>> = vec![];

    for start in 0..uv_coords.len() {
        if visited[start] {
            continue;
        }

        // BFS flood fill — connect UVs that are very close together
        let mut island = vec![];
        let mut queue = vec![start];
        visited[start] = true;

        while let Some(idx) = queue.pop() {
            island.push(idx);
            let uv = uv_coords[idx];

            for (other, other_uv) in uv_coords.iter().enumerate() {
                if visited[other] {
                    continue;
                }
                let edge = if idx < other { (idx, other) } else { (other, idx) };
                if seam_set.contains(&edge) {
                    continue;
                }
                let dist = ((uv[0] - other_uv[0]).powi(2) + (uv[1] - other_uv[1]).powi(2)).sqrt();
                if dist < 0.01 {
                    visited[other] = true;
                    queue.push(other);
                }
            }
        }

        if !island.is_empty() {
            islands.push(island);
        }
    }

    // Convert to UVIslandInfo
    islands
        .into_iter()
        .enumerate()
        .map(|(i, indices)| {
            let uvs: Vec<[f64; 2]> = indices.iter().map(|&idx| uv_coords[idx]).collect();
            let bounds = compute_uv_bounds(&uvs);
            let center = [
                (bounds.min[0] + bounds.max[0]) / 2.0,
                (bounds.min[1] + bounds.max[1]) / 2.0,
            ];
            let area = (bounds.max[0] - bounds.min[0]) * (bounds.max[1] - bounds.min[1]);

            UVIslandInfo {
                id: format!("uv_{:03}", i + 1),
                area: area.max(0.0),
                center,
                bounds,
                face_count: indices.len(),
                symmetrical_to: None,
            }
        })
        .collect()
}

/// Simple shelf-bin UV island packing.
pub fn pack_islands_simple(
    islands: &[serde_json::Value],
    _canvas_size: u32,
    margin: f64,
) -> Vec<IslandTransform> {
    let mut x = margin;
    let mut y = margin;
    let mut row_height = 0.0f64;
    let max_width = 1.0 - margin;

    islands.iter().map(|island| {
        let id = island["id"].as_str().unwrap_or("unknown").to_string();
        let area = island["area"].as_f64().unwrap_or(0.1);
        let size = area.sqrt().min(0.5).max(0.05);

        // Shelf pack
        if x + size > max_width {
            x = margin;
            y += row_height + margin;
            row_height = 0.0;
        }

        let offset = [x, y];
        x += size + margin;
        if size > row_height {
            row_height = size;
        }

        IslandTransform {
            id,
            transform: PackTransform {
                offset,
                scale: size,
            },
        }
    }).collect()
}

fn compute_uv_bounds(uvs: &[[f64; 2]]) -> UVBounds {
    if uvs.is_empty() {
        return UVBounds { min: [0.0, 0.0], max: [1.0, 1.0] };
    }

    let mut min = uvs[0];
    let mut max = uvs[0];

    for uv in uvs {
        if uv[0] < min[0] { min[0] = uv[0]; }
        if uv[1] < min[1] { min[1] = uv[1]; }
        if uv[0] > max[0] { max[0] = uv[0]; }
        if uv[1] > max[1] { max[1] = uv[1]; }
    }

    UVBounds { min, max }
}
