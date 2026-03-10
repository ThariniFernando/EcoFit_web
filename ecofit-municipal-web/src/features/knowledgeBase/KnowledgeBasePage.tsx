import { useEffect, useState } from "react";
import QuickNav from "../../app/layout/QuickNav";
import {
  getDocuments,
  uploadDocument,
  deleteDocument
} from "./KnowledgeBaseApi";

interface Document {
  doc_id: string;
  source: string;
}

export default function KnowledgeBasePage() {

  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState("");

  const fetchDocs = async () => {
    setLoading(true);

    try {
      const data = await getDocuments();
      setDocs(data.documents || []);
    } catch (err) {
      console.error(err);
    }

    setLoading(false);
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleUpload = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {

    if (!e.target.files?.length) return;

    const file = e.target.files[0];

    setUploading(true);

    try {

      await uploadDocument(file);

      alert("Upload successful");

      fetchDocs();

    } catch (err) {
      alert("Upload failed");
      console.error(err);
    }

    setUploading(false);
  };

  const handleDelete = async (docId: string) => {

    const confirmDelete = window.confirm(
      "Delete this document?"
    );

    if (!confirmDelete) return;

    try {

      await deleteDocument(docId);

      fetchDocs();

    } catch (err) {
      console.error(err);
      alert("Delete failed");
    }
  };

  const filteredDocs = docs.filter((doc) =>

    doc.source.toLowerCase().includes(search.toLowerCase()) ||
    doc.doc_id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="kb-page">

      <QuickNav />

      <h1 className="kb-title">Knowledge Base</h1>

      <div className="kb-upload-card">

        <label className="kb-upload-btn">
          Upload PDF
          <input
            type="file"
            accept=".pdf"
            onChange={handleUpload}
            hidden
          />
        </label>

         <input
          className="kb-search"
          placeholder="Search documents..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        {/* <input
          type="file"
          accept=".pdf"
          onChange={handleUpload}
        /> */}

        {uploading && <p className="kb-status">Uploading...</p>}
      </div>

      {loading ? (
        <p className="kb-status">Loading documents...</p>
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

              {docs.length === 0 ? (
                <tr>
                  <td colSpan={3} className="kb-empty">No documents uploaded</td>
                </tr>
              ) : (

                filteredDocs.map((doc) => (

                  // docs.map((doc) => (

                  <tr key={doc.doc_id}>

                    {/* <td className="kb-id">
                      <td>{doc.doc_id}</td>
                    </td> */}
                    <td>
                      <span className="kb-id" title={doc.doc_id}>
                        {doc.doc_id}
                      </span>
                    </td>

                    <td>{doc.source}</td>

                    <td>
                      <button
                        className="kb-delete-btn"
                        onClick={() =>
                          handleDelete(doc.doc_id)
                        }
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

    </div>
  );
}