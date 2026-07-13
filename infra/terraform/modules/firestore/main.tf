# Firestore Native modeデータベース。
# dev/prdはマルチデータベース機能（1プロジェクト内の名前付きデータベース）で分離する
# （docs/infra/00_OVERVIEW.md §4、docs/infra/01_ARCHITECTURE.md §3.4）。

resource "google_firestore_database" "this" {
  project                 = var.project_id
  name                    = var.database_id
  location_id             = var.location_id
  type                    = "FIRESTORE_NATIVE"
  delete_protection_state = var.delete_protection_state
}

# Composite index required by sessions.py:_load_transcript
# (WHERE session_id = ? ORDER BY created_at ASC)
resource "google_firestore_index" "session_messages_by_session_created" {
  project    = var.project_id
  database   = google_firestore_database.this.name
  collection = "session_messages"

  fields {
    field_path = "session_id"
    order      = "ASCENDING"
  }
  fields {
    field_path = "created_at"
    order      = "ASCENDING"
  }
}

# Composite index required by ws.py:_inject_reconnect_history
# (WHERE session_id = ? ORDER BY created_at ASC .limit_to_last(N)).
# limit_to_last() executes server-side as ORDER BY created_at DESC LIMIT N
# (then reverses the results client-side), which needs the opposite sort
# direction from the ASCENDING index above -- Firestore composite indexes
# are direction-specific, so both must exist side by side.
resource "google_firestore_index" "session_messages_by_session_created_desc" {
  project    = var.project_id
  database   = google_firestore_database.this.name
  collection = "session_messages"

  fields {
    field_path = "session_id"
    order      = "ASCENDING"
  }
  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
}
