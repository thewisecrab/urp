pub fn fixed_chunks(data: &[u8], size: usize) -> Vec<&[u8]> {
    if size == 0 { return vec![data]; }
    data.chunks(size).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn chunks() {
        let data = b"abcdef";
        assert_eq!(fixed_chunks(data, 2).len(), 3);
    }
}
