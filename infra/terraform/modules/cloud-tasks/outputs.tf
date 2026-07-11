output "queue_id" {
  value = google_cloud_tasks_queue.this.id
}

output "queue_name" {
  value = google_cloud_tasks_queue.this.name
}
