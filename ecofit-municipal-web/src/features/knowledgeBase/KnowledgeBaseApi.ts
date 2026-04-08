const API_BASE_ENGLISH = "http://localhost:8000/api/v1/english_docs";
const API_BASE_SINHALA = "http://localhost:8000/api/v1/sinhala_docs";

// ── English ─────────────────────────────────────────────────────────

export async function getEnglishDocuments() {
  const res = await fetch(`${API_BASE_ENGLISH}/documents`);

  if (!res.ok) {
    throw new Error("Failed to fetch English documents");
  }

  return res.json();
}

export async function uploadEnglishDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_ENGLISH}/upload`, {
    method: "POST",
    body: formData
  });

  if (!res.ok) {
    throw new Error("English upload failed");
  }

  return res.json();
}

export async function deleteEnglishDocument(docId: string) {
  const res = await fetch(`${API_BASE_ENGLISH}/documents/${docId}`, {
    method: "DELETE"
  });

  if (!res.ok) {
    throw new Error("English delete failed");
  }

  return res.json();
}

// ── Sinhala ─────────────────────────────────────────────────────────

export async function getSinhalaDocuments() {
  const res = await fetch(`${API_BASE_SINHALA}/documents`);

  if (!res.ok) {
    throw new Error("Failed to fetch Sinhala documents");
  }

  return res.json();
}

export async function uploadSinhalaDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_SINHALA}/upload`, {
    method: "POST",
    body: formData
  });

  if (!res.ok) {
    throw new Error("Sinhala upload failed");
  }

  return res.json();
}

export async function deleteSinhalaDocument(docId: string) {
  const res = await fetch(`${API_BASE_SINHALA}/documents/${docId}`, {
    method: "DELETE"
  });

  if (!res.ok) {
    throw new Error("Sinhala delete failed");
  }

  return res.json();
}

// ── Backward-compatible aliases (English) ───────────────────────────

export const getDocuments = getEnglishDocuments;
export const uploadDocument = uploadEnglishDocument;
export const deleteDocument = deleteEnglishDocument;