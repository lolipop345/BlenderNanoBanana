use anyhow::{Result, anyhow};
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use image::{DynamicImage, ImageFormat, imageops::FilterType};
use std::io::Cursor;

use crate::server::protocol::TextureResponse;

/// Decode base64 image, resize to target_size×target_size, re-encode.
pub fn process_texture_image(
    image_b64: &str,
    target_size: u32,
    output_format: &str,
    _color_space: &str,
) -> Result<TextureResponse> {
    // Decode base64
    let raw = BASE64.decode(image_b64)
        .map_err(|e| anyhow!("Base64 decode error: {}", e))?;

    // Load image
    let img = image::load_from_memory(&raw)
        .map_err(|e| anyhow!("Image decode error: {}", e))?;

    // Resize (Lanczos3 = high quality)
    let resized = img.resize_exact(target_size, target_size, FilterType::Lanczos3);

    // Encode to output format
    let fmt = match output_format {
        "png" | "PNG" => ImageFormat::Png,
        "jpg" | "jpeg" | "JPG" => ImageFormat::Jpeg,
        "tif" | "tiff" | "TIF" => ImageFormat::Tiff,
        // EXR not supported by image crate in basic config — fall back to PNG
        _ => ImageFormat::Png,
    };

    let mut out_buf: Vec<u8> = Vec::new();
    resized.write_to(&mut Cursor::new(&mut out_buf), fmt)
        .map_err(|e| anyhow!("Image encode error: {}", e))?;

    let encoded = BASE64.encode(&out_buf);

    Ok(TextureResponse {
        image_data: encoded,
        width: target_size,
        height: target_size,
        format: output_format.to_string(),
    })
}
