import { useState } from "react";

const initialForm = {
  firstName: "",
  lastName: "",
  mrn: "",
  provider: "",
  npi: "",
  diagnosis: "",
  medication: "",
  additionalDiagnosis: "",
  medicationHistory: "",
  patientRecords: "",
};

const labels = {
  firstName: "Patient First Name",
  lastName: "Patient Last Name",
  mrn: "Patient MRN",
  provider: "Referring Provider",
  npi: "Referring Provider NPI",
  diagnosis: "Primary Diagnosis (ICD-10)",
  medication: "Medication Name",
  additionalDiagnosis: "Additional Diagnoses",
  medicationHistory: "Medication History",
  patientRecords: "Patient Records",
};

export default function App() {
  const [form, setForm] = useState(initialForm);
  const [carePlan, setCarePlan] = useState("");
  const [loading, setLoading] = useState(false);

  const onChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setCarePlan("");
    const res = await fetch("/api/orders/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    const data = await res.json();
    setCarePlan(data.carePlan);
    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 720, margin: "2rem auto", fontFamily: "sans-serif", padding: "0 1rem" }}>
      <h1>Care Plan Generator (MVP)</h1>
      <form onSubmit={onSubmit}>
        {Object.keys(initialForm).map((key) => (
          <div key={key} style={{ marginBottom: 10 }}>
            <label style={{ display: "block", fontSize: 13, marginBottom: 2 }}>
              {labels[key]}
            </label>
            <input
              name={key}
              value={form[key]}
              onChange={onChange}
              style={{ width: "100%", padding: 6, boxSizing: "border-box" }}
            />
          </div>
        ))}
        <button
          type="submit"
          disabled={loading}
          style={{ marginTop: 12, padding: "8px 16px", cursor: loading ? "wait" : "pointer" }}
        >
          {loading ? "Generating..." : "Generate Care Plan"}
        </button>
      </form>

      {carePlan && (
        <div
          style={{
            marginTop: 24,
            padding: 16,
            border: "1px solid #ccc",
            whiteSpace: "pre-wrap",
            background: "#fafafa",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Care Plan</h2>
          {carePlan}
        </div>
      )}
    </div>
  );
}
