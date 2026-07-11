#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Chunk {
    pub start: usize,
    pub end: usize,
    pub data: Vec<u8>,
}

pub fn fixed_chunks(data: &[u8], size: usize) -> Vec<Chunk> {
    let size = if size == 0 { data.len().max(1) } else { size };
    data.chunks(size)
        .scan(0, |offset, part| {
            let start = *offset;
            *offset += part.len();
            Some(Chunk {
                start,
                end: start + part.len(),
                data: part.to_vec(),
            })
        })
        .collect()
}

pub fn content_defined_chunks(
    data: &[u8],
    min_size: usize,
    avg_bits: u32,
    max_size: usize,
) -> Vec<Chunk> {
    if data.is_empty() {
        return Vec::new();
    }
    assert!(min_size > 0, "min_size must be positive");
    assert!(max_size >= min_size, "max_size must be >= min_size");
    let mask = (1u32 << avg_bits) - 1;
    let mut chunks = Vec::new();
    let mut start = 0usize;
    let mut rolling = 0u32;
    for (i, byte) in data.iter().enumerate() {
        rolling = rolling
            .wrapping_shl(1)
            .wrapping_add(*byte as u32)
            .wrapping_add(0x9E37_79B1);
        let size = i - start + 1;
        if size >= min_size && ((rolling & mask) == 0 || size >= max_size) {
            chunks.push(Chunk {
                start,
                end: i + 1,
                data: data[start..=i].to_vec(),
            });
            start = i + 1;
            rolling = 0;
        }
    }
    if start < data.len() {
        chunks.push(Chunk {
            start,
            end: data.len(),
            data: data[start..].to_vec(),
        });
    }
    chunks
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_chunk_boundaries() {
        let data = b"abcdef";
        let chunks = fixed_chunks(data, 2);
        assert_eq!(chunks.len(), 3);
        assert_eq!(chunks[0].start, 0);
        assert_eq!(chunks[2].end, 6);
    }

    #[test]
    fn content_defined_covers_input() {
        let data = b"abc123abc123abc123abc123";
        let chunks = content_defined_chunks(data, 4, 3, 8);
        let restored: Vec<u8> = chunks.iter().flat_map(|chunk| chunk.data.clone()).collect();
        assert_eq!(restored, data);
    }
}
