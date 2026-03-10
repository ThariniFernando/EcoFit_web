const API_BASE = "http://localhost:8001/api/v1/english_docs";

export async function getDocuments() {
  const res = await fetch(`${API_BASE}/documents`);

  if (!res.ok) {
    throw new Error("Failed to fetch documents");
  }

  return res.json();
}

export async function uploadDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData
  });

  if (!res.ok) {
    throw new Error("Upload failed");
  }

  return res.json();
}

export async function deleteDocument(docId: string) {
  const res = await fetch(`${API_BASE}/documents/${docId}`, {
    method: "DELETE"
  });

  if (!res.ok) {
    throw new Error("Delete failed");
  }

  return res.json();
}