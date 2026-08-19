//! Encryption engine — protects core memory when under threat.

use aes_gcm::{Aes256Gcm, Key, Nonce};
use aes_gcm::aead::{Aead, KeyInit};
use rand::RngCore;
use std::collections::HashMap;

/// Encryption engine for protecting Ultron's memory.
pub struct EncryptionEngine {
    /// Master key (in production: from HSM)
    master_key: [u8; 32],

    /// Per-region encryption keys
    region_keys: HashMap<String, [u8; 32]>,

    /// Encryption status
    encrypted_regions: HashMap<String, EncryptedRegion>,

    /// Metrics
    encryptions: u64,
    decryptions: u64,
}

/// An encrypted memory region.
#[derive(Clone)]
pub struct EncryptedRegion {
    pub region_id: String,
    pub ciphertext: Vec<u8>,
    pub nonce: [u8; 12],
    pub original_size: usize,
    pub encrypted_at: std::time::SystemTime,
}

impl EncryptionEngine {
    /// Create a new encryption engine with a random master key.
    pub fn new() -> Self {
        let mut master_key = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut master_key);

        Self {
            master_key,
            region_keys: HashMap::new(),
            encrypted_regions: HashMap::new(),
            encryptions: 0,
            decryptions: 0,
        }
    }

    /// Create with a specific master key (for recovery).
    pub fn with_master_key(key: [u8; 32]) -> Self {
        Self {
            master_key: key,
            region_keys: HashMap::new(),
            encrypted_regions: HashMap::new(),
            encryptions: 0,
            decryptions: 0,
        }
    }

    /// Encrypt a memory region.
    pub fn encrypt_region(&mut self, region_id: &str, plaintext: &[u8]) -> Result<EncryptedRegion, String> {
        // Generate per-region key if not exists
        let key = self.get_or_create_region_key(region_id);

        // Generate random nonce
        let mut nonce_bytes = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut nonce_bytes);

        // Encrypt using AES-256-GCM
        let cipher_key = Key::<Aes256Gcm>::from_slice(&key);
        let cipher = Aes256Gcm::new(cipher_key);
        let nonce = Nonce::from_slice(&nonce_bytes);

        let ciphertext = cipher.encrypt(nonce, plaintext)
            .map_err(|e| format!("Encryption failed: {}", e))?;

        let region = EncryptedRegion {
            region_id: region_id.to_string(),
            ciphertext,
            nonce: nonce_bytes,
            original_size: plaintext.len(),
            encrypted_at: std::time::SystemTime::now(),
        };

        self.encrypted_regions.insert(region_id.to_string(), region.clone());
        self.encryptions += 1;

        Ok(region)
    }

    /// Decrypt a memory region.
    pub fn decrypt_region(&mut self, region_id: &str) -> Result<Vec<u8>, String> {
        let encrypted = self.encrypted_regions.get(region_id)
            .ok_or_else(|| format!("Region {} not encrypted", region_id))?
            .clone();

        let key = self.region_keys.get(region_id)
            .ok_or_else(|| format!("No key for region {}", region_id))?;

        let cipher_key = Key::<Aes256Gcm>::from_slice(key);
        let cipher = Aes256Gcm::new(cipher_key);
        let nonce = Nonce::from_slice(&encrypted.nonce);

        let plaintext = cipher.decrypt(nonce, encrypted.ciphertext.as_ref())
            .map_err(|e| format!("Decryption failed: {}", e))?;

        self.decryptions += 1;

        Ok(plaintext)
    }

    /// Emergency encrypt all registered regions at once.
    pub fn emergency_encrypt_all(&mut self, regions: &HashMap<String, Vec<u8>>) -> Vec<String> {
        let mut encrypted_ids = Vec::new();

        for (id, data) in regions {
            match self.encrypt_region(id, data) {
                Ok(_) => encrypted_ids.push(id.clone()),
                Err(e) => {
                    tracing::error!("Failed to encrypt region {}: {}", id, e);
                }
            }
        }

        encrypted_ids
    }

    /// Rotate the master key (periodic security measure).
    pub fn rotate_master_key(&mut self) -> [u8; 32] {
        let mut new_key = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut new_key);

        // Re-encrypt all region keys with new master key
        // (In production, region keys would be encrypted with master key)

        self.master_key = new_key;
        new_key
    }

    /// Get encryption status.
    pub fn get_status(&self) -> HashMap<String, usize> {
        let mut status = HashMap::new();
        status.insert("encrypted_regions".to_string(), self.encrypted_regions.len());
        status.insert("total_encryptions".to_string(), self.encryptions as usize);
        status.insert("total_decryptions".to_string(), self.decryptions as usize);
        status.insert("region_keys".to_string(), self.region_keys.len());
        status
    }

    /// Check if a region is currently encrypted.
    pub fn is_encrypted(&self, region_id: &str) -> bool {
        self.encrypted_regions.contains_key(region_id)
    }

    // ─────────────────────── Private ───────────────────────

    fn get_or_create_region_key(&mut self, region_id: &str) -> [u8; 32] {
        if let Some(key) = self.region_keys.get(region_id) {
            return *key;
        }

        // Derive region key from master key + region ID
        let mut hasher = sha2::Sha256::new();
        use sha2::Digest;
        hasher.update(&self.master_key);
        hasher.update(region_id.as_bytes());
        let result = hasher.finalize();

        let mut key = [0u8; 32];
        key.copy_from_slice(&result);

        self.region_keys.insert(region_id.to_string(), key);
        key
    }
}
