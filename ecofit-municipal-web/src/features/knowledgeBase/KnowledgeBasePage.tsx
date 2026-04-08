import { useEffect, useState } from "react";
import QuickNav from "../../app/layout/QuickNav";
import {
  getEnglishDocuments,
  uploadEnglishDocument,
  deleteEnglishDocument,
  getSinhalaDocuments,
  uploadSinhalaDocument,
  deleteSinhalaDocument,
} from "./KnowledgeBaseApi";

interface Document {
  doc_id: string;
  source: string;
}

type TabKey = "english" | "sinhala";

export default function KnowledgeBasePage() {
  const [activeTab, setActiveTab] = useState<TabKey>("english");

  // ── English state ───────────────────────────────────────────────
  const [engDocs, setEngDocs] = useState<Document[]>([]);
  const [engLoading, setEngLoading] = useState(false);
  const [engUploading, setEngUploading] = useState(false);
  const [engSearch, setEngSearch] = useState("");

  // ── Sinhala state ───────────────────────────────────────────────
  const [sinDocs, setSinDocs] = useState<Document[]>([]);
  const [sinLoading, setSinLoading] = useState(false);
  const [sinUploading, setSinUploading] = useState(false);
  const [sinSearch, setSinSearch] = useState("");

  // ── Fetch ───────────────────────────────────────────────────────
  const fetchEngDocs = async () => {
    setEngLoading(true);
    try {
      const data = await getEnglishDocuments();
      setEngDocs(data.documents || []);
    } catch (err) {
      console.error(err);
    }
    setEngLoading(false);
  };

  const fetchSinDocs = async () => {
    setSinLoading(true);
    try {
      const data = await getSinhalaDocuments();
      setSinDocs(data.documents || []);
    } catch (err) {
      console.error(err);
    }
    setSinLoading(false);
  };

  useEffect(() => {
    fetchEngDocs();
    fetchSinDocs();
  }, []);

  // ── Upload handlers ─────────────────────────────────────────────
  const handleEngUpload = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    setEngUploading(true);
    try {
      await uploadEnglishDocument(file);
      alert("English document uploaded successfully");
      fetchEngDocs();
    } catch (err) {
      alert("English upload failed");
      console.error(err);
    }
    setEngUploading(false);
    e.target.value = "";
  };

  const handleSinUpload = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    setSinUploading(true);
    try {
      await uploadSinhalaDocument(file);
      alert("Sinhala document uploaded successfully");
      fetchSinDocs();
    } catch (err) {
      alert("Sinhala upload failed");
      console.error(err);
    }
    setSinUploading(false);
    e.target.value = "";
  };

  // ── Delete handlers ─────────────────────────────────────────────
  const handleEngDelete = async (docId: string) => {
    if (!window.confirm("Delete this English document?")) return;
    try {
      await deleteEnglishDocument(docId);
      fetchEngDocs();
    } catch (err) {
      console.error(err);
      alert("Delete failed");
    }
  };

  const handleSinDelete = async (docId: string) => {
    if (!window.confirm("Delete this Sinhala document?")) return;
    try {
      await deleteSinhalaDocument(docId);
      fetchSinDocs();
    } catch (err) {
      console.error(err);
      alert("Delete failed");
    }
  };

  // ── Filtered lists ──────────────────────────────────────────────
  const filteredEng = engDocs.filter(
    (doc) =>
      doc.source.toLowerCase().includes(engSearch.toLowerCase()) ||
      doc.doc_id.toLowerCase().includes(engSearch.toLowerCase())
  );

  const filteredSin = sinDocs.filter(
    (doc) =>
      doc.source.toLowerCase().includes(sinSearch.toLowerCase()) ||
      doc.doc_id.toLowerCase().includes(sinSearch.toLowerCase())
  );

  // ── Render ──────────────────────────────────────────────────────
  return (
    <div className="kb-page">
      <QuickNav />

      <h1 className="kb-title">Knowledge Base</h1>

      {/* ── Tab bar ─────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: 0,
          marginBottom: 20,
          borderBottom: "2px solid #e5e5e5",
        }}
      >
        {(
          [
            { key: "english" as TabKey, label: "📄 English Documents", count: engDocs.length },
            { key: "sinhala" as TabKey, label: "📄 Sinhala Documents", count: sinDocs.length },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "12px 24px",
              border: "none",
              borderBottom:
                activeTab === tab.key
                  ? "3px solid rgb(45 106 79)"
                  : "3px solid transparent",
              background: activeTab === tab.key ? "#f0fdf4" : "transparent",
              color: activeTab === tab.key ? "rgb(45 106 79)" : "#666",
              fontWeight: activeTab === tab.key ? 800 : 500,
              fontSize: 14,
              cursor: "pointer",
              transition: "all 0.2s ease",
              borderRadius: "8px 8px 0 0",
            }}
          >
            {tab.label}
            <span
              style={{
                marginLeft: 8,
                background:
                  activeTab === tab.key
                    ? "rgb(45 106 79)"
                    : "#ddd",
                color: activeTab === tab.key ? "white" : "#666",
                padding: "2px 8px",
                borderRadius: 10,
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* ── English section ─────────────────────────────────────── */}
      {activeTab === "english" && (
        <>
          <div className="kb-upload-card">
            <label className="kb-upload-btn">
              Upload English PDF
              <input
                type="file"
                accept=".pdf"
                onChange={handleEngUpload}
                hidden
              />
            </label>

            <input
              className="kb-search"
              placeholder="Search English documents..."
              value={engSearch}
              onChange={(e) => setEngSearch(e.target.value)}
            />

            {engUploading && (
              <p className="kb-status">Uploading English document...</p>
            )}
          </div>

          {engLoading ? (
            <p className="kb-status">Loading English documents...</p>
          ) : (
            <div className="kb-table-card">
              <table className="kb-table">
                <thead>
                  <tr>
                    <th>Doc ID</th>
                    <th>Document Name</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {engDocs.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="kb-empty">
                        No English documents uploaded
                      </td>
                    </tr>
                  ) : (
                    filteredEng.map((doc) => (
                      <tr key={doc.doc_id}>
                        <td>
                          <span className="kb-id" title={doc.doc_id}>
                            {doc.doc_id}
                          </span>
                        </td>
                        <td>{doc.source}</td>
                        <td>
                          <button
                            className="kb-delete-btn"
                            onClick={() => handleEngDelete(doc.doc_id)}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Sinhala section ─────────────────────────────────────── */}
      {activeTab === "sinhala" && (
        <>
          <div className="kb-upload-card">
            <label className="kb-upload-btn">
              Upload Sinhala PDF
              <input
                type="file"
                accept=".pdf"
                onChange={handleSinUpload}
                hidden
              />
            </label>

            <input
              className="kb-search"
              placeholder="Search Sinhala documents..."
              value={sinSearch}
              onChange={(e) => setSinSearch(e.target.value)}
            />

            {sinUploading && (
              <p className="kb-status">Uploading Sinhala document...</p>
            )}
          </div>

          {sinLoading ? (
            <p className="kb-status">Loading Sinhala documents...</p>
          ) : (
            <div className="kb-table-card">
              <table className="kb-table">
                <thead>
                  <tr>
                    <th>Doc ID</th>
                    <th>Document Name</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sinDocs.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="kb-empty">
                        No Sinhala documents uploaded
                      </td>
                    </tr>
                  ) : (
                    filteredSin.map((doc) => (
                      <tr key={doc.doc_id}>
                        <td>
                          <span className="kb-id" title={doc.doc_id}>
                            {doc.doc_id}
                          </span>
                        </td>
                        <td>{doc.source}</td>
                        <td>
                          <button
                            className="kb-delete-btn"
                            onClick={() => handleSinDelete(doc.doc_id)}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}