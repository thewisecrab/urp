use std::collections::BTreeMap;

use urp_core::{Contract, WorkUnit, WorkUnitKind};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PutObjectRequest {
    pub tenant: String,
    pub bucket: String,
    pub key: String,
    pub bytes: Vec<u8>,
    pub metadata: BTreeMap<String, String>,
    pub tags: BTreeMap<String, String>,
}

impl PutObjectRequest {
    pub fn logical_ref(&self) -> String {
        format!("s3://{}/{}", self.bucket, self.key)
    }

    pub fn into_work_unit(self) -> WorkUnit {
        let logical_ref = self.logical_ref();
        WorkUnit::new(WorkUnitKind::ByteObject, self.tenant, logical_ref)
            .contract(Contract::ExactBytes)
            .payload(self.bytes)
            .metadata(self.metadata)
            .tags(self.tags)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RangeRead {
    pub manifest_id: String,
    pub start: usize,
    pub end: usize,
}

impl RangeRead {
    pub fn validate(&self) -> bool {
        self.start <= self.end
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ListObjectsRequest {
    pub bucket: String,
    pub prefix: String,
}

impl ListObjectsRequest {
    pub fn matches(&self, bucket: &str, key: &str) -> bool {
        bucket == self.bucket && key.starts_with(&self.prefix)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeleteObjectRequest {
    pub manifest_id: String,
    pub actor: String,
    pub allow_delete: bool,
    pub legal_hold: bool,
}

impl DeleteObjectRequest {
    pub fn allowed(&self) -> bool {
        self.allow_delete && !self.legal_hold
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn put_object_maps_to_exact_work_unit() {
        let request = PutObjectRequest {
            tenant: "tenant".to_string(),
            bucket: "bucket".to_string(),
            key: "key".to_string(),
            bytes: b"hello".to_vec(),
            metadata: BTreeMap::from([("content-type".to_string(), "text/plain".to_string())]),
            tags: BTreeMap::from([("data_class".to_string(), "demo".to_string())]),
        };
        let wu = request.into_work_unit();
        assert_eq!(wu.logical_ref, "s3://bucket/key");
        assert_eq!(wu.contract, Contract::ExactBytes);
        assert_eq!(wu.payload, b"hello");
        assert_eq!(
            wu.metadata.get("content-type").map(String::as_str),
            Some("text/plain")
        );
        assert_eq!(wu.tags.get("data_class").map(String::as_str), Some("demo"));
    }

    #[test]
    fn range_read_validates_bounds() {
        assert!(RangeRead {
            manifest_id: "mf_1".to_string(),
            start: 0,
            end: 4
        }
        .validate());
        assert!(!RangeRead {
            manifest_id: "mf_1".to_string(),
            start: 4,
            end: 0
        }
        .validate());
    }

    #[test]
    fn list_objects_matches_bucket_and_prefix() {
        let request = ListObjectsRequest {
            bucket: "bucket".to_string(),
            prefix: "logs/".to_string(),
        };
        assert!(request.matches("bucket", "logs/app.log"));
        assert!(!request.matches("bucket", "tmp/app.log"));
        assert!(!request.matches("other", "logs/app.log"));
    }

    #[test]
    fn delete_requires_explicit_allow_and_no_legal_hold() {
        assert!(DeleteObjectRequest {
            manifest_id: "mf_1".to_string(),
            actor: "admin".to_string(),
            allow_delete: true,
            legal_hold: false
        }
        .allowed());
        assert!(!DeleteObjectRequest {
            manifest_id: "mf_1".to_string(),
            actor: "admin".to_string(),
            allow_delete: false,
            legal_hold: false
        }
        .allowed());
        assert!(!DeleteObjectRequest {
            manifest_id: "mf_1".to_string(),
            actor: "admin".to_string(),
            allow_delete: true,
            legal_hold: true
        }
        .allowed());
    }
}
