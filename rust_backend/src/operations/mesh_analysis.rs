use std::collections::HashMap;

/// Compute axis-aligned bounding box for a vertex list.
/// Returns (min [x,y,z], max [x,y,z]).
pub fn compute_bounds(vertices: &[[f64; 3]]) -> ([f64; 3], [f64; 3]) {
    if vertices.is_empty() {
        return ([0.0; 3], [0.0; 3]);
    }

    let mut min = vertices[0];
    let mut max = vertices[0];

    for v in vertices {
        for i in 0..3 {
            if v[i] < min[i] { min[i] = v[i]; }
            if v[i] > max[i] { max[i] = v[i]; }
        }
    }

    (min, max)
}

/// Check approximate X-axis mirror symmetry.
/// Returns true if >80% of vertices have a mirror counterpart.
pub fn check_x_symmetry(vertices: &[[f64; 3]], tolerance: f64) -> bool {
    if vertices.len() < 4 {
        return false;
    }

    let precision = (1.0 / tolerance) as i64;
    let vertex_set: std::collections::HashSet<(i64, i64, i64)> = vertices
        .iter()
        .map(|v| (
            (v[0] * precision as f64) as i64,
            (v[1] * precision as f64) as i64,
            (v[2] * precision as f64) as i64,
        ))
        .collect();

    let mirrored_count = vertices.iter().filter(|v| {
        let mirror = (
            (-v[0] * precision as f64) as i64,
            (v[1] * precision as f64) as i64,
            (v[2] * precision as f64) as i64,
        );
        vertex_set.contains(&mirror)
    }).count();

    mirrored_count as f64 > vertices.len() as f64 * 0.8
}

/// Check if a mesh is manifold (every edge referenced by exactly 2 faces).
pub fn check_manifold(faces: &[Vec<usize>]) -> bool {
    let mut edge_count: HashMap<(usize, usize), u32> = HashMap::new();

    for face in faces {
        let n = face.len();
        for i in 0..n {
            let a = face[i];
            let b = face[(i + 1) % n];
            let edge = if a < b { (a, b) } else { (b, a) };
            *edge_count.entry(edge).or_insert(0) += 1;
        }
    }

    edge_count.values().all(|&count| count == 2)
}
