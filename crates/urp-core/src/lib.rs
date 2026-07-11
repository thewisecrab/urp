use std::collections::BTreeMap;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Contract {
    ExactBytes,
    ExactLogical,
    BoundedApprox,
    Semantic,
    Derived,
    Tombstone,
    Unknown(String),
}

impl Contract {
    pub fn as_str(&self) -> &str {
        match self {
            Contract::ExactBytes => "exact_bytes",
            Contract::ExactLogical => "exact_logical",
            Contract::BoundedApprox => "bounded_approx",
            Contract::Semantic => "semantic",
            Contract::Derived => "derived",
            Contract::Tombstone => "tombstone",
            Contract::Unknown(value) => value.as_str(),
        }
    }
}

impl From<&str> for Contract {
    fn from(value: &str) -> Self {
        match value {
            "exact_bytes" => Contract::ExactBytes,
            "exact_logical" => Contract::ExactLogical,
            "bounded_approx" => Contract::BoundedApprox,
            "semantic" => Contract::Semantic,
            "derived" => Contract::Derived,
            "tombstone" => Contract::Tombstone,
            other => Contract::Unknown(other.to_string()),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkUnitKind {
    ByteObject,
    File,
    PromptRequest,
    EmbeddingRequest,
    TableSnapshot,
    PluginAction,
    Unknown(String),
}

impl WorkUnitKind {
    pub fn as_str(&self) -> &str {
        match self {
            WorkUnitKind::ByteObject => "byte_object",
            WorkUnitKind::File => "file",
            WorkUnitKind::PromptRequest => "prompt_request",
            WorkUnitKind::EmbeddingRequest => "embedding_request",
            WorkUnitKind::TableSnapshot => "table_snapshot",
            WorkUnitKind::PluginAction => "plugin_action",
            WorkUnitKind::Unknown(value) => value.as_str(),
        }
    }
}

impl From<&str> for WorkUnitKind {
    fn from(value: &str) -> Self {
        match value {
            "byte_object" => WorkUnitKind::ByteObject,
            "file" => WorkUnitKind::File,
            "prompt_request" => WorkUnitKind::PromptRequest,
            "embedding_request" => WorkUnitKind::EmbeddingRequest,
            "table_snapshot" => WorkUnitKind::TableSnapshot,
            "plugin_action" => WorkUnitKind::PluginAction,
            other => WorkUnitKind::Unknown(other.to_string()),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkUnit {
    pub id: String,
    pub trace_id: String,
    pub kind: WorkUnitKind,
    pub tenant: String,
    pub logical_ref: String,
    pub contract: Contract,
    pub payload: Vec<u8>,
    pub metadata: BTreeMap<String, String>,
    pub tags: BTreeMap<String, String>,
}

impl WorkUnit {
    pub fn new(
        kind: WorkUnitKind,
        tenant: impl Into<String>,
        logical_ref: impl Into<String>,
    ) -> Self {
        Self {
            id: new_id("wu"),
            trace_id: new_id("tr"),
            kind,
            tenant: tenant.into(),
            logical_ref: logical_ref.into(),
            contract: Contract::ExactBytes,
            payload: Vec::new(),
            metadata: BTreeMap::new(),
            tags: BTreeMap::new(),
        }
    }

    pub fn contract(mut self, contract: Contract) -> Self {
        self.contract = contract;
        self
    }

    pub fn payload(mut self, payload: Vec<u8>) -> Self {
        self.payload = payload;
        self
    }

    pub fn metadata(mut self, metadata: BTreeMap<String, String>) -> Self {
        self.metadata = metadata;
        self
    }

    pub fn tags(mut self, tags: BTreeMap<String, String>) -> Self {
        self.tags = tags;
        self
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerificationResult {
    pub verifier: String,
    pub passed: bool,
    pub reason: String,
}

pub fn new_id(prefix: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{}_{}", prefix, nanos)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unknown_contract_roundtrips() {
        let contract = Contract::from("future_contract");
        assert_eq!(contract.as_str(), "future_contract");
    }

    #[test]
    fn work_unit_defaults_exact() {
        let wu = WorkUnit::new(WorkUnitKind::ByteObject, "tenant", "s3://b/k");
        assert_eq!(wu.contract, Contract::ExactBytes);
        assert!(wu.id.starts_with("wu_"));
        assert!(wu.trace_id.starts_with("tr_"));
    }
}
