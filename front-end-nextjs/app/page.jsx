"use client";

import { useState } from "react";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010").replace(/\/$/, "");

export default function Page() {
  const [input, setInput] = useState("https://x.com/HeyElsaAI");
  const [img, setImg] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  async function onGenerate() {
    setLoading(true);
    setErr(null);
    setImg(null);
    try {
      const res = await fetch(`${API_BASE}/generate-qr/?url=${encodeURIComponent(input)}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      if (!data.presigned_url) throw new Error("Backend did not return presigned_url");
      setImg(data.presigned_url);
    } catch (e) {
      setErr(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#111", color:"#fff" }}>
      <div style={{ width: 560, maxWidth: "92vw", display: "grid", gap: 14, padding: 24, borderRadius: 16, background: "#1b1b1b" }}>
        <h1 style={{ margin: 0, fontSize: 44 }}>QR Code Generator</h1>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="https://x.com/HeyElsaAI"
          style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #444", fontSize: 16, outline: "none", color:"#fff", background:"#111" }}
        />
        <button
          onClick={onGenerate}
          disabled={loading}
          style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #2a6df4", background: "#2a6df4", color: "#fff", cursor: "pointer" }}
        >
          {loading ? "Generating…" : "Generate QR Code"}
        </button>

        {err && <div style={{ color: "#ff6b6b", fontSize: 14 }}><strong>Error:</strong> {err}</div>}

        {img && (
          <div style={{ display: "grid", placeItems: "center", gap: 8, marginTop: 8 }}>
            <img src={img} alt="QR" style={{ maxWidth: 320, borderRadius: 12, border: "1px solid #333" }} />
            <a href={img} download="qr.png" style={{ fontSize: 14, color:"#9ecbff" }}>Download PNG</a>
          </div>
        )}
      </div>
    </main>
  );
}
