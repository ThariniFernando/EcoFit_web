import { apiClient } from "../../lib/apiClient";

// ── English ─────────────────────────────────────────────────────────

export async function getEnglishDocuments() {
  const res = await apiClient.get("/api/v1/english_docs/documents");
  return res.data;
}

export async function uploadEnglishDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await apiClient.post("/api/v1/english_docs/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function deleteEnglishDocument(docId: string) {
  const res = await apiClient.delete(`/api/v1/english_docs/documents/${docId}`);
  return res.data;
}

// ── Sinhala ─────────────────────────────────────────────────────────

export async function getSinhalaDocuments() {
  const res = await apiClient.get("/api/v1/sinhala_docs/documents");
  return res.data;
}

export async function uploadSinhalaDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await apiClient.post("/api/v1/sinhala_docs/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function deleteSinhalaDocument(docId: string) {
  const res = await apiClient.delete(`/api/v1/sinhala_docs/documents/${docId}`);
  return res.data;
}

// ── Backward-compatible aliases (English) ───────────────────────────

export const getDocuments = getEnglishDocuments;
export const uploadDocument = uploadEnglishDocument;
export const deleteDocument = deleteEnglishDocument;