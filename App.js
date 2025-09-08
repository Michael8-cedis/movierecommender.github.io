// src/AdminApp.js
import React, { useEffect, useState } from "react";
import { auth, db } from "./firebaseConfig";
import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
} from "firebase/auth";
import {
  collection,
  onSnapshot,
  updateDoc,
  deleteDoc,
  doc,
  serverTimestamp,
} from "firebase/firestore";

export default function AdminApp() {
  const [user, setUser] = useState(null);
  const [resetRequests, setResetRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  // 🔹 Auth state listener
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (u) => {
      setUser(u || null);
      setLoading(false);
    });
    return () => unsub();
  }, []);

  const handleGoogle = async () => {
    try {
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });
      await signInWithPopup(auth, provider);
    } catch (err) {
      console.error("Google sign-in failed:", err);
      alert("Google sign-in failed. Please try again.");
    }
  };

  const handleLogout = async () => {
    await signOut(auth);
  };

  // 🔹 Listen for reset requests (only pending)
  useEffect(() => {
    if (!user) return;
    const q = collection(db, "reset_requests");
    const unsub = onSnapshot(q, (snapshot) => {
      const reqs = snapshot.docs.map((d) => ({ id: d.id, ...d.data() }));
      setResetRequests(reqs.filter((r) => r.status === "pending")); // ✅ show only pending
    });
    return () => unsub();
  }, [user]);

  const handleDecision = async (req, decision) => {
    try {
      let note = null;

      if (decision === "rejected") {
        note = prompt("Enter rejection note for the driver:") || "No reason provided";
        await updateDoc(doc(db, "reset_requests", req.id), {
          status: "rejected",
          note,
          resolvedAt: serverTimestamp(),
        });
        alert(`Request rejected. Reason: ${note}`);
      }

      if (decision === "approved") {
        // ✅ Approve request
        await updateDoc(doc(db, "reset_requests", req.id), {
          status: "approved",
          note: "Reset approved. Python will generate a new SafeRide ID.",
          resolvedAt: serverTimestamp(),
        });

        // ✅ Optionally clear old vehicle registration
        await deleteDoc(doc(db, "registeredVehicles", req.driver_id));

        // 🔹 No ID generation here — Python handles that part!
        alert(`Request approved for driver ${req.driver_id}. Waiting for Python to assign new ID.`);
      }
    } catch (err) {
      console.error("Decision failed:", err);
      alert("Failed to update request ❌");
    }
  };

  if (loading) {
    return <div>Loading Admin Dashboard…</div>;
  }

  if (!user) {
    return (
      <div style={{ textAlign: "center", marginTop: "20%" }}>
        <h2>SafeRide Admin Dashboard</h2>
        <p>Please sign in with Google</p>
        <button
          onClick={handleGoogle}
          style={{
            padding: "10px 20px",
            background: "#4285F4",
            color: "#fff",
            border: "none",
            borderRadius: "5px",
          }}
        >
          Sign in with Google
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: "20px" }}>
      <h1>SafeRide Admin Dashboard</h1>
      <button
        onClick={handleLogout}
        style={{
          float: "right",
          marginTop: "-50px",
          padding: "8px 15px",
          background: "red",
          color: "white",
          border: "none",
          borderRadius: "5px",
        }}
      >
        Logout
      </button>

      <h3>Welcome, Admin {user.displayName || user.email} 👋</h3>
      <p>Email: {user.email}</p>

      {/* Reset Requests */}
      <h2>📂 Reset Requests ({resetRequests.length})</h2>
      {resetRequests.length === 0 ? (
        <p>No pending requests.</p>
      ) : (
        resetRequests.map((req) => (
          <div
            key={req.id}
            style={{
              border: "1px solid #ccc",
              padding: "10px",
              marginBottom: "10px",
              borderRadius: "5px",
            }}
          >
            <p>
              <strong>Driver:</strong> {req.driver_id}
            </p>
            <p>
              <strong>Email:</strong> {req.email}
            </p>
            <p>
              <strong>Status:</strong> {req.status}
            </p>
            {req.note && (
              <p>
                <strong>Note:</strong> {req.note}
              </p>
            )}
            <button
              onClick={() => handleDecision(req, "approved")}
              style={{
                marginRight: "10px",
                background: "green",
                color: "white",
                padding: "5px 10px",
                border: "none",
                borderRadius: "5px",
              }}
            >
              ✅ Approve
            </button>
            <button
              onClick={() => handleDecision(req, "rejected")}
              style={{
                background: "red",
                color: "white",
                padding: "5px 10px",
                border: "none",
                borderRadius: "5px",
              }}
            >
              ❌ Reject
            </button>
          </div>
        ))
      )}

      {/* Driver Questions (future phase) */}
      <h2>❓ Driver Questions (0)</h2>
      <p>No questions yet.</p>
    </div>
  );
}
