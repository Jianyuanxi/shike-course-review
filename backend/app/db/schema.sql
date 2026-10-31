CREATE TABLE IF NOT EXISTS app_users (
  user_id VARCHAR(64) PRIMARY KEY,
  powercontext_scope_id VARCHAR(128) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
  document_id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  relative_path VARCHAR(512) NOT NULL,
  file_type VARCHAR(8) NOT NULL,
  content_hash CHAR(64) NOT NULL,
  chunk_count INT NOT NULL DEFAULT 0,
  import_status VARCHAR(16) NOT NULL,
  error_message TEXT,
  imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_documents_user_path (user_id, relative_path)
);

CREATE TABLE IF NOT EXISTS memory_bindings (
  user_id VARCHAR(64) NOT NULL,
  concept_key VARCHAR(255) NOT NULL,
  artifact_id VARCHAR(128) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, concept_key)
);

CREATE TABLE IF NOT EXISTS search_logs (
  search_id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  query_text TEXT NOT NULL,
  embedding_model VARCHAR(255) NOT NULL,
  search_mode VARCHAR(64) NOT NULL,
  result_count INT NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL,
  error_message TEXT,
  latency_ms INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  KEY idx_search_user_time (user_id, created_at)
);

CREATE TABLE IF NOT EXISTS search_log_items (
  search_id VARCHAR(36) NOT NULL,
  chunk_id VARCHAR(64) NOT NULL,
  rrf_rank INT NOT NULL,
  rrf_score DOUBLE NOT NULL,
  weak_boost DOUBLE NOT NULL DEFAULT 0,
  final_score DOUBLE NOT NULL,
  final_rank INT NOT NULL,
  distance DOUBLE NULL,
  PRIMARY KEY (search_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS memory_operation_logs (
  operation_id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  search_id VARCHAR(36) NULL,
  operation VARCHAR(64) NOT NULL,
  http_method VARCHAR(8) NOT NULL,
  endpoint VARCHAR(255) NOT NULL,
  scope_id VARCHAR(128) NULL,
  artifact_ref VARCHAR(255) NULL,
  powercontext_request_id VARCHAR(128) NULL,
  status_code INT NULL,
  success BOOLEAN NOT NULL,
  request_summary TEXT,
  response_summary TEXT,
  latency_ms INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  KEY idx_memory_user_time (user_id, created_at)
);
